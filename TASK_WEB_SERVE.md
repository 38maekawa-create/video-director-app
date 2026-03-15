# タスク指示書: AI開発10 Webアプリ静的ファイルサーバー構築

## 目的
映像ディレクションシステムのWebアプリをPCブラウザから実用的に使えるようにする。
なおとさんが「PCからもなんの機能も使えない状況」と指摘しており、Webアプリをブラウザで開けるようにすることが最優先。

## 背景
- APIサーバー（FastAPI, port:8210）は既にlaunchdで自動起動・稼働中
- Webアプリ（app.js, index.html, styles.css）はAPIに接続する実装済み（MockData排除済み）
- しかし静的ファイルをHTTPサーバーで配信する仕組みがないため、ブラウザからアクセスできない
- ルートの `index.html` + `app.js` + `styles.css` + `data.js` が最新の本番化済みファイル

## 全体工程における位置づけ
- P1b（生産性UP開発）の一部。映像エージェント実用化の最初のステップ
- これが完了すると: PCブラウザで http://localhost:8211 を開くだけで映像ディレクションの全機能が使える
- 後続: TestFlight配布（Apple ID登録が必要）、品質スコア自動計算

## 完了条件と検証

### 実装内容
1. **FastAPIに静的ファイル配信を追加**（推奨アプローチ）
   - `api_server.py` に `StaticFiles` マウントを追加
   - `/` でルートの `index.html` を返す
   - `/app.js`, `/styles.css`, `/data.js` 等も配信
   - これならport 8210一本で API + Webアプリの両方が動く

   OR

2. **別途簡易HTTPサーバーをlaunchd登録**
   - `python3 -m http.server 8211 --directory ~/AI開発10/` をlaunchdで自動起動
   - port: 8211
   - `--bind 0.0.0.0` で外部アクセス可能に

### 検証方法
1. `curl http://localhost:8210/` （または8211）で index.html が返ること
2. ブラウザで開いてWebアプリが表示されること（スクリーンショットは不要、curlで確認OK）
3. Webアプリがapi_serverからデータを取得できること（API接続バナーが「緑」になること）
4. Mac2から `curl http://100.110.206.6:8210/` でアクセスできること

### 注意事項
- api_server.py が既にlaunchdで稼働中（PID 17171）。変更時はプロセス再起動が必要
- app.js の `API_BASE_URL` は `http://localhost:8210` のまま。Mac1上で配信するなら変更不要
- CORSは既にapi_serverで設定済みのはず（確認すること）
