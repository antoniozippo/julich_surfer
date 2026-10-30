import numpy as np

from napari_julich_surfer._atlas import atlas_from_labels, parcel_color
from napari_julich_surfer._nomenclature import V31_MAP, V31_NAMES, relabel_to_v31

# The 62 regions of the FSL/nilearn edition (52 grey-matter areas + 10 fibre tracts).
LEGACY_REGIONS = [
    "Amygdala centromedial group",
    "Amygdala laterobasal group",
    "Amygdala superficial group",
    "Anterior intra-parietal sulcus hIP1",
    "Anterior intra-parietal sulcus hIP2",
    "Anterior intra-parietal sulcus hIP3",
    "Broca's area BA44",
    "Broca's area BA45",
    "Hippocampus cornu ammonis",
    "Hippocampus dentate gyrus",
    "Hippocampus entorhinal cortex",
    "Hippocampus hippocampal-amygdaloid transition area",
    "Hippocampus subiculum",
    "Inferior parietal lobule PF",
    "Inferior parietal lobule PFcm",
    "Inferior parietal lobule PFm",
    "Inferior parietal lobule PFop",
    "Inferior parietal lobule PFt",
    "Inferior parietal lobule PGp",
    "Inferior parietal lobule Pga",
    "Insula Id1",
    "Insula Ig1",
    "Insula Ig2",
    "Lateral geniculate body",
    "Mamillary body",
    "Medial geniculate body",
    "Premotor cortex BA6",
    "Primary auditory cortex TE1.0",
    "Primary auditory cortex TE1.1",
    "Primary auditory cortex TE1.2",
    "Primary motor cortex BA4a",
    "Primary motor cortex BA4p",
    "Primary somatosensory cortex BA1",
    "Primary somatosensory cortex BA2",
    "Primary somatosensory cortex BA3a",
    "Primary somatosensory cortex BA3b",
    "Secondary somatosensory cortex / Parietal operculum OP1",
    "Secondary somatosensory cortex / Parietal operculum OP2",
    "Secondary somatosensory cortex / Parietal operculum OP3",
    "Secondary somatosensory cortex / Parietal operculum OP4",
    "Superior parietal lobule 5Ci",
    "Superior parietal lobule 5L",
    "Superior parietal lobule 5M",
    "Superior parietal lobule 7A",
    "Superior parietal lobule 7M",
    "Superior parietal lobule 7P",
    "Superior parietal lobule 7PC",
    "Visual cortex V1 BA17",
    "Visual cortex V2 BA18",
    "Visual cortex V3V",
    "Visual cortex V4",
    "Visual cortex V5",
    "Acoustic radiation",
    "Callosal body",
    "Cingulum",
    "Corticospinal tract",
    "Fornix",
    "Inferior occipito-frontal fascicle",
    "Optic radiation",
    "Superior longitudinal fascicle",
    "Superior occipito-frontal fascicle",
    "Uncinate fascicle",
]


def _atlas_with(names_by_value, size=24):
    zz, yy, xx = np.mgrid[:size, :size, :size]
    data = np.zeros((size, size, size), np.int16)
    for index, value in enumerate(names_by_value):
        centre = 6 + index * 10
        data[(zz - centre) ** 2 + (yy - 12) ** 2 + (xx - 6) ** 2 <= 16] = value
        data[(zz - centre) ** 2 + (yy - 12) ** 2 + (xx - 18) ** 2 <= 16] = value
    return atlas_from_labels(
        data, (1, 1, 1), names_by_value, midline_x=12, split_hemispheres=True
    )


def test_mapping_covers_every_legacy_region():
    assert len(LEGACY_REGIONS) == 62
    assert set(V31_MAP) == set(LEGACY_REGIONS)


def test_white_matter_and_mamillary_are_flagged_as_not_v31():
    for name in LEGACY_REGIONS[-10:]:
        spec = V31_MAP[name]
        assert spec.in_v31 is False
        assert "not part of Julich-Brain v3.1" in spec.note
    assert V31_MAP["Mamillary body"].in_v31 is False
    assert "No Julich-Brain v3.1 counterpart" == V31_MAP["Mamillary body"].note


def test_groups_record_their_v31_members():
    expected = {
        "Premotor cortex BA6": 9,
        "Visual cortex V4": 4,
        "Amygdala centromedial group": 3,
        "Amygdala laterobasal group": 4,
        "Amygdala superficial group": 3,
        "Hippocampus cornu ammonis": 3,
        "Hippocampus subiculum": 4,
    }
    for legacy, count in expected.items():
        spec = V31_MAP[legacy]
        assert spec.is_group
        assert len(spec.members) == count
    # Groups never masquerade as a single v3.1 leaf.
    assert all(member.endswith((")", "")) for member in V31_MAP["Premotor cortex BA6"].members)
    assert "Area 6d1 (PreCG)" in V31_MAP["Premotor cortex BA6"].members


def test_single_areas_use_exact_v31_strings():
    assert V31_MAP["Primary motor cortex BA4p"].name == "Area 4p (PreCG)"
    assert V31_MAP["Visual cortex V1 BA17"].name == "Area hOc1 (V1, 17, CalcS)"
    assert V31_MAP["Primary somatosensory cortex BA1"].name == "Area 1 (PostCG)"
    assert V31_MAP["Lateral geniculate body"].name == "CGL (Metathalamus)"
    assert V31_MAP["Broca's area BA44"].name == "Area 44 (IFG)"
    assert len(set(V31_NAMES)) == len(V31_NAMES)


def test_relabel_parcels():
    atlas = _atlas_with({3: "GM Primary motor cortex BA4p", 7: "WM Uncinate fascicle"})
    renamed = relabel_to_v31(atlas)
    assert renamed.nomenclature == "Julich-Brain v3.1"

    by_label = {p.label: p for p in renamed.parcels}
    left = by_label["Area 4p (PreCG) left"]
    assert left.legacy_name == "Primary motor cortex BA4p"
    assert left.in_v31 is True
    assert left.is_group is False
    assert left.color == parcel_color("Area 4p (PreCG)", "L")
    assert left.group_member_labels == ()

    tract = next(p for p in renamed.parcels if p.hemisphere == "")
    assert tract.name == "Uncinate fascicle"  # no v3.1 equivalent, unchanged
    assert tract.in_v31 is False
    assert tract.legacy_name == ""
    assert "not part of Julich-Brain v3.1" in tract.note
    assert tract.list_label.endswith("not in v3.1")


def test_group_labels_expose_members():
    atlas = _atlas_with({5: "GM Premotor cortex BA6"}, size=30)
    renamed = relabel_to_v31(atlas)
    parcel = renamed.parcels[0]
    assert parcel.name == "Premotor cortex (Area 6 group)"
    assert parcel.is_group
    assert parcel.legacy_name == "Premotor cortex BA6"
    assert "9 areas" in parcel.list_label
    assert parcel.group_member_labels == ("6d1", "6d2", "6d3", "6ma", "6mp", "6r1", "6v1", "6v2", "6v3")


def test_unmapped_names_are_kept_and_flagged():
    atlas = _atlas_with({1: "GM Some custom area"}, size=16)
    renamed = relabel_to_v31(atlas)
    parcel = renamed.parcels[0]
    assert parcel.name == "Some custom area"
    assert parcel.in_v31 is False
    assert parcel.note == "No Julich-Brain v3.1 counterpart"
