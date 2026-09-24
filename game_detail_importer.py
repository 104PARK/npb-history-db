"""Import NPB game detail, box score and play-by-play pages.

Pipeline:
  games.source_url (NPB /scores/.../) -> TOP/BOX/PBP
  TOP  -> game metadata, win/loss/save pitchers, attendance
  BOX  -> batting_game, pitching_game, game_players
  PBP  -> game_events

Designed for resumable local execution. NPB pages remain the primary source;
raw HTML is archived under raw/ and provenance is stored in raw_sources.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from bs4 import BeautifulSoup

ROOT=Path(__file__).parent
CFG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
DB=ROOT/CFG['db']; RAW=ROOT/CFG['raw_dir']; RAW.mkdir(exist_ok=True)
UA='NPB-History-DB/5.0 (local archival tool)'


def db():
    c=sqlite3.connect(DB); c.execute('PRAGMA foreign_keys=ON'); return c

def fetch(url):
    req=Request(url,headers={'User-Agent':UA,'Accept-Language':'ja,en;q=0.8'})
    with urlopen(req,timeout=60) as r: return r.status,r.read()

def save_raw(url,status,data):
    h=hashlib.sha256(data).hexdigest(); p=RAW/(h+'.html')
    if not p.exists(): p.write_bytes(data)
    c=db(); c.execute('''INSERT INTO raw_sources(url,sha256,fetched_at,http_status,local_path,bytes,parser_version)
        VALUES(?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET sha256=excluded.sha256,
        fetched_at=excluded.fetched_at,http_status=excluded.http_status,local_path=excluded.local_path,
        bytes=excluded.bytes,parser_version=excluded.parser_version''',
        (url,h,datetime.now().isoformat(timespec='seconds'),status,str(p),len(data),'5.0'))
    c.commit(); c.close(); return p

def clean(s): return re.sub(r'\s+','',str(s or '')).replace('　','')

def num(s):
    s=clean(s).replace(',','')
    m=re.search(r'-?\d+',s)
    return int(m.group()) if m else None

def real(s):
    s=clean(s).replace(',','')
    m=re.search(r'-?\d+(?:\.\d+)?',s)
    return float(m.group()) if m else None

def innings(s):
    s=clean(s)
    # NPB box score commonly displays 1, 2, 1/3, 2/3, etc.
    if not s: return None
    if re.fullmatch(r'\d+',s): return float(s)
    m=re.match(r'(\d+)\s*([0-2])/?3?$',s)
    if m: return int(m.group(1))+int(m.group(2))/3
    return real(s)

def player_from_anchor(c,a,season=None):
    if a is None: return None
    name=clean(a.get_text(' ',strip=True))
    if not name or name in ('選手','投手'): return None
    href=a.get('href','')
    # Stable NPB player code when exposed by the official page.
    code=None
    m=re.search(r'/bis/players/([^/?#]+)/?',href)
    if m: code=m.group(1)
    row=c.execute('SELECT id FROM players WHERE player_code=?',(code,)).fetchone() if code else None
    if row: pid=row[0]
    else:
        row=c.execute('SELECT id FROM players WHERE name=?',(name,)).fetchone()
        if row: pid=row[0]
        else:
            code=code or ('AUTO-'+hashlib.sha1(name.encode()).hexdigest()[:12])
            c.execute('INSERT OR IGNORE INTO players(player_code,name,source_url) VALUES(?,?,?)',(code,name,('https://npb.jp'+href) if href.startswith('/') else href or None))
            pid=c.execute('SELECT id FROM players WHERE player_code=?',(code,)).fetchone()[0]
    if href:
        full=('https://npb.jp'+href) if href.startswith('/') else href
        c.execute('UPDATE players SET source_url=COALESCE(source_url,?) WHERE id=?',(full,pid))
    return pid

def team_id(c,name,year):
    n=clean(name)
    row=c.execute('SELECT id FROM teams WHERE team_name=? OR canonical_name=?',(n,n)).fetchone()
    if row:return row[0]
    row=c.execute('SELECT team_id FROM team_aliases WHERE replace(alias,\' \' ,\'\')=?',(n,)).fetchone()
    return row[0] if row else None

def find_game(c,game_id):
    return c.execute('SELECT id,season,game_date,home_team_id,away_team_id,source_url,home_score,away_score FROM games WHERE id=?',(game_id,)).fetchone()

def detail_urls(top):
    base=top.rstrip('/')+'/'
    return base,base+'box.html',base+'playbyplay.html',base+'roster.html'

def text_between(soup,label):
    txt=' '.join(soup.stripped_strings)
    m=re.search(label+r'.{0,80}',txt)
    return m.group(0) if m else ''

def parse_top(game_id,season,data,url):
    soup=BeautifulSoup(data,'html.parser'); c=db()
    row=find_game(c,game_id)
    if not row: c.close(); return 0
    gid,_,_,_,_,_,_,_=row
    text=' '.join(soup.stripped_strings)
    attendance=None
    m=re.search(r'入場者\s*([\d,]+)人',text)
    if m: attendance=int(m.group(1).replace(',',''))
    start_time=end_time=duration=None
    m=re.search(r'開始\s*([0-9:]+)\s*◇終了\s*([0-9:]+)\s*◇試合時間\s*([0-9時間分]+)',text)
    if m: start_time,end_time,duration=m.groups()
    wp=lp=sp=None
    for label,target in [('勝投手','wp'),('敗投手','lp'),('セーブ','sp')]:
        m=re.search(label+r'\s*([^（]+)',text)
        if m:
            nm=clean(m.group(1));
            # use linked player if possible
            a=next((a for a in soup.find_all('a') if clean(a.get_text())==nm),None)
            pid=player_from_anchor(c,a,season) if a else None
            if not pid: pid=c.execute('SELECT id FROM players WHERE name=?',(nm,)).fetchone(); pid=pid[0] if pid else None
            if target=='wp': wp=pid
            elif target=='lp': lp=pid
            else: sp=pid
    c.execute('UPDATE games SET attendance=?,winning_pitcher_id=?,losing_pitcher_id=?,save_pitcher_id=?,detail_url=?,box_url=?,pbp_url=?,roster_url=?,start_time=?,end_time=?,game_duration=? WHERE id=?',
              (attendance,wp,lp,sp,url,detail_urls(url)[1],detail_urls(url)[2],detail_urls(url)[3],start_time,end_time,duration,gid))
    c.commit(); c.close(); return 1

def nearest_heading(table):
    node=table
    while node:
        prev=node.find_previous(['h4','h3'])
        if prev: return clean(prev.get_text(' ',strip=True))
        node=node.parent
    return ''

def stat_headers(table):
    rows=table.find_all('tr')
    if not rows:return []
    return [clean(x.get_text(' ',strip=True)) for x in rows[0].find_all(['th','td'])]

def row_cells(tr): return [clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'])]

def parse_box(game_id,season,data,url):
    soup=BeautifulSoup(data,'html.parser'); c=db(); g=find_game(c,game_id)
    if not g:c.close();return 0
    _,_,_,home_tid,away_tid,_,_,_=g; inserted=0
    # Each team section contains batting and pitching tables. The h4 preceding a table identifies the team.
    current_team=None
    for h4 in soup.find_all('h4'):
        ht=clean(h4.get_text(' ',strip=True))
        if ht in ('読売ジャイアンツ','阪神タイガース','横浜DeNAベイスターズ','広島東洋カープ','東京ヤクルトスワローズ','中日ドラゴンズ','福岡ソフトバンクホークス','北海道日本ハムファイターズ','千葉ロッテマリーンズ','東北楽天ゴールデンイーグルス','埼玉西武ライオンズ','オリックス・バファローズ'):
            current_team=team_id(c,ht,season)
        # tables until next h4
        for table in h4.find_all_next('table'):
            next_h4=table.find_previous('h4')
            if next_h4 != h4: break
            heads=stat_headers(table); head='|'.join(heads)
            trs=table.find_all('tr')[1:]
            if '打数' in head and '安打' in head and '打点' in head and '投球数' not in head:
                for tr in trs:
                    links=tr.find_all('a');
                    if not links: continue
                    pid=player_from_anchor(c,links[0],season); cells=row_cells(tr)
                    # Player table: order, position, player, AB, R, H, RBI, SB, inning results...
                    if len(cells)<8 or not pid or not current_team: continue
                    try:
                        order=num(cells[0]); ab=num(cells[3]); runs=num(cells[4]); hits=num(cells[5]); rbi=num(cells[6]); sb=num(cells[7])
                    except Exception: continue
                    plays=cells[8:]
                    doubles=sum('２' in x and '塁' in x for x in plays)
                    triples=sum('３' in x and '塁' in x for x in plays)
                    hrs=sum(('本' in x and ('越' in x or '塁' in x)) for x in plays)
                    walks=sum(('四球' in x or '故意四球' in x) for x in plays)
                    hbp=sum('死球' in x for x in plays)
                    ks=sum('三振' in x for x in plays)
                    c.execute('''INSERT INTO batting_game(game_id,player_id,team_id,batting_order,at_bats,runs,hits,doubles,triples,home_runs,rbi,walks,hit_by_pitch,strikeouts,stolen_bases)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(game_id,player_id) DO UPDATE SET team_id=excluded.team_id,
                        batting_order=excluded.batting_order,at_bats=excluded.at_bats,runs=excluded.runs,hits=excluded.hits,
                        doubles=excluded.doubles,triples=excluded.triples,home_runs=excluded.home_runs,rbi=excluded.rbi,
                        walks=excluded.walks,hit_by_pitch=excluded.hit_by_pitch,strikeouts=excluded.strikeouts,stolen_bases=excluded.stolen_bases''',
                        (game_id,pid,current_team,order,ab,runs,hits,doubles,triples,hrs,rbi,walks,hbp,ks,sb))
                    c.execute('''INSERT INTO game_players(game_id,player_id,team_id,role,batting_order,position,starter,source_url)
                        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(game_id,player_id,role) DO UPDATE SET team_id=excluded.team_id,
                        batting_order=excluded.batting_order,position=excluded.position,starter=excluded.starter,source_url=excluded.source_url''',
                        (game_id,pid,current_team,'batter',order,cells[1] if len(cells)>1 else None,1 if order is not None and cells[1].startswith('(') else 0,url))
                    inserted+=1
            elif '投球数' in head and '投球回' in head:
                for tr in trs:
                    links=tr.find_all('a');
                    if not links: continue
                    pid=player_from_anchor(c,links[0],season); cells=row_cells(tr)
                    if len(cells)<13 or not pid or not current_team: continue
                    # [result, pitcher, pitches, batters, IP, H, HR, BB, HBP, K, WP, BK, R, ER]
                    try:
                        ip=innings(cells[4]); h=num(cells[5]); hr=num(cells[6]); bb=num(cells[7]); hbp=num(cells[8]); k=num(cells[9]); r=num(cells[12]); er=num(cells[13]) if len(cells)>13 else None; pc=num(cells[2]); bf=num(cells[3])
                    except Exception: continue
                    c.execute('''INSERT INTO pitching_game(game_id,player_id,team_id,innings_pitched,batters_faced,hits_allowed,runs_allowed,earned_runs,walks,strikeouts,home_runs_allowed,pitch_count)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(game_id,player_id) DO UPDATE SET team_id=excluded.team_id,
                        innings_pitched=excluded.innings_pitched,batters_faced=excluded.batters_faced,hits_allowed=excluded.hits_allowed,
                        runs_allowed=excluded.runs_allowed,earned_runs=excluded.earned_runs,walks=excluded.walks,strikeouts=excluded.strikeouts,
                        home_runs_allowed=excluded.home_runs_allowed,pitch_count=excluded.pitch_count''',(game_id,pid,current_team,ip,bf,h,r,er,bb,k,hr,pc))
                    c.execute('''INSERT INTO game_players(game_id,player_id,team_id,role,position,starter,source_url)
                        VALUES(?,?,?,?,?,?,?) ON CONFLICT(game_id,player_id,role) DO UPDATE SET team_id=excluded.team_id,position=excluded.position,starter=excluded.starter,source_url=excluded.source_url''',
                        (game_id,pid,current_team,'pitcher','投手',1 if cells[0] in ('●','○','') and 'H' not in cells[0] and 'S' not in cells[0] else 0,url))
                    inserted+=1
    c.commit(); c.close(); return inserted

def parse_pbp(game_id,season,data,url):
    soup=BeautifulSoup(data,'html.parser'); c=db(); rows=[]; inning=0; half=None; outs=0
    # NPB PBP is a sequence of inning headings and result rows.
    for tr in soup.find_all('tr'):
        cells=row_cells(tr)
        if not cells: continue
        joined='|'.join(cells)
        if re.match(r'^\d+回[表裏]',cells[0]):
            m=re.match(r'^(\d+)回([表裏])',cells[0]); inning=int(m.group(1)); half=m.group(2); outs=0; continue
        if len(cells)>=5 and cells[0] in ('0アウト','1アウト','2アウト','3アウト'):
            before=int(cells[0][0]); outs=before
            batter_a=tr.find_all('a')
            batter_id=None; pitcher_id=None
            if batter_a: batter_id=player_from_anchor(c,batter_a[0],season)
            # first pitcher's link in current inning is not necessarily on every row; infer from pitcher column if present.
            event_text=cells[-1]
            rbi=len(re.findall(r'打点\s*\d+',event_text))
            runs=len(re.findall(r'生還|得点',event_text))
            rows.append((inning,half,before,batter_id,pitcher_id,'plate_appearance',event_text,rbi,runs))
    # Better parser using visible PBP lines: associate pitcher from '(先発投手)' row and each batter anchor.
    current_pitcher=None; inning=0; half=None
    for node in soup.find_all(['h4','tr']):
        txt=clean(node.get_text(' ',strip=True))
        m=re.match(r'^(\d+)回([表裏])',txt)
        if m: inning=int(m.group(1)); half=m.group(2); continue
        if '（先発投手）' in txt:
            a=node.find('a'); current_pitcher=player_from_anchor(c,a,season) if a else current_pitcher; continue
        if '投手交代' in txt or '投手変更' in txt:
            aa=node.find_all('a')
            if aa:
                current_pitcher=player_from_anchor(c,aa[-1],season)
            continue
        cells=row_cells(node)
        if len(cells)>=5 and re.match(r'^[0-2]アウト$',cells[0]):
            aa=node.find_all('a'); batter_id=player_from_anchor(c,aa[-1],season) if aa else None
            event_text=cells[-1]; before=int(cells[0][0]); rbi=len(re.findall(r'打点[0-9０-９]*',event_text))
            runs=1 if any(x in event_text for x in ('本塁生還','生還','得点')) else 0
            rows.append((inning,half,before,batter_id,current_pitcher,'plate_appearance',event_text,rbi,runs))
    # de-duplicate rows while preserving order
    seen=set(); clean_rows=[]
    for r in rows:
        key=(r[0],r[1],r[2],r[3],r[6])
        if key not in seen: seen.add(key); clean_rows.append(r)
    for seq,r in enumerate(clean_rows,1):
        c.execute('''INSERT INTO game_events(game_id,seq_no,inning,half,outs_before,batter_id,pitcher_id,event_type,event_text,rbi,runs_scored,source_url)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(game_id,seq_no) DO UPDATE SET inning=excluded.inning,half=excluded.half,
          outs_before=excluded.outs_before,batter_id=excluded.batter_id,pitcher_id=excluded.pitcher_id,event_type=excluded.event_type,
          event_text=excluded.event_text,rbi=excluded.rbi,runs_scored=excluded.runs_scored,source_url=excluded.source_url''',(game_id,seq,*r))
    c.commit(); c.close(); return len(clean_rows)

def enrich_batting_from_pbp(game_id):
    c=db()
    # Approximate PA from PBP rows; final official batting line remains authoritative for AB/H/R/RBI/SB.
    rows=c.execute('SELECT batter_id,COUNT(*) FROM game_events WHERE game_id=? AND batter_id IS NOT NULL GROUP BY batter_id',(game_id,)).fetchall()
    for pid,pa in rows: c.execute('UPDATE batting_game SET plate_appearances=? WHERE game_id=? AND player_id=?',(pa,game_id,pid))
    c.commit(); c.close()

def import_game(game_id,force=False):
    c=db(); row=find_game(c,game_id); c.close()
    if not row:return False
    _,season,_,_,_,top,_,_=row
    if not top or '/scores/' not in top: return False
    urls=detail_urls(top)
    for kind,url in zip(('top','box','pbp','roster'),urls):
        try:
            status,data=fetch(url); save_raw(url,status,data)
            if kind=='top': parse_top(game_id,season,data,url)
            elif kind=='box': parse_box(game_id,season,data,url)
            elif kind=='pbp':
                parse_pbp(game_id,season,data,url); enrich_batting_from_pbp(game_id)
        except Exception as e:
            print('ERROR',game_id,kind,url,e)
        time.sleep(float(CFG.get('request_delay_seconds',1.0)))
    return True

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    g=sub.add_parser('game'); g.add_argument('--game-id',type=int,required=True)
    r=sub.add_parser('range'); r.add_argument('--from-year',type=int,default=2025); r.add_argument('--to-year',type=int,default=2025); r.add_argument('--limit',type=int,default=0)
    ns=ap.parse_args(); c=db()
    if ns.cmd=='game': ids=[ns.game_id]
    else:
        ids=[x[0] for x in c.execute('SELECT id FROM games WHERE season BETWEEN ? AND ? AND source_url LIKE "https://npb.jp/scores/%" ORDER BY game_date,id'+(' LIMIT '+str(ns.limit) if ns.limit else ''),(ns.from_year,ns.to_year)).fetchall()]
    c.close()
    for i,gid in enumerate(ids,1):
        print(f'[{i}/{len(ids)}] game={gid}'); import_game(gid)

if __name__=='__main__': main()
