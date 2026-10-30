"""Entry point for the frozen macOS app bundle.

The bundle imports the widget directly instead of going through napari's plugin
discovery, so it works without npe2 seeing installed distributions.
"""

from __future__ import annotations

import multiprocessing
import sys
import traceback
from pathlib import Path

LOG_PATH = Path.home() / "Library" / "Logs" / "JulichBrainSurfer.log"


def _log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except OSError:
        pass


def _install_crash_log() -> None:
    """GUI apps have nowhere to print, so route failures to a log file."""

    def hook(exc_type, exc, tb):
        _log("".join(traceback.format_exception(exc_type, exc, tb)))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook


def _redirect_streams() -> None:
    # Launched from Finder, a windowed bundle has no stdout/stderr.
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stream = LOG_PATH.open("a", encoding="utf-8", buffering=1)
    except OSError:
        return
    sys.stdout = sys.stdout or stream
    sys.stderr = sys.stderr or stream


def main() -> None:
    # Finder used to append a process serial number, which argparse would reject.
    sys.argv = [arg for arg in sys.argv if not arg.startswith("-psn_")]
    multiprocessing.freeze_support()
    _install_crash_log()
    _redirect_streams()
    _log(f"--- launching {Path(sys.executable).name}")

    from napari_julich_surfer.__main__ import main as cli

    try:
        cli()
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 - log anything that kills the window
        _log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
