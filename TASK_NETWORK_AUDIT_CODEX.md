# タスク指示書: Python API通信監査（Codex CLI / 左腕）

## 目的
iOS アプリのAPI通信が不安定（WiFi切断後に復帰しない、4G環境で接続できない等）。Python APIサーバー側の通信関連コードを全件監査し、問題を洗い出す。

## 背景
- APIサーバー: FastAPI（`src/video_direction/integrations/api_server.py` 4,410行）
- iOS→APIの接続経路: ローカルmDNS / Tailscale VPN / cloudflaredトンネル
- cloudflaredのDNS（video-api.legit-marc.com）が壊れている状態
- CORSがワイルドカード(*)の可能性 → セキュリティリスク

## 全体工程における位置づけ
3者体制通信監査の1/3。Swift側（右腕）、設計レビュー（副脳GPT-5.4）と並行実施。
完了後、3者の結果を統合して修正優先順位を決定する。

## 監査対象ファイル
1. `src/video_direction/integrations/api_server.py` — メインAPIサーバー
2. `src/video_direction/integrations/distributed_processor.py` — リモートMac連携
3. `src/video_direction/integrations/edit_assets_routes.py` — 手修正API
4. `~/.cloudflared/config.yml` — cloudflared設定

## 監査項目

### 1. CORS設定（重要度: Critical）
- `CORSMiddleware` の設定内容を確認
- `allow_origins` が `["*"]` なら問題。cloudflared経由で外部公開されているため
- 適切なオリジン制限の提案

### 2. エラーレスポンス設計
- APIエラー時のレスポンス形式は統一されているか
- HTTPステータスコードは適切か（404 vs 500の使い分け）
- エラーメッセージにスタックトレースや内部情報が漏れていないか

### 3. タイムアウト・接続管理
- FastAPIのリクエストタイムアウト設定
- DB接続のタイムアウト・コネクションプール設定
- LLM呼び出し（teko_core.llm）のタイムアウト設定

### 4. ヘルスチェックエンドポイント
- `/api/health` や `/health` エンドポイントは存在するか
- iOS側の `probeAndConnect()` は `/api/projects` で到達テストしている
- 軽量なヘルスチェック専用エンドポイントがあるべき

### 5. コマンドインジェクション
- `distributed_processor.py` の `dispatch_task()` でユーザー入力がSSH経由で実行される
- cloudflared経由で外部からアクセス可能な場合のリスク

### 6. レート制限
- APIにレート制限は設定されているか
- cloudflared経由で外部公開されている場合、DoS耐性はあるか

## 完了条件
1. 上記全項目の監査結果を `AUDIT_NETWORK_PYTHON.md` に出力
2. 各問題を Critical / Moderate / Minor に分類
3. 修正コードの具体案を含めること
4. 検査したファイル名・行番号を明記

## 出力先
`~/AI開発10/AUDIT_NETWORK_PYTHON.md`
