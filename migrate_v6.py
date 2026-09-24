import sqlite3
from pathlib import Path
DB=Path(__file__).parent/'npb.db'
with sqlite3.connect(DB) as c:
    for s in [
      'CREATE INDEX IF NOT EXISTS idx_bg_player_game ON batting_game(player_id,game_id)',
      'CREATE INDEX IF NOT EXISTS idx_pg_player_game ON pitching_game(player_id,game_id)',
      'CREATE INDEX IF NOT EXISTS idx_gp_game_player ON game_players(game_id,player_id)',
      'CREATE INDEX IF NOT EXISTS idx_events_batter ON game_events(batter_id,game_id)',
      'CREATE INDEX IF NOT EXISTS idx_events_pitcher ON game_events(pitcher_id,game_id)',
      'CREATE INDEX IF NOT EXISTS idx_psb_team_season ON player_season_batting(team_id,season)',
      'CREATE INDEX IF NOT EXISTS idx_psp_team_season ON player_season_pitching(team_id,season)',
      'CREATE INDEX IF NOT EXISTS idx_players_kana ON players(name_kana)'
    ]: c.execute(s)
print('V6 indexes ready')
