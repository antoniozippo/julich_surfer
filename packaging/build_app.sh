#!/usr/bin/env bash
# Build dist/Julich 3D Brain Surfer.app (macOS, onedir, unsigned).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/pyinstaller ]; then
  echo "Missing build tools: run 'uv sync --extra qt --extra macos' first." >&2
  exit 1
fi

if [ ! -f packaging/AppIcon.icns ] || [ packaging/make_icon.py -nt packaging/AppIcon.icns ]; then
  .venv/bin/python packaging/make_icon.py
fi

.venv/bin/pyinstaller --noconfirm packaging/napari_julich_surfer.spec

echo
echo "Built: $(pwd)/dist/Julich 3D Brain Surfer.app"
echo "Run:   open 'dist/Julich 3D Brain Surfer.app'"
