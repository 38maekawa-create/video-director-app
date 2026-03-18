# Python API通信監査レポート

対象:
- api_server.py
- distributed_processor.py
- edit_assets_routes.py
- config.yml

## 監査結果一覧

| 分類 | 項目 | 判定 |
|---|---|---|
| Critical | CORS | `allow_origins=["*"]` で外部公開 |
| Critical | レート制限 | 未実装 |
| Moderate | エラーレスポンス設計 | 形式不統一、生例外文字列露出あり |
| Moderate | 内部情報漏洩 | db_path、例外文字列、Vimeoレスポンスが露出 |
| Moderate | SQLite接続管理 | timeout/busy_timeout未設定 |
| Moderate | リクエストタイムアウト | サーバー全体の設計なし |
| Moderate | LLMタイムアウト | 120秒はモバイルAPIとして長い |
| Moderate | ヘルスチェック | `/api/health`が重く内部情報を返す |
| Moderate | コマンドインジェクション | dispatch_task()が任意コマンドSSH実行可能 |
| Minor | ステータスコード | 500/502/503/504の整理余地あり |

## 優先順位

### P0
- CORSの `*` を廃止
- レート制限導入
- `/api/health` から `db_path` 削除
- 生例外文字列をクライアントへ返さない

### P1
- `healthz` / `readyz` を追加
- iOSの疎通確認を `/api/projects` から `healthz` に変更
- SQLite `timeout` / `busy_timeout` 追加
- 500/502/503/504 の使い分け整理

### P2
- 長時間処理をジョブ化
- `distributed_processor.py` を task whitelist 方式へ変更
- 共通エラーレスポンス導入
