import sqlite3
from pathlib import Path
import pandas as pd
DB=Path(__file__).parent/'npb.db'

def conn():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def read(sql, params=()):
    with conn() as c:
        return pd.read_sql_query(sql,c,params=params)

def player_search(name='', position='', from_year=None, to_year=None, team=''):
    sql='''SELECT DISTINCT p.id,p.name,p.name_kana,p.position,p.bats,p.throws,p.debut_date,p.retirement_date,
                   MIN(CASE WHEN psb.season IS NOT NULL THEN psb.season ELSE psp.season END) first_stat_year,
                   MAX(CASE WHEN psb.season IS NOT NULL THEN psb.season ELSE psp.season END) last_stat_year
            FROM players p
            LEFT JOIN player_season_batting psb ON psb.player_id=p.id
            LEFT JOIN player_season_pitching psp ON psp.player_id=p.id
            LEFT JOIN teams t1 ON t1.id=psb.team_id LEFT JOIN teams t2 ON t2.id=psp.team_id
            WHERE 1=1'''
    par=[]
    if name:
        sql+=' AND (p.name LIKE ? OR COALESCE(p.name_kana,\'\') LIKE ? OR p.id IN (SELECT player_id FROM player_aliases WHERE alias LIKE ?))'; par += [f'%{name}%']*3
    if position: sql+=' AND p.position LIKE ?'; par.append(f'%{position}%')
    if from_year is not None: sql+=' AND (psb.season>=? OR psp.season>=?)'; par += [from_year,from_year]
    if to_year is not None: sql+=' AND (psb.season<=? OR psp.season<=?)'; par += [to_year,to_year]
    if team: sql+=' AND (t1.team_name LIKE ? OR t2.team_name LIKE ? OR t1.canonical_name LIKE ? OR t2.canonical_name LIKE ?)'; par += [f'%{team}%']*4
    sql+=' GROUP BY p.id ORDER BY p.name'
    return read(sql,par)

def player_profile(pid):
    info=read('SELECT * FROM players WHERE id=?',(pid,))
    if info.empty: return {}
    career_b=read('''SELECT COUNT(DISTINCT season) seasons, COALESCE(SUM(games),0) games,COALESCE(SUM(at_bats),0) at_bats,COALESCE(SUM(runs),0) runs,COALESCE(SUM(hits),0) hits,
                            COALESCE(SUM(doubles),0) doubles,COALESCE(SUM(triples),0) triples,COALESCE(SUM(home_runs),0) home_runs,COALESCE(SUM(rbi),0) rbi,
                            COALESCE(SUM(stolen_bases),0) stolen_bases,COALESCE(SUM(walks),0) walks,COALESCE(SUM(strikeouts),0) strikeouts
                     FROM player_season_batting WHERE player_id=?''',(pid,))
    career_p=read('''SELECT COUNT(DISTINCT season) seasons, COALESCE(SUM(games),0) games,COALESCE(SUM(wins),0) wins,COALESCE(SUM(losses),0) losses,COALESCE(SUM(saves),0) saves,
                            COALESCE(SUM(holds),0) holds,COALESCE(SUM(innings_pitched),0) innings_pitched,COALESCE(SUM(hits_allowed),0) hits_allowed,
                            COALESCE(SUM(earned_runs),0) earned_runs,COALESCE(SUM(walks),0) walks,COALESCE(SUM(strikeouts),0) strikeouts
                     FROM player_season_pitching WHERE player_id=?''',(pid,))
    teams=read('''SELECT DISTINCT t.team_name, MIN(y.season) first_year, MAX(y.season) last_year
                  FROM teams t JOIN (
                    SELECT team_id,season,player_id FROM player_season_batting WHERE player_id=?
                    UNION ALL SELECT team_id,season,player_id FROM player_season_pitching WHERE player_id=?
                    UNION ALL SELECT team_id,season,player_id FROM player_team_history WHERE player_id=?
                  ) y ON y.team_id=t.id WHERE y.player_id=? GROUP BY t.id ORDER BY first_year''',(pid,pid,pid,pid))
    return {'info':info,'career_batting':career_b,'career_pitching':career_p,'teams':teams}

