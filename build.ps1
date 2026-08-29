param(
    [Parameter(Mandatory = $true)]
    [string]$Rom,
    [string]$BuildDirectory = 'build-public',
    [string]$CMakeExecutable = 'cmake.exe',
    [string]$NinjaExecutable = 'ninja.exe',
    [string]$CCompiler = 'x86_64-w64-mingw32-clang.exe'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$romPath = (Resolve-Path -LiteralPath $Rom).Path
$buildRoot = Join-Path $projectRoot $BuildDirectory
$recompilerBuild = Join-Path $projectRoot 'nesrecomp\build\recompiler-public-ninja'
$recompiler = Join-Path $recompilerBuild 'NESRecomp.exe'

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

$cmake = Resolve-Executable -Value $CMakeExecutable -DisplayName 'CMake'
$ninja = Resolve-Executable -Value $NinjaExecutable -DisplayName 'Ninja'
$compiler = Resolve-Executable -Value $CCompiler -DisplayName 'LLVM-MinGW C compiler'

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

Assert-NinjaBuildDirectory -Path $recompilerBuild
Assert-NinjaBuildDirectory -Path $buildRoot

& $cmake -S (Join-Path $projectRoot 'nesrecomp\recompiler') `
    -B $recompilerBuild -G Ninja `
    '-DCMAKE_BUILD_TYPE=Release' `
    "-DCMAKE_MAKE_PROGRAM:FILEPATH=$ninja" `
    "-DCMAKE_C_COMPILER:FILEPATH=$compiler"
if ($LASTEXITCODE -ne 0) { throw 'Could not configure NESRecomp.' }
& $cmake --build $recompilerBuild
if ($LASTEXITCODE -ne 0) { throw 'Could not build NESRecomp.' }

Push-Location $projectRoot
try {
    & $recompiler $romPath --game (Join-Path $projectRoot 'game.toml')
    if ($LASTEXITCODE -ne 0) { throw "NESRecomp failed with exit code $LASTEXITCODE" }

    & $cmake -S $projectRoot -B $buildRoot -G Ninja `
        '-DCMAKE_BUILD_TYPE=Release' `
        "-DCMAKE_MAKE_PROGRAM:FILEPATH=$ninja" `
        "-DCMAKE_C_COMPILER:FILEPATH=$compiler" `
        '-DNESRECOMP_ENABLE_TRACE=OFF' '-DNESRECOMP_ENABLE_STACK_TRACKING=OFF'
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure RCRness.' }
    & $cmake --build $buildRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not build RCRness.' }
}
finally {
    Pop-Location
}

Write-Host "Built $buildRoot\RCRness.exe"
