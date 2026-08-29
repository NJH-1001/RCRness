param(
    [Parameter(Mandatory = $true)]
    [string]$Rom,
    [string]$BuildDirectory = 'build-public',
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

function Update-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
}

function Get-ToolCommand {
    param([Parameter(Mandatory = $true)][string]$Name)

    return Get-Command $Name -ErrorAction SilentlyContinue
}

function Get-VCToolsInstallation {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) {
        return $null
    }

    $installation = & $vswhere -latest -products '*' -version '[17.0,18.0)' `
        -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
        -property installationPath
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ($installation | Select-Object -First 1)
}

function Get-WinGetCommand {
    $command = Get-ToolCommand -Name 'winget.exe'
    if ($command) {
        return $command.Source
    }

    # App Installer normally ships with current Windows 10 and Windows 11.
    # Ask Windows to register the installed system package if it has not yet
    # been registered for this user.
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
Windows Package Manager (winget) is not available. Install or update Microsoft's
App Installer, then run this script again:
https://learn.microsoft.com/windows/package-manager/winget/
'@
}

function Install-WinGetPackage {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [string[]]$AdditionalArguments = @()
    )

    $arguments = @(
        'install', '--id', $Id, '--exact', '--source', 'winget',
        '--accept-source-agreements', '--accept-package-agreements',
        '--disable-interactivity'
    ) + $AdditionalArguments

    Write-Host "Installing $Id through Windows Package Manager..."
    & $script:winGet @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Windows Package Manager could not install $Id (exit code $LASTEXITCODE)."
    }
    Update-ProcessPath
}

function Test-CMakeVersion {
    $cmake = Get-ToolCommand -Name 'cmake.exe'
    if (-not $cmake) {
        return $false
    }

    $versionText = & $cmake.Source --version | Select-Object -First 1
    if ($LASTEXITCODE -ne 0 -or $versionText -notmatch '(\d+\.\d+(?:\.\d+)?)') {
        return $false
    }
    return ([version]$Matches[1] -ge [version]'3.20')
}

$needsGit = -not (Get-ToolCommand -Name 'git.exe')
$needsCMake = -not (Test-CMakeVersion)
$needsVCTools = -not (Get-VCToolsInstallation)

if ($needsGit -or $needsCMake -or $needsVCTools) {
    $missingTools = @()
    if ($needsGit) { $missingTools += 'Git' }
    if ($needsCMake) { $missingTools += 'CMake 3.20 or newer' }
    if ($needsVCTools) { $missingTools += 'Visual Studio 2022 C++ build tools' }

    Write-Host "Missing build tools: $($missingTools -join ', ')"
    Write-Host 'Setup uses WinGet packages and requires acceptance of their source and package license agreements.'
    if (-not $AcceptToolLicenses) {
        $answer = Read-Host 'Install the missing tools and accept those agreements? [y/N]'
        if ($answer -notmatch '^(?i:y|yes)$') {
            throw 'Tool installation was cancelled.'
        }
    }

    $script:winGet = Get-WinGetCommand

    if ($needsGit) {
        Install-WinGetPackage -Id 'Git.Git' -AdditionalArguments @('--silent')
    }
    if ($needsCMake) {
        Install-WinGetPackage -Id 'Kitware.CMake' -AdditionalArguments @('--silent')
    }
    if ($needsVCTools) {
        Install-WinGetPackage -Id 'Microsoft.VisualStudio.2022.BuildTools' `
            -AdditionalArguments @(
                '--force', '--override',
                '--passive --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended'
            )
    }
}

Update-ProcessPath

if (-not (Get-ToolCommand -Name 'git.exe')) {
    throw 'git.exe is still unavailable after setup. Restart Windows and run this script again.'
}
if (-not (Test-CMakeVersion)) {
    throw 'CMake 3.20 or newer is still unavailable after setup. Restart Windows and run this script again.'
}
if (-not (Get-VCToolsInstallation)) {
    throw 'The Visual Studio 2022 C++ x64 build tools are unavailable after setup. Restart Windows and run this script again.'
}

Write-Host 'Toolchain ready. Building RCRness...'
& (Join-Path $projectRoot 'build.ps1') -Rom $romPath -BuildDirectory $BuildDirectory
if ($LASTEXITCODE -ne 0) {
    throw "RCRness build failed with exit code $LASTEXITCODE."
}
