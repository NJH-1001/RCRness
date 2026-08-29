param(
    [Parameter(Mandatory = $true)]
    [string]$Rom,
    [string]$BuildDirectory = 'build-public',
    [string]$ToolchainDirectory,
    [switch]$AcceptToolLicenses
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not [Environment]::Is64BitOperatingSystem) {
    throw 'RCRness requires 64-bit Windows.'
}

if (-not (Test-Path -LiteralPath $Rom -PathType Leaf)) {
    throw "ROM not found: $Rom"
}
$romPath = (Resolve-Path -LiteralPath $Rom).Path

if ([string]::IsNullOrWhiteSpace($ToolchainDirectory)) {
    $ToolchainDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) `
        'RCRness\toolchains'
}
$toolchainRoot = [IO.Path]::GetFullPath($ToolchainDirectory)
$downloadRoot = Join-Path $toolchainRoot 'downloads'

function Update-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
}

function Get-ToolCommand {
    param([Parameter(Mandatory = $true)][string]$Name)

    return Get-Command $Name -ErrorAction SilentlyContinue
}

function Get-WinGetCommand {
    $command = Get-ToolCommand -Name 'winget.exe'
    if ($command) {
        return $command.Source
    }

    $registerCommand = Get-Command Add-AppxPackage -ErrorAction SilentlyContinue
    if ($registerCommand) {
        try {
            Add-AppxPackage -RegisterByFamilyName -MainPackage `
                Microsoft.DesktopAppInstaller_8wekyb3d8bbwe -ErrorAction Stop
        }
        catch {
            Write-Verbose "Could not register App Installer: $($_.Exception.Message)"
        }
    }

    Update-ProcessPath
    $command = Get-ToolCommand -Name 'winget.exe'
    if ($command) {
        return $command.Source
    }

    throw @'
Git is required to obtain the pinned NESRecomp source, but neither Git nor
Windows Package Manager (winget) is available. Install Git for Windows, then
run this setup again:
https://git-scm.com/download/win
'@
}

function Install-Git {
    if (-not $AcceptToolLicenses) {
        $answer = Read-Host 'Git is missing. Install Git with WinGet and accept its package agreements? [y/N]'
        if ($answer -notmatch '^(?i:y|yes)$') {
            throw 'Git installation was cancelled.'
        }
    }

    $winGet = Get-WinGetCommand
    Write-Host 'Installing Git through Windows Package Manager...'
    & $winGet install --id Git.Git --exact --source winget `
        --accept-source-agreements --accept-package-agreements `
        --disable-interactivity --silent
    if ($LASTEXITCODE -ne 0) {
        throw "Windows Package Manager could not install Git (exit code $LASTEXITCODE)."
    }
    Update-ProcessPath
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Install-PortableArchive {
    param(
        [Parameter(Mandatory = $true)][string]$DisplayName,
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Sha256,
        [Parameter(Mandatory = $true)][string]$ArchiveName,
        [Parameter(Mandatory = $true)][string]$DirectoryName,
        [Parameter(Mandatory = $true)][string]$RequiredFile,
        [string]$ArchiveRoot
    )

    $target = Join-Path $toolchainRoot $DirectoryName
    $required = Join-Path $target $RequiredFile
    if (Test-Path -LiteralPath $required -PathType Leaf) {
        Write-Host "$DisplayName is ready."
        return $target
    }

    New-Item -ItemType Directory -Path $downloadRoot -Force | Out-Null
    $archive = Join-Path $downloadRoot $ArchiveName
    $partial = "$archive.partial"
    $expected = $Sha256.ToUpperInvariant()

    if ((Test-Path -LiteralPath $archive -PathType Leaf) -and
        ((Get-Sha256 -Path $archive) -ne $expected)) {
        Remove-Item -LiteralPath $archive -Force
    }

    if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
        if (Test-Path -LiteralPath $partial) {
            Remove-Item -LiteralPath $partial -Force
        }
        Write-Host "Downloading $DisplayName..."
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $partial
        if ((Get-Sha256 -Path $partial) -ne $expected) {
            Remove-Item -LiteralPath $partial -Force
            throw "$DisplayName failed its SHA-256 integrity check."
        }
        Move-Item -LiteralPath $partial -Destination $archive
    }

    if ((Get-Sha256 -Path $archive) -ne $expected) {
        throw "$DisplayName failed its SHA-256 integrity check."
    }

    $staging = Join-Path $toolchainRoot ('.extract-' + $DirectoryName + '-' + $PID)
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
    New-Item -ItemType Directory -Path $staging -Force | Out-Null

    Write-Host "Extracting $DisplayName..."
    try {
        Expand-Archive -LiteralPath $archive -DestinationPath $staging -Force
        $extracted = if ([string]::IsNullOrEmpty($ArchiveRoot)) {
            $staging
        }
        else {
            Join-Path $staging $ArchiveRoot
        }
        if (-not (Test-Path -LiteralPath (Join-Path $extracted $RequiredFile) -PathType Leaf)) {
            throw "$DisplayName archive does not contain the expected files."
        }
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        Move-Item -LiteralPath $extracted -Destination $target
    }
    finally {
        if (Test-Path -LiteralPath $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force
        }
    }

    return $target
}

