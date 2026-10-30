"""Render ``AppIcon.icns`` (macOS) and ``AppIcon.ico`` (Windows) from the atlas.

The brain is the real Jülich-Brain outline, seen from a left-front three-quarter view,
with ``Area 4p (PreCG) left`` lit so the icon shows what the app does: one parcel
highlighted on a dim whole-brain shell.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

from napari_julich_surfer._atlas import fetch_juelich
from napari_julich_surfer._surfaces import SurfaceCache, _isosurface

HERE = Path(__file__).resolve().parent
SIZE = 1024
SS = 2  # supersampling factor for the drawing pass
CONTENT = 824  # Big Sur style icon square inside the 1024 canvas
RADIUS = 185

BG_TOP = np.array([13, 21, 36], dtype=np.float64)
BG_BOTTOM = np.array([31, 47, 74], dtype=np.float64)
BONE = np.array([232, 223, 205], dtype=np.float64)
ACCENT = np.array([245, 142, 74], dtype=np.float64)
GLOW = (245, 140, 70)


def _background(size: int) -> Image.Image:
    ys = np.linspace(0, 1, size)[:, None]
    ramp = BG_TOP[None, :] * (1 - ys) + BG_BOTTOM[None, :] * ys
    gradient = Image.fromarray(
        np.repeat(ramp[:, None, :], size, axis=1).astype(np.uint8)
    ).convert("RGBA")

    inset = (size - CONTENT * size // SIZE) // 2
    radius = RADIUS * size // SIZE
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [inset, inset, size - inset - 1, size - inset - 1], radius=radius, fill=255
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(gradient, (0, 0), mask)

    # Hairline inner rim keeps the icon legible on light and dark wallpapers.
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle(
        [inset, inset, size - inset - 1, size - inset - 1],
        radius=radius,
        outline=(255, 255, 255, 26),
        width=max(2, size // 512),
    )
    return Image.alpha_composite(canvas, rim)


def _basis(camera: np.ndarray):
    camera = camera / np.linalg.norm(camera)
    forward = -camera
    right = np.cross(np.array([0.0, 0.0, 1.0]), forward)
    right /= np.linalg.norm(right)
    up = np.cross(forward, right)
    up /= np.linalg.norm(up)
    light = 0.20 * right + 0.60 * up + 0.80 * camera
    light /= np.linalg.norm(light)
    return right, up, camera, light


def _face_colors(mesh, tint: np.ndarray, camera, light, ambient: float) -> np.ndarray:
    a, b, c = (mesh.vertices[mesh.faces[:, i]].astype(np.float64) for i in range(3))
    normals = np.cross(b - a, c - a)
    normals /= np.maximum(np.linalg.norm(normals, axis=1), 1e-9)[:, None]
    # Point every normal at the camera: the atlas shell has inward-facing patches
    # where a label is missing, and those should not render as black holes.
    normals *= np.where(normals @ camera < 0, -1.0, 1.0)[:, None]
    lambert = np.clip(normals @ light, 0.0, 1.0)
    shade = ambient + (1.08 - ambient) * lambert
    return np.clip(tint[None, :] * shade[:, None], 0, 255).astype(np.uint8)


def render(atlas, motor) -> Image.Image:
    size = SIZE * SS
    pixels = _background(size)
    right, up, camera, light = _basis(np.array([-0.82, 0.40, 0.28]))

    binary = ndimage.binary_fill_holes(
        ndimage.binary_closing(atlas.data > 0, iterations=2)
    )
    shell = _isosurface(binary, atlas.scale, step=2, sigma=1.4)
    if shell is None:
        raise SystemExit("could not build the atlas isosurface")

    cache = SurfaceCache(atlas)
    parcel = cache.parcel(motor.value, "Balanced")
    xs, ys = [], []
    for mesh in (shell, parcel):
        if mesh is None:
            continue
        xyz = mesh.vertices[:, [2, 1, 0]].astype(np.float64)
        xs.append(xyz @ right)
        ys.append(xyz @ up)
    xs, ys = np.concatenate(xs), np.concatenate(ys)
    target = CONTENT * size / SIZE * 0.82
    scale = target / max(xs.max() - xs.min(), ys.max() - ys.min())
    center = np.array([(xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2])
    cx, cy = size / 2, size / 2
    screen = np.stack(
        [cx + (xs - center[0]) * scale, cy - (ys - center[1]) * scale], axis=1
    )

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gw = target * 0.9
    ImageDraw.Draw(glow).ellipse(
        [cx - gw / 2, cy - gw / 2, cx + gw / 2, cy + gw / 2], fill=(*GLOW, 30)
    )
    pixels = Image.alpha_composite(
        pixels, glow.filter(ImageFilter.GaussianBlur(size * 0.045))
    )

    draw = ImageDraw.Draw(pixels)

    def draw_mesh(mesh, tint, ambient):
        if mesh is None:
            return
        xyz = mesh.vertices[:, [2, 1, 0]].astype(np.float64)
        local = np.stack(
            [cx + (xyz @ right - center[0]) * scale,
             cy - (xyz @ up - center[1]) * scale], axis=1
        )
        face_depth = (xyz @ camera)[mesh.faces].mean(axis=1)
        colors = _face_colors(mesh, tint, camera, light, ambient)
        for idx in np.argsort(face_depth):  # far to near
            poly = local[mesh.faces[idx]]
            draw.polygon(
                [(float(poly[0, 0]), float(poly[0, 1])),
                 (float(poly[1, 0]), float(poly[1, 1])),
                 (float(poly[2, 0]), float(poly[2, 1]))],
                fill=tuple(int(v) for v in colors[idx]) + (255,),
            )

    draw_mesh(shell, BONE, 0.70)
    # The shell is smoothed outward, so the cortical parcel is drawn on top instead
    # of competing with it in the depth sort.
    draw_mesh(parcel, ACCENT, 0.76)
    return pixels.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    atlas = fetch_juelich()
    motor = next(
        p for p in atlas.parcels if p.name.startswith("Area 4p") and p.hemisphere == "L"
    )
    icon = render(atlas, motor)
    icon.save(HERE / "icon-preview.png")
    icon.resize((128, 128), Image.LANCZOS).save(HERE / "icon-preview-128.png")

    # Windows wants one multi-resolution .ico; Pillow writes it on any platform.
    icon.save(
        HERE / "AppIcon.ico",
        sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)],
    )
    print(
        "wrote",
        HERE / "AppIcon.ico",
        (HERE / "AppIcon.ico").stat().st_size,
        "bytes",
    )

    if sys.platform != "darwin":
        return  # iconutil ships with macOS only; the .ico above is enough here.

    iconset = HERE / "AppIcon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir()
    for base in (16, 32, 128, 256, 512):
        icon.resize((base, base), Image.LANCZOS).save(iconset / f"icon_{base}x{base}.png")
        icon.resize((base * 2, base * 2), Image.LANCZOS).save(
            iconset / f"icon_{base}x{base}@2x.png"
        )
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "AppIcon.icns")],
        check=True,
    )
    print("wrote", HERE / "AppIcon.icns", (HERE / "AppIcon.icns").stat().st_size, "bytes")


if __name__ == "__main__":
    main()
