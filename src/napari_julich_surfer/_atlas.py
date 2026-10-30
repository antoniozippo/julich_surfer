"""Atlas loading and parcel bookkeeping for the Jülich-Brain (Juelich) atlas.

The atlas used by default is the Jülich histological atlas as packaged by FSL and
distributed through :func:`nilearn.datasets.fetch_atlas_juelich` (cytoarchitectonic
areas from Amunts, Zilles and colleagues, mapped to MNI152 at 1 mm).  The FSL edition
is *symmetric*: each region carries a single label id covering both hemispheres.  We
therefore split grey-matter regions at the midsagittal plane into explicit left and
right parcels, which is what you want when highlighting one side of the brain.

Volumes are re-oriented once into display order ``(z, y, x)`` (superior, anterior,
right) so that napari's vertical axis is up and the layer coordinates are millimetres
in a right-handed anatomical frame.
"""

from __future__ import annotations

import colorsys
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

# Atlas variants exposed by nilearn's FSL packaging.  Thresholded maximum-probability
# maps look best as surfaces; thr25 is the usual FSL default.
DEFAULT_ATLAS_NAME = "maxprob-thr25-1mm"
ATLAS_CHOICES = (
    "maxprob-thr25-1mm",
    "maxprob-thr25-2mm",
    "maxprob-thr0-1mm",
    "maxprob-thr0-2mm",
    "maxprob-thr50-1mm",
    "maxprob-thr50-2mm",
)

ATLAS_NAME = "Jülich histological atlas"
ATLAS_SPACE = "MNI152 1 mm"

TISSUE_NAMES = {"GM": "Grey matter", "WM": "White matter"}
SIDE_NAMES = {"L": "left", "R": "right"}

_DIM_RGBA = (0.56, 0.58, 0.63, 0.32)


@dataclass(frozen=True)
class Parcel:
    """One selectable atlas region (a label value plus its metadata)."""

    value: int
    name: str
    hemisphere: str  # "L", "R" or "" for midline / bilateral structures
    tissue: str  # "GM", "WM" or ""
    n_voxels: int
    volume_mm3: float
    centroid: tuple[float, float, float]  # mm in display order (z, y, x)
    color: tuple[float, float, float, float]  # RGBA
    bbox: tuple[slice, slice, slice] = field(compare=False, repr=False)
    legacy_name: str = ""  # previous (FSL) name when the atlas was relabelled
    in_v31: bool = True  # False for FSL-only labels with no Julich-Brain v3.1 term
    is_group: bool = False  # the legacy parcel covers several v3.1 areas
    group_members: tuple[str, ...] = ()
    note: str = ""

    @property
    def label(self) -> str:
        """Display name in Julich-Brain style, e.g. ``Area 4p (PreCG) left``."""
        side = SIDE_NAMES.get(self.hemisphere)
        return f"{self.name} {side}" if side else self.name

    @property
    def list_label(self) -> str:
        """Label for the parcel list, flagging groups and FSL-only regions."""
        if self.is_group:
            return f"{self.label} · {len(self.group_members)} areas"
        if not self.in_v31:
            return f"{self.label} · not in v3.1"
        return self.label

    @property
    def group_member_labels(self) -> tuple[str, ...]:
        """Short forms of :attr:`group_members`, e.g. ``("6d1", "6d2", ...)``."""
        short = []
        for member in self.group_members:
            base = member.split(" (")[0]
            short.append(base[len("Area ") :] if base.startswith("Area ") else base)
        return tuple(short)

    @property
    def tissue_label(self) -> str:
        return TISSUE_NAMES.get(self.tissue, "Region")


@dataclass
class Atlas:
    """A labelled volume in display order plus the list of selectable parcels."""

    data: np.ndarray
    scale: tuple[float, float, float]
    parcels: list[Parcel]
    name: str = ATLAS_NAME
    space: str = ATLAS_SPACE
    source: str = ""
    nomenclature: str = ""
    _by_value: dict[int, Parcel] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        self._by_value = {p.value: p for p in self.parcels}

    @property
    def by_value(self) -> dict[int, Parcel]:
        return self._by_value

    def parcel(self, value: int) -> Parcel:
        return self._by_value[int(value)]

    @property
    def dim_color(self) -> tuple[float, float, float, float]:
        return _DIM_RGBA


# --------------------------------------------------------------------------------------
# colours
# --------------------------------------------------------------------------------------
def parcel_color(name: str, hemisphere: str) -> tuple[float, float, float, float]:
    """Deterministic colour per region: stable across sessions, readable, side-aware."""
    digest = hashlib.md5(name.lower().encode("utf-8")).digest()
    hue = (int.from_bytes(digest[:4], "big") / 2**32 * 0.6180339887498949) % 1.0
    value = {"R": 0.95, "L": 0.72}.get(hemisphere, 0.86)
    red, green, blue = colorsys.hsv_to_rgb(hue, 0.72, value)
    return (round(red, 4), round(green, 4), round(blue, 4), 1.0)


