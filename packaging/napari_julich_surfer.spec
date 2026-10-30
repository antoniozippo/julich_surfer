# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the double-clickable macOS app."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent  # SPECPATH is this file's directory
SRC = ROOT / "src"
APP_NAME = "Julich 3D Brain Surfer"

# napari, vispy and skimage load stylesheets, icons and GLSL shaders at runtime.
datas = []
for package in (
    "napari",
    "vispy",
    "skimage",
    "nilearn",
    "nibabel",
    "superqt",
    "magicgui",
    "napari_resources",
    "napari_builtins",
    "napari_svg",
    "napari_julich_surfer",
):
    datas += collect_data_files(package)

# Entry-point metadata keeps npe2 (and therefore napari's plugin state) sane.
for distribution in (
    "napari",
    "napari-julich-surfer",
    "npe2",
    "napari_builtins",
    "napari_svg",
):
    try:
        datas += copy_metadata(distribution)
    except Exception:  # noqa: BLE001 - metadata is optional at runtime
        pass

# napari resolves much of its API through lazy_loader, so its submodules are
# evidence to static analysis only. Tests are skipped to avoid pulling in pytest.
hiddenimports = collect_submodules("napari", filter=lambda name: ".tests" not in name)
hiddenimports += collect_submodules("napari_builtins")
hiddenimports += collect_submodules("napari_svg")
hiddenimports += [
    # vispy picks its Qt backend with importlib, invisible to static analysis.
    "vispy.app.backends._pyqt6",
    "vispy.app.backends._pyside6",
    "napari_julich_surfer._widget",
    "napari_julich_surfer._nomenclature",
]

excludes = [
    "tkinter",
    "matplotlib",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "PyQt5",
    "PySide2",
    "torch",
    "tensorflow",
]

a = Analysis(
    [str(ROOT / "packaging" / "macos_launcher.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=str(ROOT / "packaging" / "AppIcon.icns"),
    bundle_identifier="org.julichbrainsurfer.app",
    info_plist={
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": "Jülich 3D Brain Surfer",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "CFBundlePackageType": "APPL",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        "LSApplicationCategoryType": "public.app-category.education",
        "NSHumanReadableCopyright": "Atlas: Amunts, Zilles et al. (Julich-Brain). "
        "Code: BSD-3-Clause.",
        "CFBundleGetInfoHTML": "<html><body><p>Jülich-Brain 3-D parcellation "
        "navigator built on napari.</p></body></html>",
    },
    target_arch=None,
)
