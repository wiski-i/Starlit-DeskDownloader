param(
    [string]$Python = 'python',
    [string]$Ffmpeg = ''
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Force -Path 'build' | Out-Null
    if (!$Ffmpeg) {
        $Ffmpeg = & $Python -c 'from downloads import ffmpeg_binary; print(ffmpeg_binary() or "")'
        if ($LASTEXITCODE -ne 0) { throw 'Install requirements.txt before building.' }
    }
    if (!$Ffmpeg -or !(Test-Path -LiteralPath $Ffmpeg -PathType Leaf)) {
        throw 'Set -Ffmpeg to an ffmpeg.exe path or install imageio-ffmpeg.'
    }
    $Ffmpeg = (Resolve-Path -LiteralPath $Ffmpeg).Path
    $packagedFfmpeg = Join-Path $PSScriptRoot 'build/ffmpeg.exe'
    if ($Ffmpeg -ne $packagedFfmpeg) { Copy-Item -LiteralPath $Ffmpeg -Destination $packagedFfmpeg -Force }
    $icon = Join-Path $PSScriptRoot 'build/HizliIndir.ico'
    & $Python -c 'import sys; from PySide6.QtWidgets import QApplication; from theme import mark_pixmap; app = QApplication([]); sys.exit(not mark_pixmap(256).save(sys.argv[1], "ICO"))' $icon
    if ($LASTEXITCODE -ne 0) { throw 'The application icon could not be generated.' }
    & $Python -m PyInstaller --noconfirm --workpath build/pyinstaller --distpath dist (Join-Path $PSScriptRoot 'HizliIndir.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
} finally {
    Pop-Location
}
