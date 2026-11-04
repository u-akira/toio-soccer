$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:UV_CACHE_DIR = Join-Path $projectRoot '.uv-cache'

Push-Location $projectRoot
try {
    .\prepare_upload.ps1

    foreach ($target in @('debug', 'release')) {
        Write-Output "Running tests against $target sources..."
        $env:TOIO_TEST_TARGET = $target
        uv run --python 3.13 python -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) {
            throw "Tests failed against $target sources."
        }
    }
}
finally {
    Remove-Item Env:TOIO_TEST_TARGET -ErrorAction SilentlyContinue
    Pop-Location
}
