import numpy as np
import pytest
from napari.components import ViewerModel
from napari.utils.colormaps import DirectLabelColormap
from qtpy.QtCore import Qt

from napari_julich_surfer._atlas import atlas_from_labels
from napari_julich_surfer._nomenclature import relabel_to_v31
from napari_julich_surfer._widget import JulichSurferWidget

_CHECKED = getattr(getattr(Qt, "CheckState", Qt), "Checked")
_USER_ROLE = getattr(getattr(Qt, "ItemRole", Qt), "UserRole")


@pytest.fixture
def viewer():
    return ViewerModel()


@pytest.fixture
def widget(qtbot, viewer, synthetic_atlas):
    surfer = JulichSurferWidget(viewer, atlas=synthetic_atlas)
    qtbot.addWidget(surfer)
    return surfer


def _parcel_layers(viewer):
    return [
        layer
        for layer in viewer.layers
        if layer.metadata.get("julich_role") == "parcel"
    ]


def test_loads_context_layers_and_parcel_list(widget, viewer, synthetic_atlas):
    names = [layer.name for layer in viewer.layers]
    assert any(layer.metadata.get("julich_role") == "labels" for layer in viewer.layers)
    assert "Brain outline" in names
    assert viewer.dims.ndisplay == 3
    assert widget._list.count() == len(synthetic_atlas.parcels)
    assert widget._view3d_check.isChecked()


def test_select_highlights_parcels(widget, viewer):
    widget.select([1, 2])

    assert widget.selected_values() == [1, 2]
    layers = _parcel_layers(viewer)
    assert sorted(layer.metadata["julich_value"] for layer in layers) == [1, 2]
    assert sum(layer.visible for layer in layers) == 2
    assert all(layer.vertex_colors.shape[1] == 4 for layer in layers)
    assert "2 parcels highlighted" in widget._summary.text()

    # The slice layer highlights the same values.
    labels = next(
        layer for layer in viewer.layers if layer.metadata.get("julich_role") == "labels"
    )
    assert isinstance(labels.colormap, DirectLabelColormap)
    assert labels.colormap.map([1])[0][:3].tolist() == pytest.approx(
        np.array(widget.atlas.parcel(1).color)[:3].tolist(), abs=1e-3
    )


def test_unselecting_removes_layers(widget, viewer):
    widget.select([1, 2])
    assert len(_parcel_layers(viewer)) == 2
    widget.select([1])
    assert [layer.metadata["julich_value"] for layer in _parcel_layers(viewer)] == [1]
    widget.clear_selection()
    assert len(_parcel_layers(viewer)) == 0
    assert "tick one to highlight it" in widget._summary.text()


def test_ticking_items_by_hand_updates_viewer(widget, viewer):
    item = widget._list.item(0)
    item.setCheckState(_CHECKED)
    assert widget.selected_values() == [int(item.data(_USER_ROLE))]
    assert len(_parcel_layers(viewer)) == 1


def test_filter_by_text_tissue_and_side(widget, synthetic_atlas):
    def visible():
        return [
            widget._list.item(i).text()
            for i in range(widget._list.count())
            if not widget._list.item(i).isHidden()
        ]

    widget._search.setText("tract")
    assert visible() == ["Test tract"]

    widget._search.setText("")
    widget._tissue.setCurrentIndex(1)  # grey matter
    assert "Test area TP left" in visible()
    assert "Test tract" not in visible()

    widget._tissue.setCurrentIndex(0)
    widget._side.setCurrentIndex(2)  # right
    texts = visible()
    assert "Test area TP right" in texts
    assert "Test area TP left" not in texts
    assert "Test tract" in texts  # bilateral structures stay visible


def test_opacity_and_detail_controls(widget, viewer):
    widget.select([1])
    widget._opacity.setValue(45)
    assert _parcel_layers(viewer)[0].opacity == pytest.approx(0.45)

    before = _parcel_layers(viewer)[0]
    assert len(before.vertex_colors) > 0
    widget._detail.setCurrentText("Fine")
    after = _parcel_layers(viewer)[0]
    assert after is not before  # mesh rebuilt at the new detail
    assert len(after.vertex_colors) > len(before.vertex_colors)


