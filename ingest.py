
"""
NPB official-data ingestion layer.

This script is deliberately conservative:
- downloads official NPB pages
- stores raw source HTML for audit
- extracts HTML tables with pandas.read_html
- records every run
- does not silently overwrite existing records

Install:
    pip install -r requirements.txt

Examples:
    python ingest.py historical --from-year 1936 --to-year 2025
    python ingest.py current --date 2026-09-23
    python ingest.py current --date today
"""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
import pandas as pd

ROOT=Path(__file__).parent
CFG=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
DB=ROOT/CFG["db"]; RAW=ROOT/CFG["raw_dir"]; RAW.mkdir(exist_ok=True)

def db():
    c=sqlite3.connect(DB); c.execute("PRAGMA foreign_keys=ON"); return c

def get(url):
    req=Request(url,headers={"User-Agent":"NPB-History-DB/1.0 research"})
    with urlopen(req,timeout=40) as r: return r.read()

def raw_save(url,data):
    key=hashlib.sha256(url.encode()).hexdigest()
    p=RAW/(key[:20]+".html")
    if not p.exists(): p.write_bytes(data)
    return str(p)

def log(source,target,read_,inserted,status,message):
    c=db()
    c.execute("""INSERT INTO ingestion_log(run_started,run_finished,source_name,target_table,
                 records_read,records_inserted,records_updated,records_skipped,status,message)
                 VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (datetime.now().isoformat(timespec="seconds"),
               datetime.now().isoformat(timespec="seconds"),source,target,
               read_,inserted,0,max(0,read_-inserted),status,message))
    c.commit();c.close()

def historical_urls(year):
    if year==1936:
        return [f"{CFG['official_base']}/bis/yearly/yakyuremmei_1936s.html",
                f"{CFG['official_base']}/bis/yearly/yakyuremmei_1936f.html"]
    if year==1937:
        return [f"{CFG['official_base']}/bis/yearly/yakyuremmei_1937s.html",
                f"{CFG['official_base']}/bis/yearly/yakyuremmei_1937f.html"]
    # NPB's pre-1950 historical pages use yakyuremmei; modern years are league pages.
    if year<=1949:
        return [f"{CFG['official_base']}/bis/yearly/yakyuremmei_{year}.html"]
    return [f"{CFG['official_base']}/bis/yearly/centralleague_{year}.html",
            f"{CFG['official_base']}/bis/yearly/pacificleague_{year}.html"]

def ingest_historical(y1,y2):
    for year in range(y1,y2+1):
        for url in historical_urls(year):
            try:
                data=get(url); raw_save(url,data)
                # Read all tables; future parser modules can map them by column signature.
                tables=pd.read_html(data)
                log("NPB公式年度別成績","raw_html",len(tables),0,"DOWNLOADED",url)
                print(year, len(tables), url)
            except Exception as e:
                log("NPB公式年度別成績","raw_html",0,0,"ERROR",str(e))
                print("ERROR",year,url,e)
            time.sleep(float(CFG["request_delay_seconds"]))

def current_url(d):
    return f"{CFG['official_base']}/bis/{d.year}/games/gm{d:%Y%m%d}.html"

def ingest_current(d):
    url=current_url(d)
    try:
        data=get(url); raw_save(url,data)
        tables=pd.read_html(data)
        log("NPB公式試合結果","games",len(tables),0,"DOWNLOADED",url)
        print(d,len(tables),url)
    except Exception as e:
        log("NPB公式試合結果","games",0,0,"ERROR",str(e))
        print("ERROR",d,url,e)

def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    h=sub.add_parser("historical");h.add_argument("--from-year",type=int,default=1936);h.add_argument("--to-year",type=int,default=2025)
    c=sub.add_parser("current");c.add_argument("--date",default="today")
    a=ap.parse_args()
    if a.cmd=="historical": ingest_historical(a.from_year,a.to_year)
    else:
        d=date.today() if a.date=="today" else date.fromisoformat(a.date)
        ingest_current(d)

if __name__=="__main__": main()
