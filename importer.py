"""Import NPB official HTML pages into the normalized SQLite database.

Usage:
  python importer.py historical --from-year 1936 --to-year 2025
  python importer.py players
  python importer.py current --date 2026-09-24
  python importer.py rebuild-index

The importer is resumable: URL hashes are stored in raw_sources and existing
rows are upserted using stable keys where available.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, time
from datetime import date,datetime
from pathlib import Path
from urllib.request import Request,urlopen
from bs4 import BeautifulSoup
import pandas as pd
from table_parser import classify,find_col,norm,parse_int,parse_float

ROOT=Path(__file__).parent; CFG=json.loads((ROOT/'config.json').read_text(encoding='utf-8')); DB=ROOT/CFG['db']; RAW=ROOT/CFG['raw_dir']; RAW.mkdir(exist_ok=True)
UA='NPB-History-DB/2.0 (research; contact via local project)'

def db():
 c=sqlite3.connect(DB); c.execute('PRAGMA foreign_keys=ON'); return c

def fetch(url):
 req=Request(url,headers={'User-Agent':UA,'Accept-Language':'ja,en;q=0.8'})
 with urlopen(req,timeout=60) as r: return r.status,r.read()

def save_raw(url,status,data):
 h=hashlib.sha256(data).hexdigest(); p=RAW/(h+'.html'); p.write_bytes(data)
 c=db(); c.execute('INSERT INTO raw_sources(url,sha256,fetched_at,http_status,local_path,bytes,parser_version) VALUES(?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET sha256=excluded.sha256,fetched_at=excluded.fetched_at,http_status=excluded.http_status,local_path=excluded.local_path,bytes=excluded.bytes,parser_version=excluded.parser_version',(url,h,datetime.now().isoformat(timespec='seconds'),status,str(p),len(data),'2.0')); c.commit(); c.close(); return p

def team_id(c,name,league=None,year=None):
 n=norm(name)
 if not n:return None
 rows=c.execute('SELECT id,team_name,canonical_name FROM teams').fetchall()
 for tid,tn,cn in rows:
  if n in (norm(tn),norm(cn)) or n==norm(tn).replace('東京',''):
   return tid
 row=c.execute('SELECT team_id FROM team_aliases WHERE replace(alias,\' \',\'\')=?',(n,)).fetchone()
 if row:return row[0]
 # create an era team if official source names it and no canonical mapping exists
 code=f"AUTO-{hashlib.sha1(n.encode()).hexdigest()[:10]}"
 c.execute('INSERT OR IGNORE INTO teams(team_code,team_name,canonical_name,league,valid_from,valid_to,notes) VALUES(?,?,?,?,?,?,?)',(code,str(name).strip(),str(name).strip(),league,year,year,'auto-created from official NPB page'))
 tid=c.execute('SELECT id FROM teams WHERE team_code=?',(code,)).fetchone()[0]
 c.execute('INSERT OR IGNORE INTO team_aliases(team_id,alias,valid_from,valid_to) VALUES(?,?,?,?)',(tid,str(name).strip(),year,year)); return tid

def player_id(c,name):
 n=str(name).strip(); n= re.sub(r'\s+','',n)
 if not n or n in ('選手','氏名','名前'): return None
 row=c.execute('SELECT id FROM players WHERE name=?',(n,)).fetchone()
 if row:return row[0]
 # Match common whitespace variant / exact alias
 row=c.execute('SELECT player_id FROM player_aliases WHERE alias=?',(n,)).fetchone()
 if row:return row[0]
 code='AUTO-'+hashlib.sha1(n.encode()).hexdigest()[:12]
 c.execute('INSERT OR IGNORE INTO players(player_code,name) VALUES(?,?)',(code,n)); return c.execute('SELECT id FROM players WHERE player_code=?',(code,)).fetchone()[0]

def upsert_standings(c,df,season,league):
 teamc=find_col(df,['チーム','球団']); gamec=find_col(df,['試合']); wc=find_col(df,['勝']); lc=find_col(df,['敗']); tc=find_col(df,['引分','引き分']); pc=find_col(df,['勝率']); gbc=find_col(df,['ゲーム差','差'])
 if not teamc or not wc or not lc:return 0
 ins=0
 for _,r in df.iterrows():
  t=str(r.get(teamc,'')); tid=team_id(c,t,league,season)
  if not tid:continue
  vals=(season,league,tid,parse_int(r.get(gamec)) if gamec else None,parse_int(r.get(wc)),parse_int(r.get(lc)),parse_int(r.get(tc)) if tc else 0,parse_float(r.get(pc)) if pc else None,None,parse_float(r.get(gbc)) if gbc else None)
  rank=1+c.execute('SELECT COUNT(*) FROM standings WHERE season=? AND league=? AND (games_behind < COALESCE(?,999999))',(season,league,vals[-1])).fetchone()[0] if vals[-1] is not None else None
  c.execute('INSERT INTO standings(season,league,team_id,games,wins,losses,ties,win_pct,rank,games_behind) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(season,league,team_id) DO UPDATE SET games=excluded.games,wins=excluded.wins,losses=excluded.losses,ties=excluded.ties,win_pct=excluded.win_pct,games_behind=excluded.games_behind',(vals[0],vals[1],vals[2],vals[3],vals[4],vals[5],vals[6],vals[7],rank,vals[9])); ins+=1
 return ins

def upsert_batting(c,df,season,league):
 pc=find_col(df,['選手','氏名','打者']); tc=find_col(df,['球団','チーム']); gc=find_col(df,['試合']); abc=find_col(df,['打数']); hc=find_col(df,['安打']); runc=find_col(df,['得点']); hrc=find_col(df,['本塁打']); rbic=find_col(df,['打点']); avgc=find_col(df,['打率']); sbc=find_col(df,['盗塁']); wkc=find_col(df,['四球']); ksc=find_col(df,['三振'])
 if not pc or not hc:return 0
 ins=0
 for _,r in df.iterrows():
  name=str(r.get(pc,'')); pid=player_id(c,name); tid=team_id(c,str(r.get(tc,'')),league,season) if tc else None
  if not pid:continue
  c.execute('INSERT INTO player_season_batting(season,player_id,team_id,games,at_bats,runs,hits,home_runs,rbi,stolen_bases,walks,strikeouts,batting_average) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(season,player_id,team_id) DO UPDATE SET games=excluded.games,at_bats=excluded.at_bats,runs=excluded.runs,hits=excluded.hits,home_runs=excluded.home_runs,rbi=excluded.rbi,stolen_bases=excluded.stolen_bases,walks=excluded.walks,strikeouts=excluded.strikeouts,batting_average=excluded.batting_average',(season,pid,tid,parse_int(r.get(gc)) if gc else None,parse_int(r.get(abc)) if abc else None,parse_int(r.get(runc)) if runc else None,parse_int(r.get(hc)),parse_int(r.get(hrc)) if hrc else None,parse_int(r.get(rbic)) if rbic else None,parse_int(r.get(sbc)) if sbc else None,parse_int(r.get(wkc)) if wkc else None,parse_int(r.get(ksc)) if ksc else None,parse_float(r.get(avgc)) if avgc else None)); ins+=1
 return ins

def upsert_pitching(c,df,season,league):
 pc=find_col(df,['選手','氏名','投手']); tc=find_col(df,['球団','チーム']); gc=find_col(df,['試合']); wc=find_col(df,['勝']); lc=find_col(df,['敗']); sc=find_col(df,['セーブ']); ip=find_col(df,['投球回']); h=find_col(df,['被安打']); er=find_col(df,['自責点']); so=find_col(df,['奪三振']); era=find_col(df,['防御率']); whip=find_col(df,['WHIP'])
 if not pc or not ip:return 0
 ins=0
 for _,r in df.iterrows():
  pid=player_id(c,str(r.get(pc,''))); tid=team_id(c,str(r.get(tc,'')),league,season) if tc else None
  if not pid:continue
  c.execute('INSERT INTO player_season_pitching(season,player_id,team_id,games,wins,losses,saves,innings_pitched,hits_allowed,earned_runs,strikeouts,era,whip) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(season,player_id,team_id) DO UPDATE SET games=excluded.games,wins=excluded.wins,losses=excluded.losses,saves=excluded.saves,innings_pitched=excluded.innings_pitched,hits_allowed=excluded.hits_allowed,earned_runs=excluded.earned_runs,strikeouts=excluded.strikeouts,era=excluded.era,whip=excluded.whip',(season,pid,tid,parse_int(r.get(gc)) if gc else None,parse_int(r.get(wc)) if wc else None,parse_int(r.get(lc)) if lc else None,parse_int(r.get(sc)) if sc else None,parse_float(r.get(ip)),parse_int(r.get(h)) if h else None,parse_int(r.get(er)) if er else None,parse_int(r.get(so)) if so else None,parse_float(r.get(era)) if era else None,parse_float(r.get(whip)) if whip else None)); ins+=1
 return ins

def ingest_year(year):
 urls=[]
 if year==1936: urls=[f"{CFG['official_base']}/bis/yearly/yakyuremmei_1936s.html",f"{CFG['official_base']}/bis/yearly/yakyuremmei_1936f.html"]
 elif year==1937: urls=[f"{CFG['official_base']}/bis/yearly/yakyuremmei_1937s.html",f"{CFG['official_base']}/bis/yearly/yakyuremmei_1937f.html"]
 elif year<=1949: urls=[f"{CFG['official_base']}/bis/yearly/yakyuremmei_{year}.html"]
 else: urls=[f"{CFG['official_base']}/bis/yearly/centralleague_{year}.html",f"{CFG['official_base']}/bis/yearly/pacificleague_{year}.html"]
 for url in urls:
  try:
   status,data=fetch(url); p=save_raw(url,status,data); dfs=pd.read_html(data); c=db(); total=0
   league='セ・リーグ' if 'centralleague_' in url else ('パ・リーグ' if 'pacificleague_' in url else '日本野球連盟')
   for df in dfs:
    kind=classify(df)
    if kind=='standings': total+=upsert_standings(c,df,year,league)
    elif kind=='batting': total+=upsert_batting(c,df,year,league)
    elif kind=='pitching': total+=upsert_pitching(c,df,year,league)
   c.commit(); c.close(); print(year,league,'tables=',len(dfs),'rows=',total)
  except Exception as e: print('ERROR',year,url,e)
  time.sleep(float(CFG.get('request_delay_seconds',1.0)))

def discover_player_urls():
 url=f"{CFG['official_base']}/bis/players/all/"; status,data=fetch(url); save_raw(url,status,data); soup=BeautifulSoup(data,'html.parser'); urls=set()
 for a in soup.find_all('a',href=True):
  h=a['href'];
  if '/bis/players/' in h and ('search' in h or 'player' in h): urls.add(('https://npb.jp'+h) if h.startswith('/') else h.split('#')[0])
 return sorted(urls)

def import_players():
 urls=discover_player_urls(); print('player index links',len(urls)); c=db(); n=0
 for url in urls:
  try:
   status,data=fetch(url); save_raw(url,status,data); soup=BeautifulSoup(data,'html.parser')
   text=' '.join(soup.stripped_strings)
   # Most index pages list names, debut years and current roster info; preserve names even when detail URL is not exposed.
   for a in soup.find_all('a',href=True):
    href=a['href']; label=''.join(a.stripped_strings).strip()
    if not label or '/bis/players/' not in href: continue
    if re.match(r'^[0-9A-Za-zぁ-んァ-ヶ一-龠．・\s\-\.]+$',label) and len(label)<=40:
     player_id(c,label)
   n+=1
   if n%20==0: c.commit(); print(n)
  except Exception as e: print('player error',url,e)
  time.sleep(float(CFG.get('request_delay_seconds',1.0)))
 c.commit(); c.close(); return len(urls)

def current(d):
 url=f"{CFG['official_base']}/bis/{d.year}/games/gm{d:%Y%m%d}.html"
 try:
  status,data=fetch(url); save_raw(url,status,data); print('saved',url,len(data))
 except Exception as e: print('ERROR',e)

def rebuild_fts():
 c=db(); c.execute("INSERT INTO players_fts(rowid,name,name_kana) SELECT id,name,COALESCE(name_kana,'') FROM players WHERE id NOT IN (SELECT rowid FROM players_fts)"); c.commit(); c.close()

def main():
 ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
 h=sub.add_parser('historical'); h.add_argument('--from-year',type=int,default=1936); h.add_argument('--to-year',type=int,default=2025)
 sub.add_parser('players'); cur=sub.add_parser('current'); cur.add_argument('--date',default='today'); sub.add_parser('rebuild-index')
 a=ap.parse_args()
 if a.cmd=='historical':
  for y in range(a.from_year,a.to_year+1): ingest_year(y)
 elif a.cmd=='players': import_players()
 elif a.cmd=='current': current(date.today() if a.date=='today' else date.fromisoformat(a.date))
 else: rebuild_fts()
if __name__=='__main__': main()
