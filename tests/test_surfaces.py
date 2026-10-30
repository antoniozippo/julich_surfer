import numpy as np

from napari_julich_surfer._atlas import atlas_from_labels
from napari_julich_surfer._surfaces import SurfaceCache, _isosurface


def _sphere_atlas(radius=8, center=(20, 20, 20), scale=(1.0, 1.0, 1.0)):
    grid = np.indices((40, 40, 40))
    data = np.zeros((40, 40, 40), np.int16)
    distance = sum((grid[axis] - center[axis]) ** 2 for axis in range(3))
    data[distance <= radius**2] = 1
    return atlas_from_labels(data, scale, {1: "GM Test ball"}, split_hemispheres=False)


def test_sphere_mesh_has_expected_radius():
    atlas = _sphere_atlas(radius=8, center=(20, 20, 20))
    mesh = SurfaceCache(atlas).parcel(1, "Fine")
    assert mesh is not None
    radii = np.linalg.norm(mesh.vertices - np.array([20.0, 20.0, 20.0]), axis=1)
    assert 7.5 < radii.mean() < 10.0
    assert mesh.faces.shape[1] == 3
    assert len(mesh.faces) > 100


def test_vertices_are_in_millimetres_and_offsets_are_applied():
    atlas = _sphere_atlas(radius=6, center=(12, 30, 25), scale=(2.0, 2.0, 2.0))
    mesh = SurfaceCache(atlas).parcel(1, "Fine")
    # Coordinates are (z, y, x) = index * scale, so the ball centre maps x2.
    center = np.array([12.0, 30.0, 25.0]) * 2.0
    assert np.allclose(mesh.vertices.mean(axis=0), center, atol=3.0)
    assert mesh.vertices[:, 2].min() > (25 - 8) * 2.0
    assert mesh.vertices[:, 2].max() < (25 + 8) * 2.0


def test_cache_is_memoised_and_per_detail():
    cache = SurfaceCache(_sphere_atlas())
    first = cache.parcel(1, "Balanced")
    assert cache.parcel(1, "Balanced") is first
    coarse = cache.parcel(1, "Fast")
    fine = cache.parcel(1, "Fine")
    assert len(coarse.faces) < len(fine.faces)
    cache.clear()
    assert cache.parcel(1, "Balanced") is not first


def test_detail_presets_keep_the_same_extent():
    atlas = _sphere_atlas(radius=10)
    cache = SurfaceCache(atlas)
    coarse, fine = cache.parcel(1, "Fast"), cache.parcel(1, "Fine")
    assert np.allclose(coarse.vertices.min(axis=0), fine.vertices.min(axis=0), atol=3.0)
    assert np.allclose(coarse.vertices.max(axis=0), fine.vertices.max(axis=0), atol=3.0)


def test_outline_covers_the_whole_atlas():
    atlas = _sphere_atlas()
    outline = SurfaceCache(atlas).outline()
    assert outline is not None
    assert len(outline.vertices) > 0


def test_tiny_region_still_produces_a_mesh():
    data = np.zeros((12, 12, 12), np.int16)
    data[5, 5, 5] = 1  # a single voxel is below marching-cubes resolution
    atlas = atlas_from_labels(data, (1, 1, 1), {1: "GM Dot"}, split_hemispheres=False)
    mesh = SurfaceCache(atlas).parcel(1, "Fine")
    assert mesh is not None
    assert len(mesh.vertices) > 0


def test_empty_mask_returns_none():
    assert _isosurface(np.zeros((5, 5, 5), bool), (1, 1, 1)) is None
