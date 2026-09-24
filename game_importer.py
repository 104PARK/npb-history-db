"""Import NPB official regular-season schedule/result pages into games.

Sources:
  https://npb.jp/games/{year}/schedule_{month:02d}_detail.html

The parser is intentionally based on visible table structure rather than fixed
HTML element numbers. It stores the source URL and game-detail URL when NPB
provides one. It is resumable and safe to run repeatedly.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

ROOT=Path(__file__).parent
CFG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
DB=ROOT/CFG['db']; RAW=ROOT/CFG['raw_dir']; RAW.mkdir(exist_ok=True)
UA='NPB-History-DB/4.0 (research; local archival tool)'

ALIASES={
 '巨人':'読売ジャイアンツ','読売':'読売ジャイアンツ','G':'読売ジャイアンツ','ジャイアンツ':'読売ジャイアンツ',
 '阪神':'阪神タイガース','T':'阪神タイガース','タイガース':'阪神タイガース',
 'DeNA':'横浜DeNAベイスターズ','横浜DeNA':'横浜DeNAベイスターズ','DB':'横浜DeNAベイスターズ','DeNAベイスターズ':'横浜DeNAベイスターズ',
 '中日':'中日ドラゴンズ','D':'中日ドラゴンズ','ドラゴンズ':'中日ドラゴンズ',
 'ヤクルト':'東京ヤクルトスワローズ','東京ヤクルト':'東京ヤクルトスワローズ','S':'東京ヤクルトスワローズ','スワローズ':'東京ヤクルトスワローズ',
 '広島':'広島東洋カープ','広島東洋':'広島東洋カープ','C':'広島東洋カープ','カープ':'広島東洋カープ',
 'ソフトバンク':'福岡ソフトバンクホークス','福岡ソフトバンク':'福岡ソフトバンクホークス','H':'福岡ソフトバンクホークス','ホークス':'福岡ソフトバンクホークス',
 '西武':'埼玉西武ライオンズ','埼玉西武':'埼玉西武ライオンズ','L':'埼玉西武ライオンズ','ライオンズ':'埼玉西武ライオンズ',
 '日本ハム':'北海道日本ハムファイターズ','北海道日本ハム':'北海道日本ハムファイターズ','F':'北海道日本ハムファイターズ','ファイターズ':'北海道日本ハムファイターズ',
 'オリックス':'オリックス・バファローズ','B':'オリックス・バファローズ','バファローズ':'オリックス・バファローズ',
 'ロッテ':'千葉ロッテマリーンズ','千葉ロッテ':'千葉ロッテマリーンズ','M':'千葉ロッテマリーンズ','マリーンズ':'千葉ロッテマリーンズ',
 '楽天':'東北楽天ゴールデンイーグルス','東北楽天':'東北楽天ゴールデンイーグルス','E':'東北楽天ゴールデンイーグルス','イーグルス':'東北楽天ゴールデンイーグルス',
}

def db():
 c=sqlite3.connect(DB); c.execute('PRAGMA foreign_keys=ON'); return c

def fetch(url):
 req=Request(url,headers={'User-Agent':UA,'Accept-Language':'ja,en;q=0.8'})
 with urlopen(req,timeout=60) as r: return r.status,r.read()

def save_raw(url,status,data):
 h=hashlib.sha256(data).hexdigest(); p=RAW/(h+'.html');
 if not p.exists(): p.write_bytes(data)
 c=db(); c.execute('INSERT INTO raw_sources(url,sha256,fetched_at,http_status,local_path,bytes,parser_version) VALUES(?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET sha256=excluded.sha256,fetched_at=excluded.fetched_at,http_status=excluded.http_status,local_path=excluded.local_path,bytes=excluded.bytes,parser_version=excluded.parser_version',(url,h,date.today().isoformat(),status,str(p),len(data),'4.0')); c.commit(); c.close()

def clean(s): return re.sub(r'\s+','',str(s or '')).replace('　','')

def team_id(c,name,year):
 raw=str(name).strip(); key=clean(raw); canonical=ALIASES.get(raw,ALIASES.get(key,raw))
 # exact canonical/team name first
 row=c.execute('SELECT id FROM teams WHERE team_name=? OR canonical_name=?',(canonical,canonical)).fetchone()
 if row:return row[0]
 # aliases, including historical names already loaded
 rows=c.execute('SELECT team_id,alias FROM team_aliases').fetchall()
 for tid,alias in rows:
  if clean(alias)==key:return tid
 code='AUTO-'+hashlib.sha1(canonical.encode()).hexdigest()[:10]
 c.execute('INSERT OR IGNORE INTO teams(team_code,team_name,canonical_name,league,valid_from,valid_to,notes) VALUES(?,?,?,?,?,?,?)',(code,canonical,canonical,None,year,year,'auto-created by game importer'))
 tid=c.execute('SELECT id FROM teams WHERE team_code=?',(code,)).fetchone()[0]
 c.execute('INSERT OR IGNORE INTO team_aliases(team_id,alias,valid_from,valid_to) VALUES(?,?,?,?)',(tid,raw,year,year))
 return tid

def parse_score(s):
 s=clean(s)
 if s in ('ノーゲーム','中止','雨天中止','中断'):
  return None,None,s
 m=re.search(r'(\d+)\s*[-－]\s*(\d+)',s)
 if m:return int(m.group(1)),int(m.group(2)),None
 return None,None,s

def parse_date(s,year,month):
 m=re.search(r'\d{1,2}\s*/\s*(\d{1,2})',s)
 if not m:
  m=re.search(r'(\d{1,2})',s)
 if not m:return None
 return f'{year:04d}-{month:02d}-{int(m.group(1)):02d}'

def parse_month(year,month,html,url):
 soup=BeautifulSoup(html,'html.parser'); rows=[]
 for tr in soup.find_all('tr'):
  cells=tr.find_all(['th','td'],recursive=False)
  if len(cells)<2: continue
  date_txt=clean(cells[0].get_text(' ',strip=True))
  gd=parse_date(date_txt,year,month)
  if not gd: continue
  matchup=cells[1]
  chunks=[clean(x) for x in matchup.stripped_strings if clean(x)]
  # Most NPB rows are [home, score, away], repeated for multiple games in one cell.
  # If markup contains several score anchors, split around each anchor.
  anchors=[a for a in matchup.find_all('a') if re.search(r'\d+\s*[-－]\s*\d+|ノーゲーム|中止',a.get_text(' ',strip=True))]
  if anchors:
   for a in anchors:
    scoretxt=clean(a.get_text(' ',strip=True)); hs,as_,status=parse_score(scoretxt)
    prev=''; nxt=''
    # nearest meaningful strings around score anchor in the cell
    prevs=[]
    for node in a.previous_siblings:
     if getattr(node,'get_text',None): t=clean(node.get_text(' ',strip=True))
     else: t=clean(str(node))
     if t: prevs.append(t)
    nxts=[]
    for node in a.next_siblings:
     if getattr(node,'get_text',None): t=clean(node.get_text(' ',strip=True))
     else: t=clean(str(node))
     if t: nxts.append(t)
    prev=prevs[-1] if prevs else ''
    nxt=nxts[0] if nxts else ''
    # Team text may be adjacent to line-break nodes; fall back to chunk triplets.
    if prev and nxt and not re.search(r'[-－]',prev):
     home,away=prev,nxt
    else:
     home=away=''
     for i,x in enumerate(chunks):
      if x==scoretxt and i>0 and i+1<len(chunks): home,away=chunks[i-1],chunks[i+1]; break
    if home and away:
     venue=clean(cells[2].get_text(' ',strip=True)) if len(cells)>2 else ''
     href=a.get('href',''); detail=('https://npb.jp'+href if href.startswith('/') else href) if href else ''
     rows.append((gd,home,away,hs,as_,status,venue,detail))
  else:
   # Fallback: triplets from visible strings.
   i=0
   while i+2<len(chunks):
    hs,as_,status=parse_score(chunks[i+1])
    if hs is not None or status:
     venue=clean(cells[2].get_text(' ',strip=True)) if len(cells)>2 else ''
     rows.append((gd,chunks[i],chunks[i+2],hs,as_,status,venue,url)); i+=3
    else:i+=1
 return rows

def upsert_games(rows,source_url,year):
 c=db(); inserted=updated=skipped=0
 for gd,home,away,hs,as_,status,venue,detail in rows:
  if status in ('中止','雨天中止','中断'):
   # Preserve cancellation as a note only when both teams can be resolved.
   pass
  ht=team_id(c,home,year); at=team_id(c,away,year)
  source_id=(detail.split('/')[-1] if detail else '') or hashlib.sha1(f'{gd}|{home}|{away}|{venue}|{hs}|{as_}'.encode()).hexdigest()[:20]
  comp='セ・パ公式戦'
  notes=status or None
  existing=c.execute('SELECT id FROM games WHERE source_game_id=? ORDER BY id LIMIT 1',(source_id,)).fetchone()
  if existing:
   c.execute('UPDATE games SET game_date=?,season=?,competition=?,league=?,home_team_id=?,away_team_id=?,home_score=?,away_score=?,venue=?,notes=?,source_url=?,detail_url=? WHERE id=?',(gd,year,comp,None,ht,at,hs,as_,venue,notes,detail or source_url,detail or source_url,existing[0])); updated+=1
  else:
   c.execute('INSERT INTO games(source_game_id,game_date,season,phase,competition,league,home_team_id,away_team_id,home_score,away_score,venue,notes,source_url,detail_url) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(source_id,gd,year,'regular',comp,None,ht,at,hs,as_,venue,notes,detail or source_url,detail or source_url)); inserted+=1
 c.commit(); c.close(); return inserted,updated,skipped

def import_month(year,month):
 url=f'https://npb.jp/games/{year}/schedule_{month:02d}_detail.html'
 try:
  status,data=fetch(url); save_raw(url,status,data); rows=parse_month(year,month,data,url); ins,upd,skip=upsert_games(rows,url,year)
  c=db(); c.execute('INSERT INTO ingestion_log(run_started,run_finished,source_name,target_table,records_read,records_inserted,records_updated,records_skipped,status,message) VALUES(datetime(\'now\'),datetime(\'now\'),?,?,?,?,?,?,?,?)',('NPB公式試合日程・結果','games',len(rows),ins,upd,skip,'OK',url)); c.commit(); c.close()
  return len(rows),ins,upd
 except Exception as e:
  c=db(); c.execute('INSERT INTO ingestion_log(run_started,run_finished,source_name,target_table,records_read,records_inserted,records_updated,records_skipped,status,message) VALUES(datetime(\'now\'),datetime(\'now\'),?,?,?,?,?,?,?,?)',('NPB公式試合日程・結果','games',0,0,0,0,'ERROR',f'{url} :: {e}')); c.commit(); c.close(); print('ERROR',url,e); return 0,0,0
 finally: time.sleep(float(CFG.get('request_delay_seconds',1.0)))

def import_year(year,months=None):
 months=months or list(range(3,11))
 total=[0,0,0]
 for m in months:
  r=import_month(year,m); total=[a+b for a,b in zip(total,r)]; print(f'{year}-{m:02d}: read={r[0]} inserted={r[1]} updated={r[2]}')
 return tuple(total)

def main():
 ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
 y=sub.add_parser('year'); y.add_argument('--year',type=int,required=True); y.add_argument('--months',default='3-10')
 a=sub.add_parser('range'); a.add_argument('--from-year',type=int,default=1950); a.add_argument('--to-year',type=int,default=date.today().year)
 m=sub.add_parser('month'); m.add_argument('--year',type=int,required=True); m.add_argument('--month',type=int,required=True)
 ns=ap.parse_args()
 if ns.cmd=='month': print(import_month(ns.year,ns.month))
 elif ns.cmd=='year':
  a,b=map(int,ns.months.split('-')); print(import_year(ns.year,list(range(a,b+1))))
 else:
  for yy in range(ns.from_year,ns.to_year+1):
   # Modern NPB schedule pages are available for the two-league era; 1936-1949 require a different historical source.
   import_year(yy,list(range(3,11)) if yy<2026 else list(range(3,12)))
if __name__=='__main__': main()