def player_compare(a,b):
    """Return aligned career, season and team-history data for two players."""
    ids=(a,b)
    career=read('''WITH b AS (
        SELECT player_id,COUNT(DISTINCT season) seasons,SUM(games) games,SUM(at_bats) ab,SUM(hits) hits,
               SUM(home_runs) hr,SUM(rbi) rbi,SUM(runs) runs,SUM(stolen_bases) sb,SUM(walks) bb,SUM(strikeouts) so
        FROM player_season_batting WHERE player_id IN (?,?) GROUP BY player_id),
    p AS (
        SELECT player_id,COUNT(DISTINCT season) seasons_p,SUM(games) games_p,SUM(wins) wins,SUM(losses) losses,
               SUM(saves) saves,SUM(holds) holds,SUM(innings_pitched) ip,SUM(strikeouts) pso,SUM(earned_runs) er
        FROM player_season_pitching WHERE player_id IN (?,?) GROUP BY player_id)
    SELECT pl.id,pl.name,b.seasons,b.games,b.ab,b.hits,b.hr,b.rbi,b.runs,b.sb,b.bb,b.so,
           p.seasons_p,p.games_p,p.wins,p.losses,p.saves,p.holds,p.ip,p.pso,p.er
    FROM players pl LEFT JOIN b ON b.player_id=pl.id LEFT JOIN p ON p.player_id=pl.id WHERE pl.id IN (?,?) ORDER BY pl.id''',ids+ids+ids)
    seasons=read('''WITH years AS (SELECT DISTINCT season FROM player_season_batting WHERE player_id IN (?,?) UNION SELECT DISTINCT season FROM player_season_pitching WHERE player_id IN (?,?))
    SELECT y.season, p.id player_id,p.name,
      b.games batting_games,b.at_bats,b.hits,b.home_runs,b.rbi,b.batting_average,b.obp,b.slg,b.ops,
      x.games pitching_games,x.wins,x.losses,x.saves,x.holds,x.innings_pitched,x.strikeouts,x.era,x.whip
    FROM years y CROSS JOIN players p
    LEFT JOIN player_season_batting b ON b.player_id=p.id AND b.season=y.season
    LEFT JOIN player_season_pitching x ON x.player_id=p.id AND x.season=y.season
    WHERE p.id IN (?,?) AND (b.id IS NOT NULL OR x.id IS NOT NULL) ORDER BY y.season,p.id''',ids+ids+ids)
    teams=read('''SELECT p.id player_id,p.name,t.team_name,MIN(y.season) first_year,MAX(y.season) last_year
      FROM players p JOIN (
        SELECT player_id,team_id,season FROM player_season_batting WHERE player_id IN (?,?)
        UNION ALL SELECT player_id,team_id,season FROM player_season_pitching WHERE player_id IN (?,?)
        UNION ALL SELECT player_id,team_id,season FROM player_team_history WHERE player_id IN (?,?)
      ) y ON y.player_id=p.id JOIN teams t ON t.id=y.team_id WHERE p.id IN (?,?)
      GROUP BY p.id,t.id ORDER BY p.id,first_year''',ids+ids+ids+ids)
    return {'career':career,'seasons':seasons,'teams':teams}

