param(
    [string]$OutputDirectory = 'dist-public',
    [switch]$SkipSourcePackage
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputRoot = Join-Path $projectRoot $OutputDirectory
$sourceArchive = Join-Path $outputRoot 'RCRness-Windows-x86_64-source.zip'
$bootstrapSource = Join-Path $projectRoot 'bootstrap\RCRnessSetup.cs'
$bootstrapExe = Join-Path $outputRoot 'RCRness-Setup.exe'

if (-not $SkipSourcePackage) {
    & (Join-Path $projectRoot 'package-public.ps1') -OutputDirectory $OutputDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the public source kit.' }
}

if (-not (Test-Path -LiteralPath $sourceArchive -PathType Leaf)) {
    throw "Public source kit not found: $sourceArchive"
}
if (-not (Test-Path -LiteralPath $bootstrapSource -PathType Leaf)) {
    throw "Bootstrap source not found: $bootstrapSource"
}

$compilerCandidates = @(
    (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'),
    (Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe')
)
$compiler = $compilerCandidates | Where-Object {
    Test-Path -LiteralPath $_ -PathType Leaf
} | Select-Object -First 1
if (-not $compiler) {
    throw 'The Windows .NET Framework C# compiler was not found.'
}

$frameworkRoot = Split-Path -Parent $compiler
$references = @(
    (Join-Path $frameworkRoot 'System.dll'),
    (Join-Path $frameworkRoot 'System.Drawing.dll'),
    (Join-Path $frameworkRoot 'System.Windows.Forms.dll'),
    (Join-Path $frameworkRoot 'System.IO.Compression.dll'),
    (Join-Path $frameworkRoot 'System.IO.Compression.FileSystem.dll')
)
foreach ($reference in $references) {
    if (-not (Test-Path -LiteralPath $reference -PathType Leaf)) {
        throw "Required .NET Framework assembly not found: $reference"
    }
}

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
if (Test-Path -LiteralPath $bootstrapExe) {
    Remove-Item -LiteralPath $bootstrapExe -Force
}

$arguments = @(
    '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/warn:4', '/warnaserror+',
    "/out:$bootstrapExe",
    "/resource:$sourceArchive,RCRness.SourceKit.zip"
)
foreach ($reference in $references) {
    $arguments += "/reference:$reference"
}
$arguments += $bootstrapSource

& $compiler @arguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $bootstrapExe -PathType Leaf)) {
    throw 'Could not build RCRness-Setup.exe.'
}

Write-Host "Bootstrap executable: $bootstrapExe"
