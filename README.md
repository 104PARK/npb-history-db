# ⚾ NPB歴代データベース Complete V4

1936年から現在までを対象に、NPB公式の年度別成績・選手一覧・日別試合ページを取り込めるSQLite＋Streamlitアプリです。

## 今回の強化点
- 1936～1949年と1950年以降で異なるNPB公式URL体系を自動判定
- 1936年春・秋、1937年春・秋を別ページとして取得
- HTMLを `raw/` にSHA-256付きで保存し、SQLite `raw_sources` に出典を記録
- 年度別ページの表を「表番号」ではなく列構成から判定
- 順位表・個人打撃・個人投手を自動正規化
- 球団名・選手名をマスタに自動追加（旧球団も保持）
- 取込を年単位で再開可能
- 選手詳細画面、年度順位表、対戦検索、記録検索を追加
- `validate.py` でデータ品質チェック
- 2025年順位表はNPB公式ページを検証した初期データとして同梱

## 起動
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 歴代データ取込
最初はテストとして1年だけ実行してください。
```bash
python importer.py historical --from-year 2025 --to-year 2025
```
問題なければ全期間：
```bash
python importer.py historical --from-year 1936 --to-year 2025
```

選手マスタ：
```bash
python importer.py players
```

当日の試合ページ：
```bash
python importer.py current --date today
```

品質確認：
```bash
python validate.py
python coverage.py
```

## データの考え方
「ネット上のあらゆるデータ」を無差別にコピーするのではなく、一次資料であるNPB公式を中心に、利用条件が明確な公開データを補助的に統合する設計です。外部データを追加するときも `sources` と出典URLを残してください。

## 重要な注意
- 1936～1949年は現在のセ・パとは異なるため、リーグ名・大会区分を別管理します。
- 1936年は春・秋など複数の大会構成があるため、単純に「1936年レギュラーシーズン」と扱わないでください。
- 公式ページのHTML構造変更時は `table_parser.py` の列判定を更新してください。
- 本パッケージ同梱DBは「完成データ全部入り」ではありません。実データの大量取得は利用者PCで `importer.py` を実行する方式です。

## 外部公開データ
Nippon-Baseball-Data-Repository は選手試合成績、PBP、ロスター、スケジュール、順位表などの公開データをリリースしています。コードはMITライセンスで、データ利用時の表示条件は同リポジトリのライセンス記載に従ってください。

## V4: 全期間一括取込と試合結果自動登録

### Windowsで一括実行
フォルダ内の **`NPB全期間一括取込.bat`** をダブルクリックしてください。

自動で次を実行します。
1. 必要Pythonパッケージの確認・インストール
2. 1936～2025年のNPB公式「年度別成績」取得・正規化
3. NPB公式選手インデックス取得
4. 1950～2025年のNPB公式「試合日程・結果」を月単位で取得し、`games` テーブルへ登録
5. 選手検索用FTSインデックス再構築
6. データ品質チェック

途中で停止しても、同じBATをもう一度実行できます。既存行はキーで更新するため、原則として二重登録しません。

### 試合結果の取得方式
NPB公式の月別「試合日程・結果」ページを利用します。各試合にNPB側の試合詳細リンクがある場合は、そのURLも `games.source_url` に保存します。月別ページは日付・対戦カード・球場・開始時刻・責任投手等を掲載しています。

### 毎日更新
`run_daily_windows.bat` をタスクスケジューラへ登録すると、当月の公式試合結果を再取得して差分更新できます。

### 1936～1949年について
NPB公式の年度別成績ページは1936～1949年を「日本野球連盟」として別体系で掲載しています。1936年・1937年は春季／秋季など複数区分があります。そのため、年度成績は `importer.py` で取り込みます。一方、現行形式の月別試合日程ページとは構造が異なるため、1936～1949年の全試合については専用の歴史資料パーサーを別工程として追加する設計です。

### 主なコマンド
```text
python full_import.py --from-year 1936 --to-year 2025
python game_importer.py range --from-year 1950 --to-year 2025
python game_importer.py year --year 2025 --months 3-10
python game_importer.py month --year 2025 --month 9
python validate.py
```

## V5: 試合詳細の紐付け
`game_detail_importer.py` により、NPB公式の試合TOP / 投打成績 / 試合経過 / ベンチ入り選手を `game_id` に紐付けます。
- `games.detail_url / box_url / pbp_url / roster_url`
- `game_players`: 試合出場選手
- `batting_game`: 打撃成績
- `pitching_game`: 投手成績
- `game_events`: 打席単位の試合経過(PBP)

Windowsでは `NPB試合詳細取込.bat` または `NPB試合詳細取込_全期間.bat` を利用できます。
