$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$uploadRoot = Join-Path $projectRoot 'upload'
$uploadLib = Join-Path $uploadRoot 'lib'

New-Item -ItemType Directory -Path $uploadLib -Force | Out-Null

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
    (Join-Path $uploadRoot 'code.py')
Copy-PythonWithoutBom (Join-Path $projectRoot 'lib\toio_connection.py') `
    (Join-Path $uploadLib 'toio_connection.py')
Copy-PythonWithoutBom (Join-Path $projectRoot 'lib\tilt_drive.py') `
    (Join-Path $uploadLib 'tilt_drive.py')
Copy-PythonWithoutBom (Join-Path $projectRoot 'lib\tilt_settings.py') `
    (Join-Path $uploadLib 'tilt_settings.py')
Copy-PythonWithoutBom (Join-Path $projectRoot 'lib\accel_i2c.py') `
    (Join-Path $uploadLib 'accel_i2c.py')
Copy-PythonWithoutBom (Join-Path $projectRoot 'lib\tilt_display.py') `
    (Join-Path $uploadLib 'tilt_display.py')
Copy-PythonWithoutBom (Join-Path $projectRoot 'lib\button_control.py') `
    (Join-Path $uploadLib 'button_control.py')
Copy-PythonWithoutBom (Join-Path $projectRoot 'lib\sound_effects.py') `
    (Join-Path $uploadLib 'sound_effects.py')

Write-Output 'Upload files prepared from current sources:'
Get-ChildItem -LiteralPath $uploadRoot -File -Recurse |
    Select-Object -ExpandProperty FullName
