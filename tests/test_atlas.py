import numpy as np
import pytest

from napari_julich_surfer._atlas import (
    atlas_from_labels,
    parcel_color,
    split_tissue_prefix,
)


def test_prefix_parsing():
    assert split_tissue_prefix("GM Primary motor cortex BA4p") == (
        "GM",
        "Primary motor cortex BA4p",
    )
    assert split_tissue_prefix("WM Uncinate fascicle") == ("WM", "Uncinate fascicle")
    assert split_tissue_prefix("Hippocampus_dentate gyrus") == (
        "",
        "Hippocampus dentate gyrus",
    )
    # A region whose name merely starts with the letters GM is left alone.
    assert split_tissue_prefix("GMinor area") == ("", "GMinor area")


def test_grey_matter_is_split_left_right(synthetic_atlas):
    parcels = synthetic_atlas.parcels
    sides = sorted(p.hemisphere for p in parcels if p.tissue == "GM")
    assert sides == ["L", "R"]
    labels = {p.label for p in parcels}
    assert "Test area TP left" in labels
    assert "Test area TP right" in labels
    # White-matter tracts are not split at the midline by default.
    tract = next(p for p in parcels if p.tissue == "WM")
    assert tract.hemisphere == ""
    assert tract.label == "Test tract"


def test_split_parcels_are_unilateral(synthetic_atlas):
    left = next(p for p in synthetic_atlas.parcels if p.label == "Test area TP left")
    right = next(p for p in synthetic_atlas.parcels if p.label == "Test area TP right")
    assert left.centroid[2] < right.centroid[2]
    assert left.n_voxels > 0 and right.n_voxels > 0
    assert left.color[:3] != right.color[:3]  # same hue, different value
    assert parcel_color("Test area TP", "L") == left.color


def test_values_are_contiguous_and_unique(synthetic_atlas):
    values = sorted(p.value for p in synthetic_atlas.parcels)
    assert values == list(range(1, len(values) + 1))
    for parcel in synthetic_atlas.parcels:
        assert (synthetic_atlas.data == parcel.value).sum() == parcel.n_voxels


def test_volume_and_centroid_units(synthetic_atlas):
    parcel = synthetic_atlas.parcels[0]
    assert parcel.volume_mm3 == pytest.approx(parcel.n_voxels * 8.0)  # 2 mm voxels
    assert 0 <= parcel.centroid[0] <= 30 * 2.0


def test_disable_splitting_gives_one_parcel_per_label():
    data = np.zeros((20, 20, 20), np.int16)
    data[5:15, 5:15, 2:18] = 1  # one label spanning both hemispheres
    split = atlas_from_labels(data, (1, 1, 1), {1: "GM Bilateral blob"}, midline_x=10)
    assert [p.hemisphere for p in split.parcels] == ["L", "R"]

    whole = atlas_from_labels(
        data, (1, 1, 1), {1: "GM Bilateral blob"}, split_hemispheres=False
    )
    assert len(whole.parcels) == 1
    assert whole.parcels[0].hemisphere == ""


def test_sequence_names_handle_background():
    data = np.zeros((10, 10, 10), np.int16)
    data[2:5, 2:5, 2:5] = 1
    data[6:9, 6:9, 6:9] = 2

    offset_names = atlas_from_labels(data, (1, 1, 1), ["Area one", "Area two"])
    assert [p.name for p in offset_names.parcels] == ["Area one", "Area two"]

    padded = atlas_from_labels(data, (1, 1, 1), ["Background", "Area one", "Area two"])
    assert [p.name for p in padded.parcels] == ["Area one", "Area two"]


def test_missing_names_fall_back_to_value():
    data = np.zeros((10, 10, 10), np.int16)
    data[2:6, 2:6, 2:6] = 4
    atlas = atlas_from_labels(data, (1, 1, 1), {})
    assert atlas.parcels[0].name == "Region 4"


def test_bad_input_raises():
    with pytest.raises(ValueError):
        atlas_from_labels(np.zeros((4, 4), np.int16), (1, 1), {})
    with pytest.raises(ValueError):
        atlas_from_labels(np.zeros((4, 4, 4), np.int16), (1, 1, 1), {})
    with pytest.raises(ValueError):
        atlas_from_labels(np.zeros((4, 4, 4), np.int16), (1, 1), {})


def test_atlas_from_nifti_hands_left_right_correctly(tmp_path):
    import nibabel as nib

    data = np.zeros((20, 20, 20), np.int16)
    # Axis 0 is x: index 4 sits at MNI x = -20 + 4*2 = -12, i.e. the left hemisphere.
    # One label id on both sides, like the symmetric FSL edition.
    data[2:7, 8:12, 8:12] = 1
    data[13:18, 8:12, 8:12] = 1
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    affine[:3, 3] = (-20.0, -20.0, -20.0)
    path = tmp_path / "atlas.nii.gz"
    nib.save(nib.Nifti1Image(data, affine), path)

    from napari_julich_surfer._atlas import atlas_from_nifti

    atlas = atlas_from_nifti(path, {1: "GM Bilateral area"})
    by_name = {p.label: p for p in atlas.parcels}
    assert set(by_name) == {"Bilateral area left", "Bilateral area right"}
    assert by_name["Bilateral area left"].centroid[2] < 20.0
    assert by_name["Bilateral area right"].centroid[2] > 20.0
    assert atlas.scale == (2.0, 2.0, 2.0)
    assert atlas.data.shape == (20, 20, 20)
