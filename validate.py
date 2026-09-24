import sqlite3, json
from datetime import datetime
from pathlib import Path
DB=Path(__file__).parent/'npb.db'
checks=[]
def chk(name,table,sql,severity='ERROR'):
 c=sqlite3.connect(DB); n=c.execute(sql).fetchone()[0]; c.close(); checks.append((name,severity,table,n))
chk('standings duplicate logical keys','standings','SELECT COUNT(*)-COUNT(DISTINCT season||"/"||league||"/"||team_id) FROM standings')
chk('games without date','games','SELECT COUNT(*) FROM games WHERE game_date IS NULL OR game_date=""')
chk('games missing teams','games','SELECT COUNT(*) FROM games WHERE home_team_id IS NULL OR away_team_id IS NULL')
chk('batting missing player','player_season_batting','SELECT COUNT(*) FROM player_season_batting WHERE player_id IS NULL')
chk('pitching missing player','player_season_pitching','SELECT COUNT(*) FROM player_season_pitching WHERE player_id IS NULL')
c=sqlite3.connect(DB)
for name,severity,table,n in checks:
 c.execute('INSERT INTO data_quality(checked_at,check_name,severity,table_name,issue_count,details) VALUES(?,?,?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),name,severity,table,n,'automated validation'))
c.commit(); c.close()
print(json.dumps([dict(check=n,severity=s,table=t,issues=i) for n,s,t,i in checks],ensure_ascii=False,indent=2))
