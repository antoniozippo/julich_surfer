"""Julich-Brain v3.1 nomenclature for the legacy FSL Jülich atlas labels.

The atlas distributed through nilearn/FSL is the 2010-era Jülich histological atlas:
62 symmetric regions named in SPM-Anatomy-Toolbox style.  Julich-Brain v3.1 (siibra,
454 lateralized leaf regions) uses different strings and, for some structures, a much
deeper parcellation.

This module maps every legacy region onto its Julich-Brain v3.1 name where one exists.
Where the legacy parcel is a *group* of several v3.1 areas, the members are recorded
so the UI can label it as a group instead of pretending it is a single area.  Labels
with no v3.1 counterpart (the white-matter tracts and the mamillary body) are kept but
flagged.  Names and members were checked against the v3.1 parcellation tree in
siibra-python 1.0.1.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ._atlas import Atlas, parcel_color

V31_VERSION = "3.1"
NOMENCLATURE = f"Julich-Brain v{V31_VERSION}"

# White-matter entries of the FSL file.  Julich-Brain is a cytoarchitectonic atlas:
# none of these fibre-tract labels occur anywhere in its v3.1 hierarchy.
_WM_LABELS = (
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
)

_WM_NOTE = "FSL fibre-tract label; not part of Julich-Brain v3.1"


@dataclass(frozen=True)
class V31Mapping:
    """How one legacy region maps onto Julich-Brain v3.1."""

    name: str  # exact v3.1 name without the left/right suffix, or a group label
    members: tuple[str, ...] = ()  # v3.1 areas covered when the legacy parcel is a group
    in_v31: bool = True
    note: str = ""

    @property
    def is_group(self) -> bool:
        return len(self.members) > 1


def _single(name: str) -> V31Mapping:
    return V31Mapping(name=name)


def _group(name: str, *members: str) -> V31Mapping:
    return V31Mapping(name=name, members=members)


_GROUPS = {
    # The FSL file has one "Premotor cortex BA6"; v3.1 splits area 6 into nine areas.
    "Premotor cortex BA6": _group(
        "Premotor cortex (Area 6 group)",
        "Area 6d1 (PreCG)",
        "Area 6d2 (PreCG)",
        "Area 6d3 (SFS)",
        "Area 6ma (preSMA, mesial SFG)",
        "Area 6mp (SMA, mesial SFG)",
        "Area 6r1 (PreCG)",
        "Area 6v1 (PreCG)",
        "Area 6v2 (PreCG)",
        "Area 6v3 (PreCG)",
    ),
    "Visual cortex V4": _group(
        "Area hOc4 group (V4)",
        "Area hOc4d (Cuneus)",
        "Area hOc4la (LOC)",
        "Area hOc4lp (LOC)",
        "Area hOc4v (LingG)",
    ),
    # v3.1 resolves the amygdaloid groups into subnuclei.
    "Amygdala centromedial group": _group(
        "CM (Amygdala)",
        "CM.AAA (Amygdala)",
        "CM.Ce (Amygdala)",
        "CM.Me (Amygdala)",
    ),
    "Amygdala laterobasal group": _group(
        "LB (Amygdala)",
        "LB.Bl (Amygdala)",
        "LB.Bm (Amygdala)",
        "LB.La (Amygdala)",
        "LB.Pl (Amygdala)",
    ),
    "Amygdala superficial group": _group(
        "SF (Amygdala)",
        "SF.AHi (Amygdala)",
        "SF.APir (Amygdala)",
        "SF.VCo (Amygdala)",
    ),
    "Hippocampus cornu ammonis": _group(
        "Cornu ammonis group (CA1–CA3)",
        "CA1 (Hippocampus)",
        "CA2 (Hippocampus)",
        "CA3 (Hippocampus)",
    ),
    # "Subc (Hippocampus, Subicular complex)" is the v3.1 parent node of these four.
    "Hippocampus subiculum": _group(
        "Subc (Hippocampus, Subicular complex)",
        "Subc.Sub (Hippocampus, Subiculum)",
        "Subc.ProS (Hippocampus, Prosubiculum)",
        "Subc.PreS (Hippocampus, Presubiculum)",
        "Subc.PaS (Hippocampus, Parasubiculum)",
    ),
}

_SINGLES = {
    "Anterior intra-parietal sulcus hIP1": "Area hIP1 (IPS)",
    "Anterior intra-parietal sulcus hIP2": "Area hIP2 (IPS)",
    "Anterior intra-parietal sulcus hIP3": "Area hIP3 (IPS)",
    "Broca's area BA44": "Area 44 (IFG)",
    "Broca's area BA45": "Area 45 (IFG)",
    "Hippocampus dentate gyrus": "DG (Hippocampus)",
    "Hippocampus entorhinal cortex": "Area EC (Hippocampal Region, Entorhinal Cortex)",
    "Hippocampus hippocampal-amygdaloid transition area": "HATA (Hippocampus)",
    "Inferior parietal lobule PF": "Area PF (IPL)",
    "Inferior parietal lobule PFcm": "Area PFcm (IPL)",
    "Inferior parietal lobule PFm": "Area PFm (IPL)",
    "Inferior parietal lobule PFop": "Area PFop (IPL)",
    "Inferior parietal lobule PFt": "Area PFt (IPL)",
    "Inferior parietal lobule PGp": "Area PGp (IPL)",
    "Inferior parietal lobule Pga": "Area PGa (IPL)",
    "Insula Id1": "Area Id1 (Insula)",
    "Insula Ig1": "Area Ig1 (Insula)",
    "Insula Ig2": "Area Ig2 (Insula)",
    "Lateral geniculate body": "CGL (Metathalamus)",
    "Medial geniculate body": "CGM (Metathalamus)",
    "Primary auditory cortex TE1.0": "Area Te 1.0 (HESCHL)",
    "Primary auditory cortex TE1.1": "Area Te 1.1 (HESCHL)",
    "Primary auditory cortex TE1.2": "Area Te 1.2 (HESCHL)",
    "Primary motor cortex BA4a": "Area 4a (PreCG)",
    "Primary motor cortex BA4p": "Area 4p (PreCG)",
    "Primary somatosensory cortex BA1": "Area 1 (PostCG)",
    "Primary somatosensory cortex BA2": "Area 2 (PostCS)",
    "Primary somatosensory cortex BA3a": "Area 3a (PostCG)",
    "Primary somatosensory cortex BA3b": "Area 3b (PostCG)",
    "Secondary somatosensory cortex / Parietal operculum OP1": "Area Op1 (POperc)",
    "Secondary somatosensory cortex / Parietal operculum OP2": "Area Op2 (POperc)",
    "Secondary somatosensory cortex / Parietal operculum OP3": "Area Op3 (POperc)",
    "Secondary somatosensory cortex / Parietal operculum OP4": "Area Op4 (POperc)",
    "Superior parietal lobule 5Ci": "Area 5Ci (SPL)",
    "Superior parietal lobule 5L": "Area 5L (SPL)",
    "Superior parietal lobule 5M": "Area 5M (SPL)",
    "Superior parietal lobule 7A": "Area 7A (SPL)",
    "Superior parietal lobule 7M": "Area 7M (SPL)",
    "Superior parietal lobule 7P": "Area 7P (SPL)",
    "Superior parietal lobule 7PC": "Area 7PC (SPL)",
    "Visual cortex V1 BA17": "Area hOc1 (V1, 17, CalcS)",
    "Visual cortex V2 BA18": "Area hOc2 (V2, 18)",
    "Visual cortex V3V": "Area hOc3v (LingG)",
    "Visual cortex V5": "Area hOc5 (LOC)",
}

V31_MAP: dict[str, V31Mapping] = {
    **{legacy: _single(name) for legacy, name in _SINGLES.items()},
    **_GROUPS,
    "Mamillary body": V31Mapping(
        name="Mamillary body",
        in_v31=False,
        note="No Julich-Brain v3.1 counterpart",
    ),
    **{legacy: V31Mapping(name=legacy, in_v31=False, note=_WM_NOTE) for legacy in _WM_LABELS},
}

V31_NAMES = tuple(spec.name for spec in V31_MAP.values() if spec.in_v31)


def relabel_to_v31(atlas: Atlas) -> Atlas:
    """Return a copy of ``atlas`` carrying Julich-Brain v3.1 names and provenance."""
    parcels = []
    for parcel in atlas.parcels:
        spec = V31_MAP.get(parcel.name)
        if spec is None:
            parcels.append(
                replace(
                    parcel,
                    in_v31=False,
                    note="No Julich-Brain v3.1 counterpart",
                )
            )
            continue
        renamed = spec.name != parcel.name
        parcels.append(
            replace(
                parcel,
                name=spec.name,
                color=parcel_color(spec.name, parcel.hemisphere),
                legacy_name=parcel.name if renamed else "",
                in_v31=spec.in_v31,
                is_group=spec.is_group,
                group_members=spec.members,
                note=spec.note,
            )
        )
    return Atlas(
        data=atlas.data,
        scale=atlas.scale,
        parcels=parcels,
        name=atlas.name,
        space=atlas.space,
        source=atlas.source,
        nomenclature=NOMENCLATURE,
    )


__all__ = [
    "NOMENCLATURE",
    "V31_MAP",
    "V31_NAMES",
    "V31_VERSION",
    "V31Mapping",
    "relabel_to_v31",
]