def split_tissue_prefix(raw: str) -> tuple[str, str]:
    """``"GM Primary motor cortex BA4p"`` -> ``("GM", "Primary motor cortex BA4p")``."""
    text = str(raw).strip()
    tissue = ""
    if text[:2].upper() in TISSUE_NAMES and (len(text) == 2 or text[2] in " _-:"):
        tissue = text[:2].upper()
        text = text[2:].lstrip(" _-:")
    return tissue, text.replace("_", " ").strip()


# --------------------------------------------------------------------------------------
# building an atlas from a labelled array
# --------------------------------------------------------------------------------------
def atlas_from_labels(
    data: np.ndarray,
    scale: Sequence[float],
    names: Mapping[int, str] | Sequence[str] | None,
    *,
    midline_x: float | None = None,
    split_hemispheres: bool = True,
    split_white_matter: bool = False,
    name: str = ATLAS_NAME,
    space: str = ATLAS_SPACE,
    source: str = "",
) -> Atlas:
    """Build an :class:`Atlas` from a 3-D label volume in display order ``(z, y, x)``.

    Parameters
    ----------
    data
        Integer label volume, ``0`` meaning "no parcel".
    scale
        Millimetres per voxel along ``(z, y, x)``.
    names
        Label value -> region name mapping, or a sequence of names indexed from
        ``0`` or ``1`` (a leading ``"Background"`` is tolerated).
    midline_x
        Index (float, along the last array axis) of the midsagittal plane.  When
        given, grey-matter regions touching both sides are split into two parcels.
    """
    volume = np.asanyarray(data)
    if volume.ndim != 3:
        raise ValueError(f"expected a 3-D label volume, got shape {volume.shape}")
    scale = tuple(float(s) for s in scale)
    if len(scale) != 3:
        raise ValueError("scale must have three entries (z, y, x)")
    if midline_x is not None and not 0 <= float(midline_x) <= volume.shape[2]:
        midline_x = None

    table = _name_table(names)
    present = np.unique(volume)
    present = present[present != 0]
    voxel_volume = float(np.prod(scale))

    # Per-label bounding boxes make every following step cheap and cropped.
    objects = ndimage.find_objects(volume.astype(np.int32, copy=False))

    out = np.zeros(volume.shape, dtype=np.int16)
    parcels: list[Parcel] = []

    for raw_value in present:
        value = int(raw_value)
        raw_name = table.get(value, f"Region {value}")
        tissue, base_name = split_tissue_prefix(raw_name)
        if not base_name:
            base_name = f"Region {value}"
        if value - 1 >= len(objects) or objects[value - 1] is None:
            continue
        sl = objects[value - 1]
        crop = volume[sl]
        mask = crop == raw_value

        sides: list[tuple[str, np.ndarray | None]] = [("", None)]
        if (
            split_hemispheres
            and midline_x is not None
            and (tissue != "WM" or split_white_matter)
        ):
            xs = np.arange(sl[2].start, sl[2].stop)
            right = xs >= float(midline_x)
            left = ~right
            if mask[:, :, right].any() and mask[:, :, left].any():
                sides = [("L", left), ("R", right)]

        for hemisphere, selector in sides:
            sub = mask if selector is None else mask & selector[np.newaxis, np.newaxis, :]
            count = int(sub.sum())
            if count == 0:
                continue
            new_value = len(parcels) + 1
            target = out[sl]
            target[sub] = new_value

            indices = np.nonzero(sub)
            bbox = tuple(
                slice(int(indices[axis].min()) + sl[axis].start,
                      int(indices[axis].max()) + 1 + sl[axis].start)
                for axis in range(3)
            )
            # +0.5 puts the centroid at the centre of a voxel, matching surface coords.
            centroid = tuple(
                float((indices[axis].mean() + sl[axis].start + 0.5) * scale[axis])
                for axis in range(3)
            )
            parcels.append(
                Parcel(
                    value=new_value,
                    name=base_name,
                    hemisphere=hemisphere,
                    tissue=tissue,
                    n_voxels=count,
                    volume_mm3=count * voxel_volume,
                    centroid=centroid,
                    color=parcel_color(base_name, hemisphere),
                    bbox=bbox,
                )
            )

    if not parcels:
        raise ValueError("no labelled voxels found in the volume")

    return Atlas(
        data=out,
        scale=scale,
        parcels=parcels,
        name=name,
        space=space,
        source=source,
    )


