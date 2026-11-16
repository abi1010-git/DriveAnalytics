# Exports the static site's data, uploads it to the data-latest release and starts the Pages
# workflow, which builds the site with these files (docs/STATIC_SITE.md).
# Needs the backend venv and a logged-in gh. Uses DATABASE_URL if it is set, like the pipeline.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$data = Join-Path $root 'frontend\public\data'
$python = Join-Path $backend '.venv\Scripts\python.exe'

# Native commands don't throw on failure; stop on a non-zero exit code instead.
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" } }

if (-not (Test-Path $python)) { throw "No Python venv at $python" }
if ($env:DATABASE_URL) { Write-Host "Exporting from DATABASE_URL" } else { Write-Host "DATABASE_URL is not set: exporting from the default local SQLite file" }

Push-Location $backend
try { & $python -m pipeline export --out ..\frontend\public\data; Check 'Export' } finally { Pop-Location }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("site-data-" + [guid]::NewGuid())
New-Item -ItemType Directory $tmp | Out-Null
$archive = Join-Path $tmp 'site-data.tar.gz'
Push-Location $root
try {
  # Files at the archive root, so the workflow can extract straight into frontend/public/data.
  tar -czf $archive -C $data .; Check 'tar'
  Write-Host ("Archive: {0:N1} MB" -f ((Get-Item $archive).Length / 1MB))

  # gh writes "release not found" to stderr; keep PowerShell 5.1 from turning that into an error.
  $ErrorActionPreference = 'Continue'
  gh release view data-latest *> $null
  $exists = $LASTEXITCODE -eq 0
  $ErrorActionPreference = 'Stop'
  if (-not $exists) {
    gh release create data-latest --title "Site data" --notes "Data files for the GitHub Pages site. Replaced by scripts/publish-data.ps1." --latest=false; Check 'gh release create'
  }
  gh release upload data-latest $archive --clobber; Check 'gh release upload'
  gh workflow run pages.yml; Check 'gh workflow run'
  Write-Host "Uploaded. The Pages workflow is building the site: gh run list --workflow pages.yml"
} finally {
  Pop-Location
  Remove-Item -Recurse -Force $tmp
}