[Net.ServicePointManager]::SecurityProtocol = `
    [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

if (-not (Get-ToolCommand -Name 'git.exe')) {
    Install-Git
}
if (-not (Get-ToolCommand -Name 'git.exe')) {
    throw 'git.exe is still unavailable after setup. Restart Windows and run this setup again.'
}

Write-Host "Preparing a compact portable toolchain in $toolchainRoot"
$llvmRoot = Install-PortableArchive `
    -DisplayName 'LLVM-MinGW 20260616 (portable C/C++ compiler)' `
    -Url 'https://github.com/mstorsjo/llvm-mingw/releases/download/20260616/llvm-mingw-20260616-ucrt-x86_64.zip' `
    -Sha256 'B9B68A4D276E16FA25802AABA458E4638F64B3884C290AACCDC2D87083B6CA35' `
    -ArchiveName 'llvm-mingw-20260616-ucrt-x86_64.zip' `
    -DirectoryName 'llvm-mingw-20260616-ucrt-x86_64' `
    -ArchiveRoot 'llvm-mingw-20260616-ucrt-x86_64' `
    -RequiredFile 'bin\x86_64-w64-mingw32-clang.exe'

$cmakeRoot = Install-PortableArchive `
    -DisplayName 'CMake 4.4.2 (portable)' `
    -Url 'https://github.com/Kitware/CMake/releases/download/v4.4.2/cmake-4.4.2-windows-x86_64.zip' `
    -Sha256 'E8139D85B3813BC38833142AE1940472E9A587E9B5D2718AC1804C60F4E57A64' `
    -ArchiveName 'cmake-4.4.2-windows-x86_64.zip' `
    -DirectoryName 'cmake-4.4.2-windows-x86_64' `
    -ArchiveRoot 'cmake-4.4.2-windows-x86_64' `
    -RequiredFile 'bin\cmake.exe'

$ninjaRoot = Install-PortableArchive `
    -DisplayName 'Ninja 1.13.2 (portable)' `
    -Url 'https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip' `
    -Sha256 '07FC8261B42B20E71D1720B39068C2E14FFCEE6396B76FB7A795FB460B78DC65' `
    -ArchiveName 'ninja-win-1.13.2.zip' `
    -DirectoryName 'ninja-1.13.2' `
    -RequiredFile 'ninja.exe'

$cmake = Join-Path $cmakeRoot 'bin\cmake.exe'
$ninja = Join-Path $ninjaRoot 'ninja.exe'
$compiler = Join-Path $llvmRoot 'bin\x86_64-w64-mingw32-clang.exe'

Write-Host 'Portable toolchain ready. Building RCRness...'
& (Join-Path $projectRoot 'build.ps1') -Rom $romPath `
    -BuildDirectory $BuildDirectory -CMakeExecutable $cmake `
    -NinjaExecutable $ninja -CCompiler $compiler
if ($LASTEXITCODE -ne 0) {
    throw "RCRness build failed with exit code $LASTEXITCODE."
}
