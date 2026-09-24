import sqlite3
from pathlib import Path
DB=Path(__file__).parent/'npb.db'
c=sqlite3.connect(DB)
cols={r[1] for r in c.execute('PRAGMA table_info(games)')}
for col,typ in [('detail_url','TEXT'),('box_url','TEXT'),('pbp_url','TEXT'),('roster_url','TEXT'),('start_time','TEXT'),('end_time','TEXT'),('game_duration','TEXT')]:
    if col not in cols: c.execute(f'ALTER TABLE games ADD COLUMN {col} {typ}')
ecols={r[1] for r in c.execute('PRAGMA table_info(game_events)')}
for col,typ in [('seq_no','INTEGER'),('source_url','TEXT')]:
    if col not in ecols: c.execute(f'ALTER TABLE game_events ADD COLUMN {col} {typ}')
c.execute('''CREATE TABLE IF NOT EXISTS game_players(id INTEGER PRIMARY KEY,game_id INTEGER NOT NULL,player_id INTEGER NOT NULL,team_id INTEGER,role TEXT,batting_order INTEGER,position TEXT,starter INTEGER DEFAULT 0,source_url TEXT,UNIQUE(game_id,player_id,role),FOREIGN KEY(game_id) REFERENCES games(id),FOREIGN KEY(player_id) REFERENCES players(id),FOREIGN KEY(team_id) REFERENCES teams(id))''')
c.execute('CREATE INDEX IF NOT EXISTS idx_game_players_game ON game_players(game_id)')
c.execute('CREATE INDEX IF NOT EXISTS idx_game_players_player ON game_players(player_id)')
c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_events_seq ON game_events(game_id,seq_no)')
c.commit(); c.close(); print('V5 migration complete')
