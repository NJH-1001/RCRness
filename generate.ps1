param(
    [Parameter(Mandatory = $true)]
    [string]$Rom
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$recompiler = Join-Path $projectRoot 'nesrecomp\build\recompiler-public\Release\NESRecomp.exe'

if (-not (Test-Path -LiteralPath $Rom -PathType Leaf)) {
    throw "ROM not found: $Rom"
}
if (-not (Test-Path -LiteralPath $recompiler -PathType Leaf)) {
    throw "NESRecomp is not built at $recompiler. Run build.ps1 instead."
}

Push-Location $projectRoot
try {
    & $recompiler $Rom --game (Join-Path $projectRoot 'game.toml')
    if ($LASTEXITCODE -ne 0) { throw "NESRecomp failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}
