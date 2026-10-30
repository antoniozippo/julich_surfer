"""Entry point for the frozen Windows executable.

Same shape as ``macos_launcher.py``: a windowed build has no console, so crashes
and stray prints go to a log file, and napari is imported directly instead of
relying on plugin discovery.
"""

from __future__ import annotations

import multiprocessing
import os
import sys
import traceback
from pathlib import Path

APP_ID = "org.julichbrainsurfer.app"


def _log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) / "JulichBrainSurfer" if base else Path.home() / ".julich-surfer"
    return root / "JulichBrainSurfer.log"


LOG_PATH = _log_path()


def _log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except OSError:
        pass


def _install_crash_log() -> None:
    """A windowed .exe has nowhere to print, so route failures to the log."""

    def hook(exc_type, exc, tb):
        _log("".join(traceback.format_exception(exc_type, exc, tb)))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook


def _redirect_streams() -> None:
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stream = LOG_PATH.open("a", encoding="utf-8", buffering=1)
    except OSError:
        return
    sys.stdout = sys.stdout or stream
    sys.stderr = sys.stderr or stream


def _set_app_user_model_id() -> None:
    """Show the app icon in the taskbar instead of the generic interpreter one."""
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:  # noqa: BLE001 - cosmetic only, and absent off Windows
        pass


def main() -> None:
    multiprocessing.freeze_support()
    _install_crash_log()
    _redirect_streams()
    _set_app_user_model_id()
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
