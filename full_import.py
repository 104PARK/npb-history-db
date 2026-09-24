"""One-command full importer for the NPB historical database.

Examples:
  python full_import.py
  python full_import.py --from-year 1950 --to-year 2026
  python full_import.py --skip-players

The process is resumable: each source page is upserted and every run is logged.
1936-1949 season/stat pages are imported by importer.py; official modern
schedule pages are used for game results from 1950 onward.
"""
from __future__ import annotations
import argparse, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).parent

def run(args):
 print('\n'+'='*72+'\n'+' '.join(args)+'\n'+'='*72,flush=True)
 p=subprocess.run(args,cwd=ROOT)
 if p.returncode!=0:
  print(f'FAILED: exit={p.returncode}',flush=True); return False
 return True

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--from-year',type=int,default=1936); ap.add_argument('--to-year',type=int,default=2025); ap.add_argument('--skip-players',action='store_true'); ap.add_argument('--skip-games',action='store_true'); ap.add_argument('--games-from-year',type=int,default=1950); ap.add_argument('--include-game-details',action='store_true'); ap.add_argument('--detail-from-year',type=int,default=2025); ap.add_argument('--detail-to-year',type=int,default=2025); ap.add_argument('--detail-limit',type=int,default=0)
 a=ap.parse_args(); py=sys.executable
 steps=[]
 steps.append([py,'importer.py','historical','--from-year',str(a.from_year),'--to-year',str(a.to_year)])
 if not a.skip_players: steps.append([py,'importer.py','players'])
 if not a.skip_games: steps.append([py,'game_importer.py','range','--from-year',str(max(a.games_from_year,a.from_year)),'--to-year',str(a.to_year)])
 if a.include_game_details:
  steps.append([py,'game_detail_importer.py','range','--from-year',str(a.detail_from_year),'--to-year',str(a.detail_to_year)]+(['--limit',str(a.detail_limit)] if a.detail_limit else []))
 steps += [[py,'importer.py','rebuild-index'],[py,'validate.py']]
 start=time.time()
 for cmd in steps:
  if not run(cmd): return 1
 print(f'\n完了: {time.time()-start:.1f}秒',flush=True)
 return 0
if __name__=='__main__': raise SystemExit(main())