def _name_table(names: Mapping[int, str] | Sequence[str] | None) -> dict[int, str]:
    if names is None:
        return {}
    if isinstance(names, Mapping):
        table = {int(k): str(v) for k, v in names.items()}
    else:
        labels = [str(n) for n in names]
        # nilearn now includes "Background" as the first entry (so value == index),
        # older versions did not (so value == index + 1).
        offset = 0 if labels and labels[0].strip().lower() == "background" else 1
        table = {index + offset: label for index, label in enumerate(labels)}
    return {
        value: label
        for value, label in table.items()
        if str(label).strip().lower() not in ("", "background")
    }


# --------------------------------------------------------------------------------------
# loading from NIfTI / nilearn
# --------------------------------------------------------------------------------------
def atlas_from_nifti(
    path: str,
    names: Mapping[int, str] | Sequence[str] | None = None,
    *,
    split_hemispheres: bool = True,
    split_white_matter: bool = False,
    name: str | None = None,
    space: str = "MNI152",
) -> Atlas:
    """Load any Jülich-Brain maximum-probability map (e.g. the EBRAINS v3.0 export)."""
    import nibabel as nib

    image = nib.load(str(path))
    return _atlas_from_image(
        image,
        names,
        split_hemispheres=split_hemispheres,
        split_white_matter=split_white_matter,
        name=name or str(path),
        space=space,
        source=str(path),
    )


def fetch_juelich(
    atlas_name: str = DEFAULT_ATLAS_NAME,
    *,
    data_dir: str | None = None,
    split_hemispheres: bool = True,
    split_white_matter: bool = False,
    v31_names: bool = True,
) -> Atlas:
    """Download (once, via nilearn) and return the Jülich atlas in display order.

    With ``v31_names`` (the default) regions are renamed to their Julich-Brain v3.1
    strings and legacy-only labels are flagged; see :mod:`._nomenclature`.
    """
    from nilearn.datasets import fetch_atlas_juelich

    fetched = fetch_atlas_juelich(atlas_name=atlas_name, data_dir=data_dir, verbose=0)
    if isinstance(fetched, Mapping):
        image = fetched["maps"]
        names = fetched.get("labels")
        lut = fetched.get("lut")
    else:  # pragma: no cover - older nilearn returned plain dicts
        image = fetched.maps
        names = getattr(fetched, "labels", None)
        lut = getattr(fetched, "lut", None)

    table = _names_from_lut(lut) or names
    atlas = _atlas_from_image(
        image,
        table,
        split_hemispheres=split_hemispheres,
        split_white_matter=split_white_matter,
        source=f"nilearn/FSL Juelich {atlas_name}",
        space="MNI152 1 mm" if atlas_name.endswith("1mm") else "MNI152 2 mm",
    )
    if v31_names:
        from ._nomenclature import relabel_to_v31

        atlas = relabel_to_v31(atlas)
    return atlas


def _names_from_lut(lut) -> dict[int, str]:
    if lut is None:
        return {}
    try:
        return {int(i): str(n) for i, n in zip(lut["index"], lut["name"])}
    except Exception:  # noqa: BLE001 - a missing/renamed column is not fatal
        return {}


def _atlas_from_image(
    image,
    names,
    *,
    split_hemispheres: bool,
    split_white_matter: bool,
    name: str = ATLAS_NAME,
    space: str = ATLAS_SPACE,
    source: str = "",
) -> Atlas:
    import nibabel as nib

    canonical = nib.as_closest_canonical(image)
    affine = canonical.affine
    data = np.asanyarray(canonical.dataobj)
    if data.ndim != 3:
        raise ValueError("the atlas image must be a 3-D label volume")
    zooms = tuple(abs(float(z)) for z in canonical.header.get_zooms()[:3])

    # Midsagittal plane, expressed as an index along the first array axis.  After
    # canonical re-orientation axis 0 is +x (right), so this is a clean L/R split.
    midline_i = float(-affine[0, 3] / affine[0, 0]) if affine[0, 0] else None

    display = np.ascontiguousarray(np.transpose(data, (2, 1, 0)))
    scale = (zooms[2], zooms[1], zooms[0])
    return atlas_from_labels(
        display,
        scale,
        names,
        midline_x=midline_i if split_hemispheres else None,
        split_hemispheres=split_hemispheres,
        split_white_matter=split_white_matter,
        name=name,
        space=space,
        source=source,
    )


__all__ = [
    "ATLAS_CHOICES",
    "ATLAS_NAME",
    "ATLAS_SPACE",
    "DEFAULT_ATLAS_NAME",
    "Atlas",
    "Parcel",
    "atlas_from_labels",
    "atlas_from_nifti",
    "fetch_juelich",
    "parcel_color",
    "split_tissue_prefix",
]
