$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'NPB歴代データベース 全期間一括取込' -ForegroundColor Cyan
Write-Host '1936-2025年度成績 + 1950-2025試合結果'
python -m pip install -r requirements.txt
python full_import.py --from-year 1936 --to-year 2025
Read-Host '完了しました。Enterで終了'
