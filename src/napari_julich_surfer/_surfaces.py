"""Turn atlas parcels into triangle meshes that napari can render in 3-D."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from skimage import measure

from ._atlas import Atlas

# Name -> (marching-cubes step size in voxels, gaussian pre-smoothing in voxels).
# Step size sets speed and triangle count; smoothing removes the voxel staircase.
DETAIL_PRESETS: dict[str, tuple[int, float]] = {
    "Fast": (3, 1.5),
    "Balanced": (2, 1.0),
    "Fine": (1, 0.8),
}
DEFAULT_DETAIL = "Balanced"


@dataclass(frozen=True)
class Mesh:
    """Vertices in millimetres (display order z, y, x) plus triangle indices."""

    vertices: np.ndarray
    faces: np.ndarray

    def __len__(self) -> int:
        return len(self.vertices)


class SurfaceCache:
    """Mesh extraction with memoisation; a half-second region is only built once."""

    def __init__(self, atlas: Atlas):
        self.atlas = atlas
        self._meshes: dict[tuple, Mesh | None] = {}

    def parcel(self, value: int, detail: str = DEFAULT_DETAIL) -> Mesh | None:
        key = ("parcel", int(value), detail)
        if key not in self._meshes:
            step, sigma = DETAIL_PRESETS.get(detail, DETAIL_PRESETS[DEFAULT_DETAIL])
            parcel = self.atlas.parcel(int(value))
            pad = int(np.ceil(3 * sigma)) + 1
            sl = _pad_slices(parcel.bbox, pad, self.atlas.data.shape)
            binary = self.atlas.data[sl] == parcel.value
            self._meshes[key] = _isosurface(
                binary,
                self.atlas.scale,
                origin=(sl[0].start, sl[1].start, sl[2].start),
                step=step,
                sigma=sigma,
            )
        return self._meshes[key]

    def outline(self, detail: str = "Fast") -> Mesh | None:
        """A dim whole-atlas shell, useful as a spatial reference in 3-D."""
        key = ("outline", detail)
        if key not in self._meshes:
            step, sigma = DETAIL_PRESETS.get(detail, DETAIL_PRESETS["Fast"])
            binary = self.atlas.data > 0
            self._meshes[key] = _isosurface(
                binary, self.atlas.scale, step=step, sigma=max(sigma, 1.4)
            )
        return self._meshes[key]

    def clear(self) -> None:
        self._meshes.clear()


def _pad_slices(
    bbox: Sequence[slice], pad: int, shape: Sequence[int]
) -> tuple[slice, slice, slice]:
    return tuple(
        slice(max(0, sl.start - pad), min(int(size), sl.stop + pad))
        for sl, size in zip(bbox, shape)
    )


def _isosurface(
    binary: np.ndarray,
    scale: Sequence[float],
    *,
    origin: Sequence[float] = (0.0, 0.0, 0.0),
    step: int = 1,
    sigma: float = 1.0,
) -> Mesh | None:
    """Marching cubes at the 0.5 level of a (optionally smoothed) binary mask."""
    if not binary.any():
        return None

    volume = binary.astype(np.float32)
    if sigma > 0:
        smoothed = ndimage.gaussian_filter(volume, sigma, mode="constant", truncate=2.5)
        # Smoothing erases features smaller than the kernel; keep those blocky rather
        # than letting them disappear from the navigator.
        if smoothed.max() > 0.5 + 1e-3:
            volume = smoothed

    # marching_cubes needs at least two samples per axis; pad degenerate crops.
    deficiency = [(0, max(0, 2 - size)) for size in volume.shape]
    if any(pad[1] for pad in deficiency):
        volume = np.pad(volume, deficiency, mode="constant")

    vertices, faces, _normals, _values = measure.marching_cubes(
        volume,
        level=0.5,
        spacing=tuple(float(s) for s in scale),
        step_size=int(step),
        allow_degenerate=False,
    )
    if len(vertices) == 0 or len(faces) == 0:
        return None

    offset = np.asarray(origin, dtype=np.float64) * np.asarray(scale, dtype=np.float64)
    vertices = vertices + offset
    return Mesh(vertices.astype(np.float32), faces.astype(np.int32))


__all__ = ["DEFAULT_DETAIL", "DETAIL_PRESETS", "Mesh", "SurfaceCache"]
