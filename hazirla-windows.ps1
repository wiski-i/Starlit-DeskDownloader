param([string]$Python = 'python', [string]$MakeNsis = 'makensis.exe')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Sanal ortam oluşturulamadı.' }
    $pythonExe = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    & $pythonExe -m pip install -r requirements-verified.txt
    if ($LASTEXITCODE -ne 0) { throw 'Bağımlılıklar kurulamadı.' }
    $env:VIDEOINDIR_FFMPEG = & $pythonExe -c 'from imageio_ffmpeg import get_ffmpeg_exe; print(get_ffmpeg_exe())'
    if ($LASTEXITCODE -ne 0) { throw 'FFmpeg bulunamadı.' }
    $env:QT_QPA_PLATFORM = 'offscreen'
    & $pythonExe -m unittest -v
    if ($LASTEXITCODE -ne 0) { throw 'Python testleri başarısız.' }
    & node --test tests/extension.test.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Chrome eklenti testleri başarısız.' }
    & ./build.ps1 -Python $pythonExe
    & $pythonExe tests/check_packaged_host.py dist/HizliIndir/HizliIndirBrowserHost.exe
    if ($LASTEXITCODE -ne 0) { throw 'Paketli Chrome host testi başarısız.' }
    & ./build-installer.ps1 -MakeNsis $MakeNsis
} finally {
    Pop-Location
}
