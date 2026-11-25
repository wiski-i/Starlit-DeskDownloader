"""Record the exact FFmpeg binary included in a distributable."""
import hashlib
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys


def write_notice(binary: Path, destination: Path, source: Path | None = None) -> None:
    result = subprocess.run(
        [str(binary), "-version"], check=True, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30,
    )
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    import imageio_ffmpeg
    imageio_binaries = Path(imageio_ffmpeg.__file__).resolve().parent / "binaries"
    provider = source.resolve() if source is not None else binary.resolve()
    if provider.is_relative_to(imageio_binaries):
        distribution = (
            "Binary distribution: https://github.com/imageio/imageio-ffmpeg\n"
            f"Upstream binaries/source providers: https://github.com/imageio/imageio-ffmpeg/blob/v{version('imageio-ffmpeg')}/tools/ffmpeg-sources.json\n"
            f"FFmpeg binary selection: https://github.com/imageio/imageio-ffmpeg/blob/v{version('imageio-ffmpeg')}/tools/download_ffmpeg.py\n"
        )
    else:
        distribution = (
            "Binary distribution: user-supplied FFmpeg (not supplied by imageio-ffmpeg).\n"
            "Obtain the exact source and build recipes from the binary provider.\n"
        )
    destination.write_text(
        "Starlit DeskDownloader - third-party software\n\n"
        "PySide6 / Qt: https://www.qt.io/licensing/\n"
        "PySide6 source: https://code.qt.io/pyside/pyside-setup.git/\n"
        "yt-dlp: https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE\n"
        "PyInstaller bootloader: https://pyinstaller.org/en/stable/license.html\n\n"
        f"FFmpeg binary: {binary.name}\nSHA-256: {digest}\n"
        f"imageio-ffmpeg: {version('imageio-ffmpeg')}\n"
        + distribution + "FFmpeg source: https://ffmpeg.org/download.html\n"
        "FFmpeg licensing: https://ffmpeg.org/legal.html\n"
        "The configuration and license of this particular binary follow below.\n"
        "This notice is an inventory; review applicable redistribution obligations before publication.\n\n"
        + result.stdout + result.stderr,
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_notice(
        Path(sys.argv[1]).resolve(strict=True), Path(sys.argv[2]),
        Path(sys.argv[3]) if len(sys.argv) > 3 else None,
    )
