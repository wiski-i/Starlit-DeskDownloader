"""Build the native-architecture macOS application and unsigned DMG."""
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def artifact_name(version: str, machine: str) -> str:
    architectures = {"arm64": "arm64", "x86_64": "x64"}
    if machine not in architectures:
        raise ValueError(f"Unsupported macOS architecture: {machine}")
    return f"Starlit-DeskDownloader-{version}-macos-{architectures[machine]}.dmg"


def main() -> None:
    if sys.platform != "darwin":
        raise SystemExit("build_macos.py must run on macOS; each architecture needs its own Mac runner.")
    root = Path(__file__).resolve().parent
    os.chdir(root)
    build = root / "build"
    dist = root / "dist"
    build.mkdir(exist_ok=True)
    dist.mkdir(exist_ok=True)
    version = (root / "version.txt").read_text(encoding="utf-8-sig").strip()
    output = dist / artifact_name(version, platform.machine())

    from imageio_ffmpeg import get_ffmpeg_exe
    from third_party import write_notice

    source = os.environ.get("VIDEOINDIR_FFMPEG") or get_ffmpeg_exe()
    if not source:
        raise SystemExit("Install requirements-verified.txt or set VIDEOINDIR_FFMPEG.")
    ffmpeg = build / "ffmpeg"
    if Path(source).resolve() != ffmpeg.resolve():
        shutil.copy2(source, ffmpeg)
    ffmpeg.chmod(0o755)
    write_notice(ffmpeg, build / "THIRD-PARTY.txt", Path(source))

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from theme import mark_pixmap

    application = QApplication([])
    iconset = build / "HizliIndir.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            suffix = "@2x" if scale == 2 else ""
            path = iconset / f"icon_{size}x{size}{suffix}.png"
            if not mark_pixmap(size * scale).save(str(path), "PNG"):
                raise RuntimeError(f"Could not create icon: {path}")
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(build / "HizliIndir.icns")], check=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--workpath", "build/pyinstaller", "--distpath", "dist", "HizliIndir.spec",
    ], check=True)
    app = dist / "HizliIndir.app"
    for name in ("HizliIndir", "HizliIndirBrowserHost"):
        if not (app / "Contents" / "MacOS" / name).is_file():
            raise RuntimeError(f"Missing bundled executable: {name}")

    # PyInstaller rewrites Mach-O signatures; identify the actual shipped binary.
    bundled_ffmpeg = app / "Contents" / "Frameworks" / "tools" / "ffmpeg"
    bundled_notice = app / "Contents" / "Resources" / "THIRD-PARTY.txt"
    write_notice(bundled_ffmpeg, bundled_notice, Path(source))
    # Re-seal resources only; keep nested binary signatures and their hashes intact.
    subprocess.run(["codesign", "--force", "--sign", "-", str(app)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)

    # Stage a disposable copy of the finalized application.
    stage = build / "dmg-stage"
    if stage.resolve().parent != build.resolve():
        raise RuntimeError("DMG staging path escapes the build directory.")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    subprocess.run(["ditto", str(app), str(stage / app.name)], check=True)
    (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
    for name in ("register-browser-macos.command", "LICENSE", "ONCE-BENI-OKU.txt"):
        shutil.copy2(root / name, stage / name)
    (stage / "register-browser-macos.command").chmod(0o755)
    shutil.copy2(bundled_notice, stage / "THIRD-PARTY.txt")
    output.unlink(missing_ok=True)
    subprocess.run([
        "hdiutil", "create", "-volname", "Hızlı İndir", "-srcfolder", str(stage),
        "-ov", "-format", "UDZO", str(output),
    ], check=True)
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (dist / "SHA256SUMS").write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
