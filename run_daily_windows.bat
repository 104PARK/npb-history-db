@echo off
cd /d %~dp0
python -m pip install -r requirements.txt
python game_importer.py month --year %date:~0,4% --month %date:~5,2%
python importer.py rebuild-index
python validate.py