def player_vs_player_games(a,b,from_year=None,to_year=None,limit=5000):
    """Games where both players appeared. If one is a pitcher and one batter, also exposes PBP rows connecting them."""
    sql='''SELECT DISTINCT g.id,g.game_date,g.season,ht.team_name home_team,at.team_name away_team,
             g.home_score,g.away_score,g.innings,g.venue,
             CASE WHEN EXISTS(SELECT 1 FROM batting_game x WHERE x.game_id=g.id AND x.player_id=? ) THEN 1 ELSE 0 END a_batted,
             CASE WHEN EXISTS(SELECT 1 FROM pitching_game x WHERE x.game_id=g.id AND x.player_id=? ) THEN 1 ELSE 0 END a_pitched,
             CASE WHEN EXISTS(SELECT 1 FROM batting_game x WHERE x.game_id=g.id AND x.player_id=? ) THEN 1 ELSE 0 END b_batted,
             CASE WHEN EXISTS(SELECT 1 FROM pitching_game x WHERE x.game_id=g.id AND x.player_id=? ) THEN 1 ELSE 0 END b_pitched
           FROM games g JOIN teams ht ON ht.id=g.home_team_id JOIN teams at ON at.id=g.away_team_id
           WHERE (EXISTS(SELECT 1 FROM game_players gp WHERE gp.game_id=g.id AND gp.player_id=? )
              OR EXISTS(SELECT 1 FROM batting_game bg WHERE bg.game_id=g.id AND bg.player_id=? )
              OR EXISTS(SELECT 1 FROM pitching_game pg WHERE pg.game_id=g.id AND pg.player_id=? ))
             AND (EXISTS(SELECT 1 FROM game_players gp WHERE gp.game_id=g.id AND gp.player_id=? )
              OR EXISTS(SELECT 1 FROM batting_game bg WHERE bg.game_id=g.id AND bg.player_id=? )
              OR EXISTS(SELECT 1 FROM pitching_game pg WHERE pg.game_id=g.id AND pg.player_id=? ))'''
    p=[a,a,b,b,a,a,a,b,b,b]
    if from_year is not None: sql+=' AND g.season>=?';p.append(from_year)
    if to_year is not None: sql+=' AND g.season<=?';p.append(to_year)
    sql+=' ORDER BY g.game_date DESC,g.id DESC LIMIT ?';p.append(limit)
    return read(sql,p)

def player_matchup_events(a,b,from_year=None,to_year=None,limit=5000):
    sql='''SELECT g.game_date,g.season,ht.team_name home_team,at.team_name away_team,e.inning,e.half,e.outs_before,
             p.name batter,pp.name pitcher,e.event_text,e.rbi,e.runs_scored,g.id game_id
           FROM game_events e JOIN games g ON g.id=e.game_id LEFT JOIN players p ON p.id=e.batter_id LEFT JOIN players pp ON pp.id=e.pitcher_id
           LEFT JOIN teams ht ON ht.id=g.home_team_id LEFT JOIN teams at ON at.id=g.away_team_id
           WHERE ((e.batter_id=? AND e.pitcher_id=?) OR (e.batter_id=? AND e.pitcher_id=?))'''
    par=[a,b,b,a]
    if from_year is not None: sql+=' AND g.season>=?';par.append(from_year)
    if to_year is not None: sql+=' AND g.season<=?';par.append(to_year)
    sql+=' ORDER BY g.game_date DESC,e.seq_no DESC LIMIT ?';par.append(limit)
    return read(sql,par)

def composite_games(season=None, team='', opponent='', venue='', competition='', min_runs=None, max_runs=None,
                    min_total_runs=None, result='', extra=None, no_hitter=False, perfect=False):
    sql='''SELECT g.id,g.game_date,g.season,g.phase,g.competition,g.league,
                  ht.team_name home_team,at.team_name away_team,g.home_score,g.away_score,g.innings,g.venue,
                  g.attendance,g.is_extra_innings,g.is_no_hitter,g.is_perfect_game,g.source_url
           FROM games g LEFT JOIN teams ht ON ht.id=g.home_team_id LEFT JOIN teams at ON at.id=g.away_team_id WHERE 1=1'''
    p=[]
    if season is not None: sql+=' AND g.season=?';p.append(season)
    if team: sql+=' AND (ht.team_name LIKE ? OR at.team_name LIKE ?)';p += [f'%{team}%',f'%{team}%']
    if opponent: sql+=' AND (ht.team_name LIKE ? OR at.team_name LIKE ?)';p += [f'%{opponent}%',f'%{opponent}%']
    if venue: sql+=' AND g.venue LIKE ?';p.append(f'%{venue}%')
    if competition: sql+=' AND g.competition LIKE ?';p.append(f'%{competition}%')
    if min_runs is not None: sql+=' AND (g.home_score>=? OR g.away_score>=?)';p += [min_runs,min_runs]
    if max_runs is not None: sql+=' AND (g.home_score<=? AND g.away_score<=?)';p += [max_runs,max_runs]
    if min_total_runs is not None: sql+=' AND COALESCE(g.home_score,0)+COALESCE(g.away_score,0)>=?';p.append(min_total_runs)
    if result=='extra': sql+=' AND g.is_extra_innings=1'
    if no_hitter: sql+=' AND g.is_no_hitter=1'
    if perfect: sql+=' AND g.is_perfect_game=1'
    if result=='home_win': sql+=' AND g.home_score>g.away_score'
    if result=='away_win': sql+=' AND g.away_score>g.home_score'
    if result=='tie': sql+=' AND g.home_score=g.away_score'
    sql+=' ORDER BY g.game_date DESC,g.id DESC'
    return read(sql,p)

