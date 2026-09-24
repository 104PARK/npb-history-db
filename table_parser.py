from __future__ import annotations
import re
import pandas as pd

def norm(v):
    return re.sub(r'\s+','',str(v)).replace('▲','').replace('▼','').replace('－','-').replace('―','-').replace('−','-')

def flat(df):
    if isinstance(df.columns,pd.MultiIndex):
        df.columns=[''.join(str(x) for x in c if str(x)!='nan') for c in df.columns]
    else: df.columns=[str(c) for c in df.columns]
    return df

def find_col(df,cands):
    cols=list(df.columns)
    for c in cols:
        n=norm(c)
        for cand in cands:
            if cand in n:return c
    return None

def classify(df):
    df=flat(df.copy()); s='|'.join(norm(c) for c in df.columns)
    if any(x in s for x in ['勝率','ゲーム差']) and any(x in s for x in ['勝','敗']): return 'standings'
    if any(x in s for x in ['打率','打数','安打']) and any(x in s for x in ['本塁打','打点']): return 'batting'
    if any(x in s for x in ['防御率','投球回']) and any(x in s for x in ['勝','敗','奪三振']): return 'pitching'
    return 'other'

def parse_number(v):
    if v is None or pd.isna(v): return None
    s=norm(v).replace(',','')
    m=re.search(r'-?\d+(?:\.\d+)?',s)
    return float(m.group()) if m else None

def parse_int(v):
    x=parse_number(v); return None if x is None else int(x)

def parse_float(v):
    return parse_number(v)
