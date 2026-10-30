"""A 3-D brain surfer for the Jülich-Brain atlas, built on napari."""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = [
    "Atlas",
    "JulichSurferWidget",
    "atlas_from_nifti",
    "fetch_juelich",
    "__version__",
]


def __getattr__(name: str):
    # Keep Qt out of import time so `npe2` can read the manifest without a GUI.
    if name == "JulichSurferWidget":
        from ._widget import JulichSurferWidget

        return JulichSurferWidget
    if name in ("Atlas", "atlas_from_nifti", "fetch_juelich"):
        from . import _atlas

        return getattr(_atlas, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
