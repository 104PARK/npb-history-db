from pathlib import Path
from urllib.request import Request,urlopen
from datetime import datetime
import argparse,hashlib,time
ROOT=Path(__file__).parent; RAW=ROOT/"raw"; RAW.mkdir(exist_ok=True)
def fetch(url):
    req=Request(url,headers={"User-Agent":"NPB-Historical-DB/1.0 research"})
    return urlopen(req,timeout=30).read().decode("utf-8","replace")
def yearly_urls(y):
    if y==1936:return [f"https://npb.jp/bis/yearly/yakyuremmei_1936s.html",f"https://npb.jp/bis/yearly/yakyuremmei_1936f.html"]
    if y==1937:return [f"https://npb.jp/bis/yearly/yakyuremmei_1937s.html",f"https://npb.jp/bis/yearly/yakyuremmei_1937f.html"]
    if y<=1949:return [f"https://npb.jp/bis/yearly/yakyuremmei_{y}.html"]
    return [f"https://npb.jp/bis/yearly/{y}.html"]
def fetch_year(y):
    for url in yearly_urls(y):
        try:
            html=fetch(url); fn=RAW/(hashlib.sha256(url.encode()).hexdigest()[:16]+".html")
            fn.write_text(html,encoding="utf-8"); print("OK",y,url); time.sleep(.4)
        except Exception as e: print("ERROR",y,url,e)
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--from-year",type=int,default=1936);ap.add_argument("--to-year",type=int,default=datetime.now().year);ap.add_argument("--year",type=int)
    a=ap.parse_args()
    if a.year: fetch_year(a.year)
    else:
        for y in range(a.from_year,a.to_year+1): fetch_year(y)
