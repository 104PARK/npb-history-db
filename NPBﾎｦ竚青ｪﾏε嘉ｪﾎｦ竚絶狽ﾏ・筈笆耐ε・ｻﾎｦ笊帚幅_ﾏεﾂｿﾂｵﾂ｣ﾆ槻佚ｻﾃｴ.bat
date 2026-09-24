@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
echo ========================================================
echo NPB 試合詳細・出場選手・打撃投手・PBP 全期間取込
echo 対象: 1950～2025年 / 途中停止後も再実行可能
echo ========================================================
%PY% migrate_v5.py
%PY% game_detail_importer.py range --from-year 1950 --to-year 2025
if errorlevel 1 pause & exit /b 1
echo.
echo 全期間の詳細取込が完了しました。
pause
