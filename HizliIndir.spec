from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project = Path(SPECPATH)
data_files = [(str(project / name), ".") for name in ("copy_tr.json", "browser_address.ps1")]
binary_files = [(str(project / "build" / "ffmpeg.exe"), "tools")]
hidden_imports = []

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
)

# Qt imports the Windows ICU ABI. A same-named ICU from PATH can shadow it.
analysis.binaries = [
    entry for entry in analysis.binaries
    if entry[0].casefold() not in {"icuuc.dll", "icuin.dll"}
    and not entry[0].casefold().startswith("icudt")
]

archive = PYZ(analysis.pure)
executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="HizliIndir",
    console=False,
    icon=str(project / "build" / "HizliIndir.ico"),
)

distribution = COLLECT(executable, analysis.binaries, analysis.datas, name="HizliIndir")
