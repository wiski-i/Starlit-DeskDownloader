from importlib.util import find_spec
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all


project = Path(SPECPATH)
is_mac = sys.platform == "darwin"
is_windows = sys.platform == "win32"
ffmpeg = "ffmpeg.exe" if is_windows else "ffmpeg"
icon = str(project / "build" / ("HizliIndir.icns" if is_mac else "HizliIndir.ico")) if is_mac or is_windows else None
names = ["copy_tr.json", "LICENSE"]
if is_windows:
    names.append("browser_address.ps1")
data_files = [(str(project / name), ".") for name in names]
data_files.append((str(project / "build" / "THIRD-PARTY.txt"), "."))
data_files.append((str(project / "browser_extension"), "browser_extension"))
binary_files = [(str(project / "build" / ffmpeg), "tools")]
hidden_imports = ["native_host"]

packages = ["yt_dlp"]
if find_spec("yt_dlp_ejs") is not None:
    packages.append("yt_dlp_ejs")
for package in packages:
    data, binaries, imports = collect_all(
        package,
        include_py_files=False,
        filter_submodules=lambda name: not name.startswith("yt_dlp.__pyinstaller"),
    )
    data_files.extend(data)
    binary_files.extend(binaries)
    hidden_imports.extend(imports)

analysis = Analysis(
    [str(project / "app.py")],
    datas=data_files,
    binaries=binary_files,
    hiddenimports=hidden_imports,
    excludes=["imageio_ffmpeg"],
)
host_analysis = Analysis([str(project / "native_host.py")], excludes=["imageio_ffmpeg"])

# Qt imports the Windows ICU ABI. A same-named ICU from PATH can shadow it.
if is_windows:
    for item in (analysis, host_analysis):
        item.binaries = [
            entry for entry in item.binaries
            if entry[0].casefold() not in {"icuuc.dll", "icuin.dll"}
            and not entry[0].casefold().startswith("icudt")
        ]

archive = PYZ(analysis.pure, host_analysis.pure)
executable = EXE(
    archive, analysis.scripts, [], exclude_binaries=True,
    name="HizliIndir", console=False, icon=icon,
)
host_options = {"hide_console": "hide-early"} if is_windows else {}
host = EXE(
    archive, host_analysis.scripts, [], exclude_binaries=True,
    name="HizliIndirBrowserHost", console=True, icon=icon, **host_options,
)
distribution = COLLECT(
    executable, host, analysis.binaries, analysis.datas,
    host_analysis.binaries, host_analysis.datas, name="HizliIndir",
)
if is_mac:
    version = (project / "version.txt").read_text(encoding="utf-8-sig").strip()
    bundle = BUNDLE(
        distribution, name="HizliIndir.app", icon=icon,
        bundle_identifier="com.starlit.deskdownloader", version=version,
        info_plist={
            "CFBundleShortVersionString": version,
            "NSHighResolutionCapable": True,
            "LSBackgroundOnly": False,  # COLLECT inherits the console host settings.
            "NSAppleEventsUsageDescription": "Etkin tarayıcı sekmesinin adresini indirmek için okur.",
        },
    )
