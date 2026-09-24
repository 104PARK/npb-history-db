import sqlite3, json
from pathlib import Path
DB=Path(__file__).parent/'npb.db'
c=sqlite3.connect(DB)
out={}
for t in ['teams','players','games','game_events','player_season_batting','player_season_pitching','standings','championships']:
 out[t]=c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
out['seasons_loaded']=c.execute('SELECT COUNT(DISTINCT season) FROM standings').fetchone()[0]
out['min_season']=c.execute('SELECT MIN(season) FROM standings').fetchone()[0]
out['max_season']=c.execute('SELECT MAX(season) FROM standings').fetchone()[0]
print(json.dumps(out,ensure_ascii=False,indent=2)); c.close()
