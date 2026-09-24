Set-Location $PSScriptRoot
if (Get-Command py -ErrorAction SilentlyContinue) { $PY='py' } else { $PY='python' }
& $PY migrate_v5.py
& $PY game_detail_importer.py range --from-year 2025 --to-year 2025
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host '完了しました。'