def player_game_performance(pid, min_hits=None, min_hr=None, min_rbi=None, min_so=None, min_ip=None, min_pitch_so=None, year=None, opponent=''):
    sql='''SELECT g.id,g.game_date,g.season,ht.team_name home_team,at.team_name away_team,g.home_score,g.away_score,g.venue,
                  bg.at_bats,bg.hits,bg.home_runs,bg.rbi,bg.runs,bg.walks,bg.strikeouts batting_so,
                  pg.innings_pitched,pg.strikeouts pitching_so,pg.earned_runs,pg.hits_allowed,pg.walks pitching_bb
           FROM games g LEFT JOIN teams ht ON ht.id=g.home_team_id LEFT JOIN teams at ON at.id=g.away_team_id
           LEFT JOIN batting_game bg ON bg.game_id=g.id AND bg.player_id=?
           LEFT JOIN pitching_game pg ON pg.game_id=g.id AND pg.player_id=?
           WHERE (bg.player_id IS NOT NULL OR pg.player_id IS NOT NULL)'''
    p=[pid,pid]
    if min_hits is not None: sql+=' AND COALESCE(bg.hits,0)>=?';p.append(min_hits)
    if min_hr is not None: sql+=' AND COALESCE(bg.home_runs,0)>=?';p.append(min_hr)
    if min_rbi is not None: sql+=' AND COALESCE(bg.rbi,0)>=?';p.append(min_rbi)
    if min_so is not None: sql+=' AND COALESCE(bg.strikeouts,0)>=?';p.append(min_so)
    if min_ip is not None: sql+=' AND COALESCE(pg.innings_pitched,0)>=?';p.append(min_ip)
    if min_pitch_so is not None: sql+=' AND COALESCE(pg.strikeouts,0)>=?';p.append(min_pitch_so)
    if year is not None: sql+=' AND g.season=?';p.append(year)
    if opponent: sql+=' AND (ht.team_name LIKE ? OR at.team_name LIKE ?)';p += [f'%{opponent}%',f'%{opponent}%']
    sql+=' ORDER BY g.game_date DESC'
    return read(sql,p)

def head_to_head(a,b,from_year=None,to_year=None):
    sql='''SELECT g.game_date,g.season,ht.team_name home_team,at.team_name away_team,g.home_score,g.away_score,g.innings,g.venue
           FROM games g JOIN teams ht ON ht.id=g.home_team_id JOIN teams at ON at.id=g.away_team_id
           WHERE ((ht.team_name LIKE ? AND at.team_name LIKE ?) OR (ht.team_name LIKE ? AND at.team_name LIKE ?))'''
    p=[f'%{a}%',f'%{b}%',f'%{b}%',f'%{a}%']
    if from_year is not None:sql+=' AND g.season>=?';p.append(from_year)
    if to_year is not None:sql+=' AND g.season<=?';p.append(to_year)
    return read(sql+' ORDER BY g.game_date',p)

def record_summary(df):
    if df.empty:return {}
    return {'games':len(df),'home_wins':int((df.home_score>df.away_score).sum()),'away_wins':int((df.away_score>df.home_score).sum()),'ties':int((df.home_score==df.away_score).sum()),'runs':int((df.home_score.fillna(0)+df.away_score.fillna(0)).sum())}
