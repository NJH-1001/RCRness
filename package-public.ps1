param(
    [string]$OutputDirectory = 'dist-public'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputRoot = Join-Path $projectRoot $OutputDirectory
$stageRoot = Join-Path $outputRoot 'RCRness-Windows-x86_64-source'
$archive = Join-Path $outputRoot 'RCRness-Windows-x86_64-source.zip'

$forbiddenTracked = @(
    '\.(nes|bin|sav|srm|state|exe|dll|pdb|obj|zip)$',
    '(^|/)generated/',
    '(^|/)ghidra/',
    '(^|/)(captures|savestates|sprite_trace_[^/]*)/',
    '(^|/)config\.ini$',
    '(^|/)rom\.cfg$'
)

$tracked = & git -C $projectRoot ls-files
if ($LASTEXITCODE -ne 0) { throw 'Could not enumerate tracked files.' }
foreach ($path in $tracked) {
    foreach ($pattern in $forbiddenTracked) {
        if ($path -match $pattern) {
            throw "Public distribution audit failed: tracked forbidden file '$path'"
        }
    }
}

if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
}
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}
New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null

foreach ($path in $tracked) {
    if ($path -eq 'nesrecomp') { continue }
    $source = Join-Path $projectRoot $path
    $destination = Join-Path $stageRoot $path
    $parent = Split-Path -Parent $destination
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item -LiteralPath $source -Destination $destination
}

Compress-Archive -LiteralPath $stageRoot -DestinationPath $archive
Write-Host "Public package: $archive"
