param(
    [ValidatePattern('^(0|[1-9]\d{0,4})\.(0|[1-9]\d{0,4})\.(0|[1-9]\d{0,4})$')]
    [string]$Version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'version.txt') -Raw).Trim(),
    [string]$MakeNsis = 'makensis.exe'
)

$ErrorActionPreference = 'Stop'
if (@($Version.Split('.') | Where-Object { [int]$_ -gt 65535 }).Count) {
    throw 'Version components must be between 0 and 65535.'
}

$compiler = (Get-Command -Name $MakeNsis -CommandType Application).Source
$bundle = Join-Path $PSScriptRoot 'dist/HizliIndir'
$icon = Join-Path $PSScriptRoot 'build/HizliIndir.ico'
$manifest = 'com.starlit.deskdownloader.json'
foreach ($required in @("$bundle/HizliIndir.exe", "$bundle/HizliIndirBrowserHost.exe", "$bundle/$manifest", "$bundle/_internal/tools/ffmpeg.exe", $icon)) {
    if (!(Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Run build.ps1 first. Missing file: $required"
    }
}

# Compile an exact file list so upgrades and removal leave any user's files alone.
$bundle = (Resolve-Path -LiteralPath $bundle).Path
$files = @(Get-ChildItem -LiteralPath $bundle -Recurse -File | Sort-Object FullName)
$directories = @(Get-ChildItem -LiteralPath $bundle -Recurse -Directory |
    Sort-Object -Property @{ Expression = { $_.FullName.Length }; Descending = $true })
$packageKiB = [math]::Ceiling((($files | Measure-Object -Property Length -Sum).Sum +
    (Get-Item -LiteralPath "$PSScriptRoot/LICENSE").Length) / 1KB)

function ConvertTo-NsisLiteral([string]$Value) {
    return $Value.Replace('$', '$$').Replace('"', '$\"')
}

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('!macro InstallPayload')
$currentDirectory = $null
foreach ($file in $files) {
    $relativeDirectory = $file.DirectoryName.Substring($bundle.Length)
    if ($currentDirectory -cne $relativeDirectory) {
        $lines.Add(('  SetOutPath "$AppDir{0}"' -f (ConvertTo-NsisLiteral $relativeDirectory)))
        $currentDirectory = $relativeDirectory
    }
    $lines.Add(('  File "{0}"' -f (ConvertTo-NsisLiteral $file.FullName)))
}
$lines.Add('  SetOutPath "$AppDir"')
$lines.Add(('  File "{0}"' -f (ConvertTo-NsisLiteral (Join-Path $PSScriptRoot 'LICENSE'))))
$lines.Add('!macroend')
$lines.Add('!macro RemoveFiles Root')
foreach ($file in $files) {
    $relativeFile = $file.FullName.Substring($bundle.Length)
    $lines.Add(('  Delete "${{Root}}{0}"' -f (ConvertTo-NsisLiteral $relativeFile)))
}
$lines.Add('  Delete "${Root}\LICENSE"')
$lines.Add('!macroend')
$lines.Add('!macro RemoveEmptyDirs Root')
foreach ($directory in $directories) {
    $relativeDirectory = $directory.FullName.Substring($bundle.Length)
    $lines.Add(('  RMDir "${{Root}}{0}"' -f (ConvertTo-NsisLiteral $relativeDirectory)))
}
$lines.Add('!macroend')

$include = Join-Path $PSScriptRoot "build/installer-payload-$Version.nsh"
[IO.File]::WriteAllLines($include, $lines, [Text.UTF8Encoding]::new($true))
$setup = Join-Path $PSScriptRoot "dist/Starlit-DeskDownloader-Setup-$Version-win-x64.exe"
& $compiler /INPUTCHARSET UTF8 /V2 /WX /NOCD "/DAPP_VERSION=$Version" "/DSETUP_FILE=$setup" "/DAPP_ICON=$icon" `
    "/DPAYLOAD_INCLUDE=$include" "/DPAYLOAD_KIB=$packageKiB" (Join-Path $PSScriptRoot 'installer/setup.nsi')
if ($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $setup -PathType Leaf)) {
    throw 'Windows installer build failed.'
}
@($setup) | ForEach-Object { $hash = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant(); "${hash}  $([IO.Path]::GetFileName($_))" } | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'dist/SHA256SUMS') -Encoding ascii
Write-Output $setup
