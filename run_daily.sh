#!/bin/sh
set -e
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
YEAR=$(date +%Y); MONTH=$(date +%m)
python3 game_importer.py month --year "$YEAR" --month "$MONTH"
python3 importer.py rebuild-index
python3 validate.py
