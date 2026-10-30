"""Launch the surfer in a standalone napari window: ``python -m napari_julich_surfer``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ._atlas import ATLAS_CHOICES, DEFAULT_ATLAS_NAME, atlas_from_nifti, fetch_juelich


def _load_names(path: str):
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [line.strip() for line in text.splitlines() if line.strip()]
    if isinstance(data, dict):
        return {int(key): str(value) for key, value in data.items()}
    return [str(value) for value in data]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="julich-surfer",
        description="3-D brain surfer for the Jülich-Brain atlas (napari).",
    )
    parser.add_argument(
        "--atlas",
        default=DEFAULT_ATLAS_NAME,
        choices=ATLAS_CHOICES,
        help="nilearn/FSL Jülich atlas variant (default: %(default)s)",
    )
    parser.add_argument(
        "--nifti",
        help="use your own maximum-probability map instead (e.g. the EBRAINS "
        "Jülich-Brain v3 export) instead of downloading the FSL edition",
    )
    parser.add_argument(
        "--labels",
        help="JSON object {label value: name} or a text file with one name per line, "
        "used together with --nifti",
    )
    parser.add_argument(
        "--keep-sides-together",
        action="store_true",
        help="list each region once instead of as separate left/right parcels",
    )
    parser.add_argument(
        "--legacy-names",
        action="store_true",
        help="keep the old FSL/Anatomy-Toolbox labels instead of Julich-Brain v3.1 names",
    )
    parser.add_argument(
        "--2d",
        dest="three_d",
        action="store_false",
        help="start in the 2-D slice view instead of 3-D",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    split = not args.keep_sides_together
    if args.nifti:
        names = _load_names(args.labels) if args.labels else None
        atlas = atlas_from_nifti(args.nifti, names, split_hemispheres=split)
    else:
        atlas = fetch_juelich(
            args.atlas, split_hemispheres=split, v31_names=not args.legacy_names
        )

    import napari

    from ._widget import JulichSurferWidget

    viewer = napari.Viewer(title="Jülich 3D Brain Surfer")
    widget = JulichSurferWidget(viewer, atlas=atlas)
    viewer.window.add_dock_widget(widget, name="Jülich parcels", area="right")
    if not args.three_d:
        viewer.dims.ndisplay = 2
    napari.run()


if __name__ == "__main__":
    main()
