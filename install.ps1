$ErrorActionPreference = 'Stop'

$bootstrapUrl = 'https://raw.githubusercontent.com/smturtle2/godot-mcp/main/src/godot_mcp/bootstrap.py'
$uvInstallerUrl = 'https://astral.sh/uv/install.ps1'
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ('godot-mcp-install-' + [Guid]::NewGuid().ToString('N'))
$bootstrap = Join-Path $tempDir 'bootstrap.py'
$uvInstaller = Join-Path $tempDir 'uv-install.ps1'

New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    Invoke-WebRequest -Uri $bootstrapUrl -OutFile $bootstrap

    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -ne $uvCommand) {
        $uvPath = $uvCommand.Source
    } else {
        Invoke-WebRequest -Uri $uvInstallerUrl -OutFile $uvInstaller
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $uvInstaller
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $uvPath = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
        if (-not (Test-Path -LiteralPath $uvPath -PathType Leaf)) {
            $uvPath = Join-Path $env:USERPROFILE '.local\bin\uv'
        }
        if (-not (Test-Path -LiteralPath $uvPath -PathType Leaf)) {
            throw "uv was not found in the user-local installation directory."
        }
    }

    & $uvPath run --no-project --python 3.13 $bootstrap @args
    exit $LASTEXITCODE
} finally {
    if (Test-Path -LiteralPath $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
