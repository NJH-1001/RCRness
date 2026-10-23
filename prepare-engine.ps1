# Keep the upstream gitlink fetchable. The reviewed local renderer changes are
# stored as a source patch and applied after the original dependency is fetched.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$engineRoot = Join-Path $projectRoot 'nesrecomp'
$patch = Join-Path $projectRoot 'engine-patches\adaptive-renderer.patch'
if (-not (Test-Path -LiteralPath $patch -PathType Leaf)) { throw "Missing engine patch: $patch" }
$previousPreference=$ErrorActionPreference
$ErrorActionPreference='Continue'
& git -C $engineRoot apply --reverse --check --whitespace=nowarn $patch 2>$null
$patchAlreadyApplied=$LASTEXITCODE -eq 0
$ErrorActionPreference=$previousPreference
if ($patchAlreadyApplied) { Write-Host 'Enhanced renderer engine patch is already applied.'; return }
& git -C $engineRoot apply --check --whitespace=nowarn $patch
if ($LASTEXITCODE -ne 0) { throw 'The engine patch does not apply cleanly. Preserve local changes and inspect the pinned dependency.' }
& git -C $engineRoot apply --whitespace=nowarn $patch
if ($LASTEXITCODE -ne 0) { throw 'Could not apply the enhanced renderer engine patch.' }
