import sqlite3
from pathlib import Path
DB=Path(__file__).parent/'npb.db'
indexes=[
'CREATE INDEX IF NOT EXISTS idx_players_name_kana ON players(name_kana)',
'CREATE INDEX IF NOT EXISTS idx_bg_player_date ON batting_game(player_id,game_id)',
'CREATE INDEX IF NOT EXISTS idx_pg_player_date ON pitching_game(player_id,game_id)',
'CREATE INDEX IF NOT EXISTS idx_gp_player_role ON game_players(player_id,role,game_id)',
'CREATE INDEX IF NOT EXISTS idx_events_batter_pitcher ON game_events(batter_id,pitcher_id,game_id)',
'CREATE INDEX IF NOT EXISTS idx_events_game_seq ON game_events(game_id,seq_no)',
'CREATE INDEX IF NOT EXISTS idx_games_source ON games(source_url)',
'CREATE INDEX IF NOT EXISTS idx_games_detail ON games(detail_url)',
'CREATE INDEX IF NOT EXISTS idx_games_box ON games(box_url)',
'CREATE INDEX IF NOT EXISTS idx_games_pbp ON games(pbp_url)',
'CREATE INDEX IF NOT EXISTS idx_pth_player_team_season ON player_team_history(player_id,team_id,season)',
]
with sqlite3.connect(DB) as c:
    for sql in indexes: c.execute(sql)
print('V7 indexes ready')
