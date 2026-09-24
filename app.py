import streamlit as st
import pandas as pd
from query_engine import read, player_search, player_profile, composite_games, player_game_performance, head_to_head, record_summary
st.set_page_config(page_title='NPB歴代データベース PRO',page_icon='⚾',layout='wide')
st.title('⚾ NPB歴代データベース PRO')
st.caption('選手・試合・球団・年度成績を横断して検索する複合条件検索エンジン')
menu=st.sidebar.radio('メニュー',['ダッシュボード','複合条件検索','選手検索','選手ページ','選手の試合実績','試合詳細','対戦成績','年度成績','記録検索'])

def game_link(df):
    if not df.empty:
        st.dataframe(df,use_container_width=True,hide_index=True)

if menu=='ダッシュボード':
    cols=st.columns(7)
    for col,t in zip(cols,['teams','players','games','game_events','batting_game','pitching_game','standings']):
        try:n=int(read(f'SELECT COUNT(*) n FROM {t}').iloc[0,0])
        except:n=0
        col.metric(t.replace('_',' '),f'{n:,}')
    st.subheader('データ期間')
    st.dataframe(read('''SELECT MIN(game_date) 開始,MAX(game_date) 最新,COUNT(*) 試合数 FROM games'''),hide_index=True,use_container_width=True)
    st.subheader('最近の試合')
    st.dataframe(read('''SELECT g.game_date 日付,ht.team_name ホーム,g.home_score,at.team_name ビジター,g.away_score,g.venue 球場
                         FROM games g LEFT JOIN teams ht ON ht.id=g.home_team_id LEFT JOIN teams at ON at.id=g.away_team_id ORDER BY g.game_date DESC LIMIT 20'''),hide_index=True,use_container_width=True)

elif menu=='複合条件検索':
    st.subheader('試合・成績 複合条件検索')
    c=st.columns(4); year=c[0].number_input('年度（0=指定なし）',0,2100,0); team=c[1].text_input('球団'); opp=c[2].text_input('相手球団'); venue=c[3].text_input('球場')
    c=st.columns(4); comp=c[0].text_input('大会'); min_runs=c[1].number_input('片側最低得点',0,100,0); total=c[2].number_input('両軍合計最低得点',0,200,0); result=c[3].selectbox('結果条件',['','home_win','away_win','tie','extra'])
    c=st.columns(2); nh=c[0].checkbox('ノーヒットノーラン'); pg=c[1].checkbox('完全試合')
    if st.button('検索',type='primary'):
        d=composite_games(year or None,team,opp,venue,comp,min_runs or None,None,total or None,result,False,nh,pg)
        s=record_summary(d); st.write(f"該当 {s.get('games',0):,}試合｜ホーム勝 {s.get('home_wins',0):,}｜ビジター勝 {s.get('away_wins',0):,}｜引分 {s.get('ties',0):,}｜総得点 {s.get('runs',0):,}")
        game_link(d)

elif menu=='選手検索':
    c=st.columns(4); name=c[0].text_input('選手名・よみ'); pos=c[1].selectbox('守備位置',['','投手','捕手','内野手','外野手']); fy=c[2].number_input('開始年',0,2100,0); ty=c[3].number_input('終了年',0,2100,0); team=st.text_input('所属球団')
    d=player_search(name,pos,fy or None,ty or None,team)
    st.write(f'該当 {len(d):,}人'); st.dataframe(d,use_container_width=True,hide_index=True)

