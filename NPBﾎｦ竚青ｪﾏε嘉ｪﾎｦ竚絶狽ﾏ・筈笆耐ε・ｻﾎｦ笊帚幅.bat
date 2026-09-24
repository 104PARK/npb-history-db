@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
echo ================================================
echo NPB 試合詳細・出場選手・打撃投手・PBP 取込
 echo ================================================
%PY% migrate_v5.py
%PY% game_detail_importer.py range --from-year 2025 --to-year 2025
if errorlevel 1 pause & exit /b 1
echo.
echo 完了しました。
pause
