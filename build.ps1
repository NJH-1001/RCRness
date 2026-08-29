param(
    [Parameter(Mandatory = $true)]
    [string]$Rom,
    [string]$BuildDirectory = 'build-public'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$romPath = (Resolve-Path -LiteralPath $Rom).Path
$buildRoot = Join-Path $projectRoot $BuildDirectory
$recompilerBuild = Join-Path $projectRoot 'nesrecomp\build\recompiler-public'
$recompiler = Join-Path $recompilerBuild 'Release\NESRecomp.exe'

if (-not (Test-Path -LiteralPath $romPath -PathType Leaf)) {
    throw "ROM not found: $Rom"
}

if (Test-Path -LiteralPath (Join-Path $projectRoot '.git')) {
    & git -C $projectRoot submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize submodules.' }
}
elseif (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'nesrecomp\recompiler'))) {
    $frameworkUrl = 'https://github.com/NJH-1001/nesrecomp.git'
    $frameworkCommit = (Get-Content -Raw (Join-Path $projectRoot 'NESRECOMP_COMMIT')).Trim()
    & git clone --recursive $frameworkUrl (Join-Path $projectRoot 'nesrecomp')
    if ($LASTEXITCODE -ne 0) { throw 'Could not clone NESRecomp.' }
    & git -C (Join-Path $projectRoot 'nesrecomp') checkout $frameworkCommit
    if ($LASTEXITCODE -ne 0) { throw 'Could not select the pinned NESRecomp commit.' }
    & git -C (Join-Path $projectRoot 'nesrecomp') submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize NESRecomp submodules.' }
}

& cmake -S (Join-Path $projectRoot 'nesrecomp\recompiler') `
    -B $recompilerBuild -G 'Visual Studio 17 2022' -A x64
if ($LASTEXITCODE -ne 0) { throw 'Could not configure NESRecomp.' }
& cmake --build $recompilerBuild --config Release
if ($LASTEXITCODE -ne 0) { throw 'Could not build NESRecomp.' }

Push-Location $projectRoot
try {
    & $recompiler $romPath --game (Join-Path $projectRoot 'game.toml')
    if ($LASTEXITCODE -ne 0) { throw "NESRecomp failed with exit code $LASTEXITCODE" }

    & cmake -S $projectRoot -B $buildRoot -G 'Visual Studio 17 2022' -A x64 `
        -DNESRECOMP_ENABLE_TRACE=OFF -DNESRECOMP_ENABLE_STACK_TRACKING=OFF
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure RCRness.' }
    & cmake --build $buildRoot --config Release
    if ($LASTEXITCODE -ne 0) { throw 'Could not build RCRness.' }
}
finally {
    Pop-Location
}

Write-Host "Built $buildRoot\Release\RCRness.exe"
