"""The napari dock widget: a parcel list wired to surfaces and slice colours."""

from __future__ import annotations

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ._atlas import Atlas, fetch_juelich
from ._surfaces import DEFAULT_DETAIL, DETAIL_PRESETS, SurfaceCache

# Qt5/Qt6 scoped-enum compatibility without pulling in extra helpers.
_CHECKED = getattr(getattr(Qt, "CheckState", Qt), "Checked")
_UNCHECKED = getattr(getattr(Qt, "CheckState", Qt), "Unchecked")
_USER_ROLE = getattr(getattr(Qt, "ItemRole", Qt), "UserRole")
_ITEM_CHECKABLE = getattr(getattr(Qt, "ItemFlag", Qt), "ItemIsUserCheckable")
_WAIT_CURSOR = getattr(getattr(Qt, "CursorShape", Qt), "WaitCursor")

_OUTLINE_RGBA = (0.86, 0.87, 0.92, 1.0)


class JulichSurferWidget(QWidget):
    """Pick Jülich-Brain parcels from a list; they light up in the viewer.

    Parameters
    ----------
    viewer : napari.Viewer
        Viewer to add layers to (napari supplies this for plugin widgets).
    atlas : Atlas, optional
        Pre-loaded atlas.  When omitted the Jülich atlas is fetched on creation
        (downloaded once and cached in ``~/nilearn_data``).
    """

    def __init__(self, viewer, atlas: Atlas | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._viewer = viewer
        self._atlas = atlas
        self._cache = SurfaceCache(atlas) if atlas is not None else None
        self._parcel_layers: dict[int, object] = {}
        self._labels_layer = None
        self._outline_layer = None
        self._names_layer = None
        self._updating = False
        self._busy = False
        self._framed = False
        self._retry_button = None

        self._build_ui()
        try:
            self._viewer.dims.events.ndisplay.connect(self._sync_view3d)
        except Exception:  # noqa: BLE001 - a bare ViewerModel may not expose events
            pass

        if self._atlas is None:
            self._load_atlas()
        else:
            self._on_atlas_ready()

    # ------------------------------------------------------------------ public API
    @property
    def atlas(self) -> Atlas | None:
        return self._atlas

    def selected_values(self) -> list[int]:
        """Label values of every ticked parcel."""
        values = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.checkState() == _CHECKED:
                values.append(int(item.data(_USER_ROLE)))
        return values

    def selected_parcels(self):
        if self._atlas is None:
            return []
        return [self._atlas.parcel(value) for value in self.selected_values()]

    def select(self, values) -> None:
        """Tick exactly ``values`` (label ids) and refresh the viewer."""
        wanted = {int(value) for value in values}
        self._updating = True
        try:
            for index in range(self._list.count()):
                item = self._list.item(index)
                value = int(item.data(_USER_ROLE))
                item.setCheckState(_CHECKED if value in wanted else _UNCHECKED)
        finally:
            self._updating = False
        self._refresh()

    def clear_selection(self) -> None:
        self.select([])

    def focus_selected(self) -> None:
        """Fly the camera to the selected parcels (and jump to their slice in 2-D)."""
        parcels = self.selected_parcels()
        if not parcels:
            self._viewer.reset_view()
            return
        center = np.mean([p.centroid for p in parcels], axis=0)
        layers = [
            self._parcel_layers[p.value]
            for p in parcels
            if p.value in self._parcel_layers
            and self._parcel_layers[p.value] in self._viewer.layers
        ]
        framed = False
        if layers:
            try:
                self._viewer.reset_view(
                    layers=layers, margin=0.4, reset_camera_angle=False
                )
                framed = True
            except TypeError:  # napari < 0.9 has no layers argument
                pass
        if not framed:
            try:
                self._camera.center = tuple(float(c) for c in center)
            except Exception:  # noqa: BLE001
                return
        if int(self._viewer.dims.ndisplay) < 3:
            try:
                self._viewer.dims.set_point(0, float(center[0]))
            except Exception:  # noqa: BLE001 - axis 0 is displayed in some layouts
                pass

    @property
    def _camera(self):
        # napari >= 0.9 moved the camera onto viewer.scene.
        scene = getattr(self._viewer, "scene", None)
        camera = getattr(scene, "camera", None)
        return camera if camera is not None else self._viewer.camera

    # --------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(6, 6, 6, 6)
        self._root.setSpacing(6)
        self.setMinimumWidth(320)

        title = QLabel("<b>Jülich 3D Brain Surfer</b>")
        self._subtitle = QLabel("Loading the Jülich atlas…")
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet("color: gray; font-size: 11px;")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter parcels (try BA4p, V1, hIP1…)")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)

        self._tissue = QComboBox()
        self._tissue.addItem("All tissue", None)
        self._tissue.addItem("Grey matter", "GM")
        self._tissue.addItem("White matter", "WM")
        self._tissue.currentIndexChanged.connect(self._apply_filter)

        self._side = QComboBox()
        self._side.addItem("Both sides", None)
        self._side.addItem("Left", "L")
        self._side.addItem("Right", "R")
        self._side.currentIndexChanged.connect(self._apply_filter)

        filters = QHBoxLayout()
        filters.addWidget(self._tissue, 1)
        filters.addWidget(self._side, 1)

        self._list = QListWidget()
        self._list.setToolTip(
            "Tick one or more parcels to highlight them in 3-D and 2-D"
        )
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.itemDoubleClicked.connect(self._on_item_activated)

        self._summary = QLabel()
        self._summary.setWordWrap(True)

        buttons = QHBoxLayout()
        self._focus_button = QPushButton("Focus")
        self._focus_button.setToolTip("Centre the camera on the ticked parcels")
        self._focus_button.clicked.connect(self.focus_selected)
        self._clear_button = QPushButton("Clear")
        self._clear_button.clicked.connect(self.clear_selection)
        self._reset_button = QPushButton("Reset view")
        self._reset_button.clicked.connect(self._viewer.reset_view)
        for button in (self._focus_button, self._clear_button, self._reset_button):
            buttons.addWidget(button)

        display = QGroupBox("Display")
        display_layout = QVBoxLayout(display)
        display_layout.setContentsMargins(8, 6, 8, 6)

        detail_row = QHBoxLayout()
        detail_row.addWidget(QLabel("Surface detail"))
        self._detail = QComboBox()
        for preset in DETAIL_PRESETS:
            self._detail.addItem(preset)
        self._detail.setCurrentText(DEFAULT_DETAIL)
        self._detail.setToolTip("Fast is coarse but instant; Fine is dense and slower")
        self._detail.currentIndexChanged.connect(self._on_detail_changed)
        detail_row.addWidget(self._detail, 1)

        brain_row = QHBoxLayout()
        brain_row.addWidget(QLabel("Brain"))
        self._brain_opacity = QSlider(getattr(Qt, "Orientation", Qt).Horizontal)
        self._brain_opacity.setRange(0, 100)
        self._brain_opacity.setValue(10)
        self._brain_opacity.setToolTip(
            "Opacity of the whole-brain shell; slide to 0 to hide it"
        )
        self._brain_opacity.valueChanged.connect(self._on_brain_opacity_changed)
        brain_row.addWidget(self._brain_opacity, 1)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Parcels"))
        self._opacity = QSlider(getattr(Qt, "Orientation", Qt).Horizontal)
        self._opacity.setRange(15, 100)
        self._opacity.setValue(90)
        self._opacity.setToolTip("Opacity of the highlighted parcel surfaces")
        self._opacity.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self._opacity, 1)

        self._names_check = QCheckBox("Region names")
        self._names_check.setChecked(True)
        self._names_check.toggled.connect(lambda _state: self._refresh())
        self._view3d_check = QCheckBox("3-D view")
        self._view3d_check.setChecked(True)
        self._view3d_check.toggled.connect(self._on_view3d_toggled)

        display_layout.addLayout(detail_row)
        display_layout.addLayout(brain_row)
        display_layout.addLayout(opacity_row)
        display_layout.addWidget(self._names_check)
        display_layout.addWidget(self._view3d_check)

        self._root.addWidget(title)
        self._root.addWidget(self._subtitle)
        self._root.addWidget(self._search)
        self._root.addLayout(filters)
        self._root.addWidget(self._list, 1)
        self._root.addWidget(self._summary)
        self._root.addLayout(buttons)
        self._root.addWidget(display)

    # ------------------------------------------------------------------ loading
    def _load_atlas(self) -> None:
        self._set_busy(True, "Downloading the Jülich atlas (first run only)…")
        try:
            self._atlas = fetch_juelich()
        except Exception as exc:  # noqa: BLE001 - surface the reason in the UI
            self._atlas = None
            self._subtitle.setText(f"Could not load the Jülich atlas:\n{exc}")
            self._summary.setText("No atlas loaded.")
            if self._retry_button is None:
                self._retry_button = QPushButton("Retry")
                self._retry_button.clicked.connect(self._retry_load)
                self._root.insertWidget(self._root.count() - 1, self._retry_button)
            self._retry_button.setEnabled(True)
            return
        finally:
            self._set_busy(False)
        if self._retry_button is not None:
            self._retry_button.deleteLater()
            self._retry_button = None
        self._cache = SurfaceCache(self._atlas)
        self._on_atlas_ready()

    def _retry_load(self) -> None:
        if self._retry_button is not None:
            self._retry_button.setEnabled(False)
        self._load_atlas()

    def _on_atlas_ready(self) -> None:
        assert self._atlas is not None
        self._cache = SurfaceCache(self._atlas)
        subtitle = (
            f"{len(self._atlas.parcels)} parcels · {self._atlas.space} · "
            f"{self._atlas.name}"
        )
        if self._atlas.nomenclature:
            subtitle += f" · {self._atlas.nomenclature} names"
        self._subtitle.setText(subtitle)
        self._populate()
        self._apply_filter()
        self._add_context_layers()
        self._viewer.dims.ndisplay = 3
        self._view3d_check.setChecked(True)
        self._sync_view3d()
        self._update_summary()
        if not self._framed:
            try:
                self._viewer.reset_view()
            except Exception:  # noqa: BLE001
                pass
            self._framed = True

    def _populate(self) -> None:
        self._updating = True
        try:
            self._list.clear()
            for parcel in sorted(
                self._atlas.parcels, key=lambda p: (p.name.lower(), p.hemisphere)
            ):
                item = QListWidgetItem(parcel.list_label)
                item.setData(_USER_ROLE, parcel.value)
                item.setFlags(item.flags() | _ITEM_CHECKABLE)
                item.setCheckState(_UNCHECKED)
                item.setToolTip(self._parcel_tooltip(parcel))
                self._list.addItem(item)
        finally:
            self._updating = False

    @staticmethod
    def _parcel_tooltip(parcel) -> str:
        lines = [
            parcel.label,
            f"{parcel.tissue_label} · {parcel.volume_mm3:,.0f} mm³ · "
            f"value {parcel.value}",
        ]
        if parcel.is_group:
            members = ", ".join(parcel.group_member_labels)
            lines.append(
                f"Group of {len(parcel.group_members)} Julich-Brain v3.1 areas: {members}"
            )
        if parcel.note:
            lines.append(parcel.note)
        if parcel.legacy_name:
            lines.append(f"FSL label: {parcel.legacy_name}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ layers
    def _add_context_layers(self) -> None:
        if self._labels_layer is None or self._labels_layer not in self._viewer.layers:
            self._labels_layer = self._viewer.add_labels(
                self._atlas.data,
                name="Jülich parcels (slice)",
                opacity=0.6,
                metadata={"julich_role": "labels"},
            )
            try:
                self._labels_layer.editable = False
            except Exception:  # noqa: BLE001
                pass
        self._apply_label_colormap()

        if (
            self._outline_layer is None
            or self._outline_layer not in self._viewer.layers
        ):
            mesh = self._cache.outline()
            if mesh is not None:
                colors = np.tile(
                    np.asarray(_OUTLINE_RGBA, dtype=np.float32), (len(mesh.vertices), 1)
                )
                self._outline_layer = self._viewer.add_surface(
                    (mesh.vertices, mesh.faces),
                    vertex_colors=colors,
                    name="Brain outline",
                    opacity=self._brain_opacity.value() / 100.0,
                    shading="smooth",
                    # Depth testing lets this closed shell swallow the parcels
                    # inside it, even when it is nearly transparent.
                    blending="translucent_no_depth",
                    metadata={"julich_role": "outline"},
                )
                self._apply_brain_opacity()

    def _apply_label_colormap(self) -> None:
        if self._atlas is None or self._labels_layer is None:
            return
        from napari.utils.colormaps import DirectLabelColormap

        selected = set(self.selected_values())
        dim = self._atlas.dim_color
        color_dict: dict = {None: dim}
        for parcel in self._atlas.parcels:
            color_dict[parcel.value] = (
                tuple(parcel.color[:3]) + (1.0,) if parcel.value in selected else dim
            )
        self._labels_layer.colormap = DirectLabelColormap(color_dict=color_dict)

    def _sync_parcel_layers(self, selected: set[int]) -> None:
        for value, layer in list(self._parcel_layers.items()):
            if value not in selected or layer not in self._viewer.layers:
                if layer in self._viewer.layers:
                    self._viewer.layers.remove(layer)
                del self._parcel_layers[value]

        for value in sorted(selected):
            if value in self._parcel_layers:
                continue
            parcel = self._atlas.parcel(value)
            mesh = self._cache.parcel(value, self._detail.currentText())
            if mesh is None:
                continue
            colors = np.tile(
                np.asarray(parcel.color, dtype=np.float32), (len(mesh.vertices), 1)
            )
            self._parcel_layers[value] = self._viewer.add_surface(
                (mesh.vertices, mesh.faces),
                vertex_colors=colors,
                name=parcel.label,
                opacity=self._opacity.value() / 100.0,
                shading="smooth",
                metadata={"julich_role": "parcel", "julich_value": value},
            )

    def _sync_names_layer(self, selected: set[int]) -> None:
        if (
            self._names_layer is not None
            and self._names_layer not in self._viewer.layers
        ):
            self._names_layer = None

        if not selected or not self._names_check.isChecked():
            if self._names_layer is not None:
                self._viewer.layers.remove(self._names_layer)
                self._names_layer = None
            return

        parcels = [self._atlas.parcel(value) for value in sorted(selected)]
        positions = np.asarray([p.centroid for p in parcels], dtype=float)
        text = {
            "string": [p.label for p in parcels],
            "color": "white",
            "anchor": "center",
        }
        if self._names_layer is None:
            self._names_layer = self._viewer.add_points(
                positions,
                size=4,
                face_color="transparent",
                border_color="transparent",
                text=text,
                name="Region names",
                metadata={"julich_role": "names"},
            )
        else:
            self._names_layer.data = positions
            self._names_layer.text = text

    # ------------------------------------------------------------------ updates
    def _refresh(self) -> None:
        if self._atlas is None or self._cache is None:
            return
        selected = set(self.selected_values())
        self._set_busy(True, "Building surfaces…" if selected else None)
        try:
            self._add_context_layers()
            self._sync_parcel_layers(selected)
            self._apply_label_colormap()
            self._sync_names_layer(selected)
        finally:
            self._set_busy(False)
        self._update_summary()

    def _update_summary(self) -> None:
        if self._atlas is None:
            return
        values = self.selected_values()
        if not values:
            self._summary.setText(
                f"{len(self._atlas.parcels)} parcels · tick one to highlight it"
            )
            return
        volume = sum(self._atlas.parcel(value).volume_mm3 for value in values)
        plural = "s" if len(values) > 1 else ""
        self._summary.setText(
            f"{len(values)} parcel{plural} highlighted · {volume:,.0f} mm³"
        )

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        if message is not None:
            self._summary.setText(message)
        if busy and not self._busy:
            QApplication.setOverrideCursor(_WAIT_CURSOR)
            QApplication.processEvents()
            self._busy = True
        elif not busy and self._busy:
            QApplication.restoreOverrideCursor()
            self._busy = False

    # ------------------------------------------------------------------ slots
    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        if self._updating:
            return
        self._refresh()

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        if item.checkState() != _CHECKED:
            item.setCheckState(_CHECKED)
        self.focus_selected()

    def _apply_filter(self) -> None:
        if self._atlas is None:
            return
        needle = self._search.text().strip().lower()
        tissue = self._tissue.currentData()
        side = self._side.currentData()
        for index in range(self._list.count()):
            item = self._list.item(index)
            parcel = self._atlas.parcel(int(item.data(_USER_ROLE)))
            haystack = " ".join(
                (
                    parcel.label,
                    parcel.legacy_name,
                    *parcel.group_members,
                    *parcel.group_member_labels,
                )
            ).lower()
            matches_text = not needle or needle in haystack
            matches_tissue = tissue is None or parcel.tissue == tissue
            # Bilateral structures (white-matter tracts) stay visible on either side.
            matches_side = side is None or parcel.hemisphere in ("", side)
            item.setHidden(not (matches_text and matches_tissue and matches_side))

    def _on_detail_changed(self) -> None:
        for layer in list(self._parcel_layers.values()):
            if layer in self._viewer.layers:
                self._viewer.layers.remove(layer)
        self._parcel_layers.clear()
        self._refresh()

    def _on_opacity_changed(self, value: int) -> None:
        for layer in self._parcel_layers.values():
            layer.opacity = value / 100.0

    def _apply_brain_opacity(self) -> None:
        layer = self._outline_layer
        if layer is None or layer not in self._viewer.layers:
            return
        value = self._brain_opacity.value()
        layer.opacity = value / 100.0
        layer.visible = value > 0

    def _on_brain_opacity_changed(self, _value: int) -> None:
        self._apply_brain_opacity()

    def _on_view3d_toggled(self, checked: bool) -> None:
        self._viewer.dims.ndisplay = 3 if checked else 2

    def _sync_view3d(self, _event=None) -> None:
        is_3d = int(self._viewer.dims.ndisplay) == 3
        self._view3d_check.blockSignals(True)
        self._view3d_check.setChecked(is_3d)
        self._view3d_check.blockSignals(False)
        # Labels layers render as a volume in 3-D and would fog the surfaces.
        if self._labels_layer is not None and self._labels_layer in self._viewer.layers:
            self._labels_layer.visible = not is_3d

    # ------------------------------------------------------------------ teardown
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        try:
            self._viewer.dims.events.ndisplay.disconnect(self._sync_view3d)
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)


__all__ = ["JulichSurferWidget"]
