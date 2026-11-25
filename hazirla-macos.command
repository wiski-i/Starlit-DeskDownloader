#!/bin/bash
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-verified.txt
if [ -z "${VIDEOINDIR_FFMPEG:-}" ]; then
    VIDEOINDIR_FFMPEG=$(.venv/bin/python -c 'from imageio_ffmpeg import get_ffmpeg_exe; print(get_ffmpeg_exe())')
fi
export VIDEOINDIR_FFMPEG
export QT_QPA_PLATFORM=offscreen
.venv/bin/python -m unittest -v
node --test tests/extension.test.mjs
.venv/bin/python build_macos.py
.venv/bin/python tests/check_packaged_host.py dist/HizliIndir.app/Contents/MacOS/HizliIndirBrowserHost
printf '\nPaket ve SHA256SUMS dist klasöründe.\n'
