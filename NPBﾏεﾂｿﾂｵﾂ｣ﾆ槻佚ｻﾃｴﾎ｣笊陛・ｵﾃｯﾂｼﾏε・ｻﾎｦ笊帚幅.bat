@echo off
setlocal
cd /d %~dp0
chcp 65001 >nul

echo ================================================================
echo   NPB歴代データベース 全期間一括取込
echo ================================================================
echo.
echo 1936年から指定年度までの公式年度別データを取得し、
echo 1950年以降の公式試合結果を games テーブルへ登録します。
echo 初回は長時間かかる場合があります。途中で止めても再実行できます。
echo.
choice /C YN /M "開始しますか"
if errorlevel 2 exit /b 0

where py >nul 2>nul
if errorlevel 1 set PY=python
if not defined PY set PY=py

%PY% -m pip install -r requirements.txt
if errorlevel 1 goto :error

%PY% full_import.py --from-year 1936 --to-year 2025
if errorlevel 1 goto :error

echo.
echo ================================================================
echo   全期間一括取込が完了しました。
echo   npb.db と raw フォルダを確認してください。
echo ================================================================
pause
exit /b 0

:error
echo.
echo [ERROR] 取込中にエラーが発生しました。
echo ログは ingestion_log と画面のメッセージを確認してください。
pause
exit /b 1
