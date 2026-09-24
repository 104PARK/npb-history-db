"""Resumable staged importer for NPB History DB V7.

Profiles:
  core      = historical season pages + all players + games (1950+)
  expand    = core + game details for a chosen recent range
  details   = only game TOP/BOX/PBP for a chosen range
"""
from __future__ import annotations
import argparse, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).parent

def run(cmd):
    print('\n'+'='*78+'\n'+' '.join(cmd)+'\n'+'='*78,flush=True)
    p=subprocess.run(cmd,cwd=ROOT)
    if p.returncode:
        raise SystemExit(p.returncode)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--profile',choices=['core','expand','details'],default='core')
    ap.add_argument('--from-year',type=int,default=1936); ap.add_argument('--to-year',type=int,default=2025)
    ap.add_argument('--games-from-year',type=int,default=1950)
    ap.add_argument('--detail-from-year',type=int,default=2020); ap.add_argument('--detail-to-year',type=int,default=2025)
    ap.add_argument('--detail-limit',type=int,default=0)
    a=ap.parse_args(); py=sys.executable; start=time.time()
    if a.profile in ('core','expand'):
        run([py,'migrate_v7.py'])
        run([py,'importer.py','historical','--from-year',str(a.from_year),'--to-year',str(a.to_year)])
        run([py,'importer.py','players'])
        run([py,'game_importer.py','range','--from-year',str(max(a.games_from_year,a.from_year)),'--to-year',str(a.to_year)])
    if a.profile in ('expand','details'):
        run([py,'game_detail_importer.py','range','--from-year',str(a.detail_from_year),'--to-year',str(a.detail_to_year)]+(['--limit',str(a.detail_limit)] if a.detail_limit else []))
    run([py,'importer.py','rebuild-index']); run([py,'validate.py']); run([py,'migrate_v7.py'])
    print(f'\nV7 import finished in {time.time()-start:.1f}s')
if __name__=='__main__': main()
