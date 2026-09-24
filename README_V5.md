# NPB 歴代データベース Complete V5

## 今回の追加機能
- NPB公式の試合詳細 `/scores/.../` を起点に、1試合を1つの関連グラフとして扱う
- 試合TOP: 入場者、開始/終了時刻、勝敗/セーブ投手、関連URL
- 投打成績: `batting_game` / `pitching_game`
- 出場選手: `game_players`
- 試合経過: `game_events`（公式PBPの打席結果単位）
- すべての取得ページを `raw/` と `raw_sources` に保存
- 再実行可能なUPSERT方式

## 実行
### 1試合だけ
`python game_detail_importer.py game --game-id 123`

### 年度を一括
`python game_detail_importer.py range --from-year 2025 --to-year 2025`

### Windowsワンクリック
`NPB試合詳細取込.bat`

## 注意
NPB公式の「試合経過」は打席単位のプレーバイプレーです。1球ごとの球種・球速等を意味するピッチ単位PBPとは別物です。
1球単位を追加する場合は、別ソースを明示した別テーブルに分離します。

NPB公式サイトには試合TOP、投打成績、試合経過、ベンチ入り選手が分離して掲載されているため、それぞれを別URLとして保存し、DB上で `game_id` に紐付けています。