def test_brain_opacity_controls_the_outline(widget, viewer):
    outline = next(
        layer
        for layer in viewer.layers
        if layer.metadata.get("julich_role") == "outline"
    )
    # The closed shell must not depth-occlude the parcels inside it.
    assert outline.blending == "translucent_no_depth"

    widget._brain_opacity.setValue(35)
    assert outline.opacity == pytest.approx(0.35)
    assert outline.visible is True

    widget._brain_opacity.setValue(0)
    assert outline.opacity == pytest.approx(0.0)
    assert outline.visible is False

    widget._brain_opacity.setValue(10)
    assert outline.opacity == pytest.approx(0.10)
    assert outline.visible is True

    # The parcel slider leaves the brain shell alone.
    widget.select([1])
    widget._opacity.setValue(45)
    assert outline.opacity == pytest.approx(0.10)


def test_region_names_layer_toggles(widget, viewer):
    widget.select([1])
    names = [layer.name for layer in viewer.layers]
    assert "Region names" in names
    widget._names_check.setChecked(False)
    assert "Region names" not in [layer.name for layer in viewer.layers]
    widget._names_check.setChecked(True)
    assert "Region names" in [layer.name for layer in viewer.layers]


def test_focus_moves_camera(widget, viewer):
    widget.select([1])
    widget.focus_selected()
    parcel = widget.atlas.parcel(1)
    assert viewer.scene.camera.center == pytest.approx(list(parcel.centroid), abs=20)


def test_3d_toggle_syncs_with_viewer(widget, viewer):
    widget._view3d_check.setChecked(False)
    assert viewer.dims.ndisplay == 2
    viewer.dims.ndisplay = 3
    assert widget._view3d_check.isChecked()


def test_slice_layer_only_visible_in_2d(widget, viewer):
    labels = next(
        layer for layer in viewer.layers if layer.metadata.get("julich_role") == "labels"
    )
    assert viewer.dims.ndisplay == 3
    assert labels.visible is False
    viewer.dims.ndisplay = 2
    assert labels.visible is True


def test_v31_group_labels_and_legacy_search(qtbot, viewer):
    zz, yy, xx = np.mgrid[:28, :28, :28]
    data = np.zeros((28, 28, 28), np.int16)
    ball = (zz - 14) ** 2 + (yy - 14) ** 2 <= 25
    data[ball] = 1  # one legacy label spanning both hemispheres
    atlas = relabel_to_v31(
        atlas_from_labels(
            data, (1, 1, 1), {1: "GM Premotor cortex BA6"}, midline_x=14
        )
    )
    surfer = JulichSurferWidget(viewer, atlas=atlas)
    qtbot.addWidget(surfer)

    texts = [surfer._list.item(i).text() for i in range(surfer._list.count())]
    assert texts == [
        "Premotor cortex (Area 6 group) left · 9 areas",
        "Premotor cortex (Area 6 group) right · 9 areas",
    ]
    assert "Julich-Brain v3.1 names" in surfer._subtitle.text()

    surfer._search.setText("BA6")  # legacy string still finds it
    assert len(surfer.selected_values()) == 0
    assert sum(
        not surfer._list.item(i).isHidden() for i in range(surfer._list.count())
    ) == 2

    surfer._search.setText("6d2")  # group member also matches
    assert sum(
        not surfer._list.item(i).isHidden() for i in range(surfer._list.count())
    ) == 2


def test_missing_atlas_reports_error(qtbot, viewer, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("no network")

    monkeypatch.setattr("napari_julich_surfer._widget.fetch_juelich", boom)
    surfer = JulichSurferWidget(viewer, atlas=None)
    qtbot.addWidget(surfer)
    assert "Could not load the Jülich atlas" in surfer._subtitle.text()
    assert "no network" in surfer._subtitle.text()
    assert surfer.atlas is None
    assert surfer._retry_button is not None
