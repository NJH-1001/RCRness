param(
    [Parameter(Mandatory = $true)]
    [string]$Rom,
    [string]$BuildDirectory = 'build-public',
    [string]$CMakeExecutable = 'cmake.exe',
    [string]$NinjaExecutable = 'ninja.exe',
    [string]$CCompiler = 'x86_64-w64-mingw32-clang.exe',
    [switch]$UseVisualStudio,
    [switch]$Trace
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$romPath = (Resolve-Path -LiteralPath $Rom).Path
$buildRoot = if ([IO.Path]::IsPathRooted($BuildDirectory)) { [IO.Path]::GetFullPath($BuildDirectory) } else { Join-Path $projectRoot $BuildDirectory }
$recompilerBuild = Join-Path $buildRoot 'recompiler'
$recompiler = if ($UseVisualStudio) { Join-Path $recompilerBuild 'Release\NESRecomp.exe' } else { Join-Path $recompilerBuild 'NESRecomp.exe' }
New-Item -ItemType Directory -Force -Path (Join-Path $buildRoot 'temp') | Out-Null
$env:TEMP = Join-Path $buildRoot 'temp'
$env:TMP = $env:TEMP
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $romPath).Hash -ne 'B95F8DEF04C0012604B7CC68CF4ED8F49B2DFE4BEDA6182051DE4B2423BEA7B1') {
    throw 'This build requires the exact River City Ransom USA ROM documented in README.md.'
}

function Resolve-Executable {
    param(
        [Parameter(Mandatory = $true)][string]$Value,
        [Parameter(Mandatory = $true)][string]$DisplayName
    )

    if (Test-Path -LiteralPath $Value -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Value).Path
    }
    $command = Get-Command $Value -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    throw "$DisplayName was not found: $Value"
}

function Assert-NinjaBuildDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $cache = Join-Path $Path 'CMakeCache.txt'
    if ((Test-Path -LiteralPath $cache -PathType Leaf) -and
        -not (Select-String -LiteralPath $cache -Pattern '^CMAKE_GENERATOR:INTERNAL=Ninja$' -Quiet)) {
        throw "Build directory '$Path' was created with another generator. Choose a different -BuildDirectory."
    }
}

if (-not (Test-Path -LiteralPath $romPath -PathType Leaf)) {
    throw "ROM not found: $Rom"
}

if ($CMakeExecutable -eq 'cmake.exe' -and (Test-Path -LiteralPath "$env:ProgramFiles\CMake\bin\cmake.exe")) {
    $CMakeExecutable = "$env:ProgramFiles\CMake\bin\cmake.exe"
}
$cmake = Resolve-Executable -Value $CMakeExecutable -DisplayName 'CMake'
if (-not $UseVisualStudio) {
    $ninja = Resolve-Executable -Value $NinjaExecutable -DisplayName 'Ninja'
    $compiler = Resolve-Executable -Value $CCompiler -DisplayName 'LLVM-MinGW C compiler'
}

if ((Test-Path -LiteralPath (Join-Path $projectRoot '.git')) -and
    -not (Test-Path -LiteralPath (Join-Path $projectRoot 'nesrecomp\recompiler'))) {
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

& (Join-Path $projectRoot 'prepare-engine.ps1')
if ($UseVisualStudio) {
    $generatorArgs = @('-G', 'Visual Studio 17 2022', '-A', 'x64')
} else {
    Assert-NinjaBuildDirectory -Path $recompilerBuild
    Assert-NinjaBuildDirectory -Path $buildRoot
    $generatorArgs = @('-G','Ninja', '-DCMAKE_BUILD_TYPE=Release', "-DCMAKE_MAKE_PROGRAM:FILEPATH=$ninja", "-DCMAKE_C_COMPILER:FILEPATH=$compiler")
}

& $cmake -S (Join-Path $projectRoot 'nesrecomp\recompiler') `
    -B $recompilerBuild @generatorArgs
if ($LASTEXITCODE -ne 0) { throw 'Could not configure NESRecomp.' }
& $cmake --build $recompilerBuild --config Release --parallel 4
if ($LASTEXITCODE -ne 0) { throw 'Could not build NESRecomp.' }

Push-Location $projectRoot
try {
    & $recompiler $romPath --game (Join-Path $projectRoot 'game.toml')
    if ($LASTEXITCODE -ne 0) { throw "NESRecomp failed with exit code $LASTEXITCODE" }

    $traceValue = if ($Trace) { 'ON' } else { 'OFF' }
    & $cmake -S $projectRoot -B $buildRoot @generatorArgs `
        "-DNESRECOMP_ENABLE_TRACE=$traceValue" '-DNESRECOMP_ENABLE_STACK_TRACKING=OFF' `
        "-DNESRECOMP_ENABLE_POSTMORTEM_RINGS=$traceValue"
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure RCRness.' }
    & $cmake --build $buildRoot --config Release --parallel 4
    if ($LASTEXITCODE -ne 0) { throw 'Could not build RCRness.' }
}
finally {
    Pop-Location
}

$gameExecutable = if ($UseVisualStudio) { Join-Path $buildRoot 'Release\RCRness.exe' } else { Join-Path $buildRoot 'RCRness.exe' }
Write-Host "Built $gameExecutable"