elif menu=='選手ページ':
    ps=read('SELECT id,name FROM players ORDER BY name');
    if ps.empty: st.warning('選手データがありません'); st.stop()
    q=st.text_input('選手名を入力'); cand=ps[ps.name.str.contains(q,na=False)] if q else ps.head(1000); st.dataframe(cand,use_container_width=True,hide_index=True)
    if not cand.empty:
        pid=int(st.selectbox('選手を選択',cand.id.tolist(),format_func=lambda x: cand.loc[cand.id==x,'name'].iloc[0])); prof=player_profile(pid); info=prof['info'].iloc[0]
        st.header(info['name']); st.write({k:v for k,v in info.items() if pd.notna(v) and k!='id'})
        a,b,c=st.columns(3)
        cb=prof['career_batting'].iloc[0]; cp=prof['career_pitching'].iloc[0]
        a.metric('通算試合（打撃）',int(cb['games'] or 0)); b.metric('通算本塁打',int(cb['home_runs'] or 0)); c.metric('通算安打',int(cb['hits'] or 0))
        st.subheader('所属球団の履歴'); st.dataframe(prof['teams'],hide_index=True,use_container_width=True)
        x,y=st.tabs(['年度別打撃','年度別投手'])
        with x: st.dataframe(read('''SELECT b.season 年度,t.team_name 球団,b.games 試合,b.at_bats 打数,b.hits 安打,b.home_runs 本塁打,b.rbi 打点,b.stolen_bases 盗塁,b.batting_average 打率,b.obp 出塁率,b.slg 長打率,b.ops OPS FROM player_season_batting b LEFT JOIN teams t ON t.id=b.team_id WHERE b.player_id=? ORDER BY b.season''',(pid,)),use_container_width=True,hide_index=True)
        with y: st.dataframe(read('''SELECT p.season 年度,t.team_name 球団,p.games 試合,p.wins 勝,p.losses 敗,p.saves セーブ,p.holds ホールド,p.innings_pitched 投球回,p.strikeouts 奪三振,p.era 防御率,p.whip WHIP FROM player_season_pitching p LEFT JOIN teams t ON t.id=p.team_id WHERE p.player_id=? ORDER BY p.season''',(pid,)),use_container_width=True,hide_index=True)
        st.subheader('この選手の最近の出場試合'); st.dataframe(player_game_performance(pid).head(100),use_container_width=True,hide_index=True)

elif menu=='選手の試合実績':
    ps=read('SELECT id,name FROM players ORDER BY name'); q=st.text_input('選手名'); cand=ps[ps.name.str.contains(q,na=False)] if q else ps.head(300); 
    if not cand.empty:
        pid=int(st.selectbox('選手',cand.id.tolist(),format_func=lambda x:cand.loc[cand.id==x,'name'].iloc[0]))
        c=st.columns(6); year=c[0].number_input('年度',0,2100,0); hits=c[1].number_input('安打≧',0,10,0); hr=c[2].number_input('本塁打≧',0,10,0); rbi=c[3].number_input('打点≧',0,20,0); so=c[4].number_input('打撃三振≧',0,20,0); ip=c[5].number_input('投球回≧',0.0,20.0,0.0); pso=st.number_input('投手奪三振≧',0,30,0); opp=st.text_input('相手球団')
        d=player_game_performance(pid,hits or None,hr or None,rbi or None,so or None,ip or None,pso or None,year or None,opp); st.write(f'該当 {len(d):,}試合'); st.dataframe(d,use_container_width=True,hide_index=True)

elif menu=='試合詳細':
    gs=read('''SELECT g.id,g.game_date,ht.team_name home_team,at.team_name away_team,g.home_score,g.away_score,g.venue FROM games g LEFT JOIN teams ht ON ht.id=g.home_team_id LEFT JOIN teams at ON at.id=g.away_team_id ORDER BY g.game_date DESC LIMIT 10000''')
    if not gs.empty:
        gid=int(st.selectbox('試合',gs.id.tolist(),format_func=lambda x:(lambda r:f"{r.game_date}｜{r.home_team} {r.home_score}-{r.away_score} {r.away_team}｜{r.venue}")(gs.loc[gs.id==x].iloc[0])))
        top=read('''SELECT g.*,ht.team_name home_team,at.team_name away_team FROM games g LEFT JOIN teams ht ON ht.id=g.home_team_id LEFT JOIN teams at ON at.id=g.away_team_id WHERE g.id=?''',(gid,)).iloc[0]; st.header(f"{top.home_team} {top.home_score} - {top.away_score} {top.away_team}"); st.write({k:v for k,v in top.items() if pd.notna(v) and k not in ['id','home_team_id','away_team_id']})
        a,b,c=st.tabs(['出場・打撃','投手','PBP'])
        with a: st.dataframe(read('''SELECT t.team_name 球団,gp.batting_order 打順,gp.position 守備,p.name 選手,b.at_bats 打数,b.hits 安打,b.home_runs 本塁打,b.rbi 打点,b.walks 四球,b.strikeouts 三振 FROM game_players gp JOIN players p ON p.id=gp.player_id LEFT JOIN teams t ON t.id=gp.team_id LEFT JOIN batting_game b ON b.game_id=gp.game_id AND b.player_id=gp.player_id WHERE gp.game_id=? ORDER BY t.team_name,gp.batting_order''',(gid,)),use_container_width=True,hide_index=True)
        with b: st.dataframe(read('''SELECT t.team_name 球団,p.name 投手,x.innings_pitched 投球回,x.pitch_count 投球数,x.hits_allowed 被安打,x.walks 四球,x.strikeouts 奪三振,x.earned_runs 自責点 FROM pitching_game x JOIN players p ON p.id=x.player_id LEFT JOIN teams t ON t.id=x.team_id WHERE x.game_id=? ORDER BY t.team_name,x.id''',(gid,)),use_container_width=True,hide_index=True)
        with c: st.dataframe(read('''SELECT e.seq_no 順序,e.inning 回,e.half 表裏,e.outs_before アウト,p.name 打者,pp.name 投手,e.event_type 種別,e.event_text 結果,e.rbi 打点,e.runs_scored 得点 FROM game_events e LEFT JOIN players p ON p.id=e.batter_id LEFT JOIN players pp ON pp.id=e.pitcher_id WHERE e.game_id=? ORDER BY e.seq_no''',(gid,)),use_container_width=True,hide_index=True)

