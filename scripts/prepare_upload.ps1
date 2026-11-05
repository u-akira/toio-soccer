$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$uploadRoot = Join-Path $projectRoot 'upload'
$debugRoot = Join-Path $uploadRoot 'debug'
$debugLib = Join-Path $debugRoot 'lib'
$releaseRoot = Join-Path $uploadRoot 'release'

# Remove artifacts from the previous upload layout.
foreach ($stalePath in @(
    (Join-Path $uploadRoot 'code.py'),
    (Join-Path $uploadRoot 'lib')
)) {
    if (Test-Path -LiteralPath $stalePath) {
        Remove-Item -LiteralPath $stalePath -Recurse -Force
    }
}

New-Item -ItemType Directory -Path $debugLib -Force | Out-Null
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null

function Copy-PythonWithoutBom($source, $destination) {
    $bytes = [System.IO.File]::ReadAllBytes($source)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and
        $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $bytes = $bytes[3..($bytes.Length - 1)]
    }
    [System.IO.File]::WriteAllBytes($destination, $bytes)

    $output = [System.IO.File]::ReadAllBytes($destination)
    if ($output.Length -ge 3 -and $output[0] -eq 0xEF -and
        $output[1] -eq 0xBB -and $output[2] -eq 0xBF) {
        throw "UTF-8 BOM remains in upload file: $destination"
    }
}

Copy-PythonWithoutBom (Join-Path $projectRoot 'code.py') `
    (Join-Path $debugRoot 'code.py')
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'lib') -Filter '*.py' -File |
    ForEach-Object {
        Copy-PythonWithoutBom $_.FullName (Join-Path $debugLib $_.Name)
    }

Push-Location $projectRoot
try {
    $env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'
    uv run --python 3.13 python tools/build_release.py `
        --output (Join-Path $releaseRoot 'code.py')
    if ($LASTEXITCODE -ne 0) {
        throw 'Release bundle generation failed.'
    }
}
finally {
    Pop-Location
}

$releaseCode = Join-Path $releaseRoot 'code.py'
$releaseBytes = [System.IO.File]::ReadAllBytes($releaseCode)
if ($releaseBytes.Length -ge 3 -and $releaseBytes[0] -eq 0xEF -and
    $releaseBytes[1] -eq 0xBB -and $releaseBytes[2] -eq 0xBF) {
    throw "UTF-8 BOM remains in upload file: $releaseCode"
}

Write-Output 'Upload files prepared from current sources:'
Get-ChildItem -LiteralPath $uploadRoot -File -Recurse |
    Select-Object -ExpandProperty FullName