elif menu=='対戦成績':
    a,b=st.columns(2); A=a.text_input('球団A'); B=b.text_input('球団B'); c=st.columns(2); fy=c[0].number_input('開始年',0,2100,0); ty=c[1].number_input('終了年',0,2100,0)
    if A and B:
        d=head_to_head(A,B,fy or None,ty or None); s=record_summary(d); st.subheader(f'{A} vs {B}'); st.write(f"{s.get('games',0):,}試合｜A側表記の勝敗は開催地で異なるため、下表のスコアを基準に確認してください"); st.dataframe(d,use_container_width=True,hide_index=True)

elif menu=='年度成績':
    y=st.number_input('年度',1936,2100,2025); st.dataframe(read('''SELECT s.rank 順位,t.team_name 球団,s.games 試合,s.wins 勝,s.losses 敗,s.ties 分,s.win_pct 勝率,s.games_behind 差 FROM standings s JOIN teams t ON t.id=s.team_id WHERE s.season=? ORDER BY s.league,s.rank''',(y,)),use_container_width=True,hide_index=True)
    a,b=st.tabs(['打撃','投手'])
    with a: st.dataframe(read('''SELECT p.name 選手,t.team_name 球団,b.games 試合,b.hits 安打,b.home_runs 本塁打,b.rbi 打点,b.batting_average 打率,b.ops OPS FROM player_season_batting b JOIN players p ON p.id=b.player_id LEFT JOIN teams t ON t.id=b.team_id WHERE b.season=? ORDER BY b.ops DESC NULLS LAST''',(y,)),use_container_width=True,hide_index=True)
    with b: st.dataframe(read('''SELECT p.name 選手,t.team_name 球団,x.games 試合,x.wins 勝,x.saves セーブ,x.innings_pitched 投球回,x.strikeouts 奪三振,x.era 防御率,x.whip WHIP FROM player_season_pitching x JOIN players p ON p.id=x.player_id LEFT JOIN teams t ON t.id=x.team_id WHERE x.season=? ORDER BY x.era ASC NULLS LAST''',(y,)),use_container_width=True,hide_index=True)

elif menu=='記録検索':
    c=st.columns(5); hr=c[0].number_input('本塁打≧',0,10,0); hits=c[1].number_input('安打≧',0,10,0); rbi=c[2].number_input('打点≧',0,20,0); so=c[3].number_input('奪三振≧',0,30,0); ip=c[4].number_input('投球回≧',0.0,20.0,0.0)
    st.caption('選手の1試合成績を横断して検索します。'); ps=read('SELECT id,name FROM players ORDER BY name'); q=st.text_input('対象選手（空欄なら全員）'); cand=ps[ps.name.str.contains(q,na=False)] if q else ps
    if st.button('記録検索',type='primary'):
        rows=[]
        for _,r in cand.iterrows():
            d=player_game_performance(int(r.id),hits or None,hr or None,rbi or None,None,ip or None,so or None)
            if not d.empty: d.insert(0,'選手',r['name']); rows.append(d)
        st.dataframe(pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(),use_container_width=True,hide_index=True)
