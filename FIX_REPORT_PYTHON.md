# Python APIサーバー 通信監査修正レポート

> 実施日: 2026-03-18
> 対象ファイル:
> - `src/video_direction/integrations/api_server.py`
> - `src/video_direction/integrations/edit_assets_routes.py`

## 修正サマリー

| # | 修正内容 | 状態 |
|---|---------|------|
| 1 | CORS `allow_origins=["*"]` 廃止 → localhost明示列挙 + 環境変数上書き | 完了 |
| 2 | `/api/health` レスポンスから `db_path` 削除 | 完了 |
| 3 | `/healthz`（軽量）・`/readyz`（DB疎通確認）エンドポイント追加 | 完了 |
| 4 | SQLite `timeout=10` + `PRAGMA busy_timeout=10000` 追加（両ファイル） | 完了 |
| 5 | 生例外文字列の露出防止（6箇所） | 完了 |
| 6 | 共通エラーハンドラ追加（HTTPException + 未処理Exception） | 完了 |

## 修正詳細

### 1. CORS修正
- **変更前**: `allow_origins=["*"]`（全オリジン許可）
- **変更後**: localhost/127.0.0.1のポート8210, 3000, 5173のみ明示列挙
- 環境変数 `API_ALLOW_ORIGINS`（カンマ区切り）で上書き可能

### 2. `/api/health` から `db_path` 削除
- レスポンスJSONの `db_path` キーを削除
- サーバー内部のファイルパスがクライアントに露出しなくなった

### 3. `/healthz` と `/readyz` エンドポイント追加
- `GET /healthz` → `{"status": "ok"}`（DB不要、超軽量）
- `GET /readyz` → DB `SELECT 1` で疎通確認、失敗時は503

### 4. SQLite timeout/busy_timeout 追加
- `api_server.py` の `_get_db()`: `sqlite3.connect(..., timeout=10)` + `PRAGMA busy_timeout=10000`
- `edit_assets_routes.py` の `_get_db()`: 同上
- WALモードは既設のため維持

### 5. 生例外文字列の露出防止（6箇所）
以下の箇所で `str(e)` や例外詳細をクライアントに返していたのを修正:

| 箇所 | 変更前 | 変更後 |
|------|--------|--------|
| スプレッドシートカテゴリ取得 | `f"...{e}"` | `logger.exception()` + 一般メッセージ |
| Vimeoトークン読み込み | `str(e)` | `logger.exception()` + `"Internal server error"` |
| モジュールimport失敗 | `f"...{e}"` | `logger.exception()` + `"Internal server error"` |
| ディレクション生成エラー | `f"...{e}"` | `logger.exception()` + `"Internal server error"` |
| Vimeo APIエラー（HTTPError） | `error_body[:200]` 含む | ステータスコードのみ返却、詳細はログへ |
| Vimeoコメント編集エラー | `str(e)` | `logger.exception()` + `"Internal server error"` |

### 6. 共通エラーハンドラ追加
- `@app.exception_handler(HTTPException)`: 統一JSON形式 `{"error": {"code", "message", "retryable"}}` で返却
- `@app.exception_handler(Exception)`: 未処理例外をキャッチ、`logger.exception()` でスタックトレースを記録、クライアントには一般メッセージのみ

### レスポンス統一フォーマット
```json
{
  "error": {
    "code": "HTTP_500",
    "message": "Internal server error",
    "retryable": true
  }
}
```

## 未実施（スキップ）
- slowapiによるレート制限: pip install が必要なため今回はスキップ

## 構文検証
- `api_server.py`: Python AST解析パス
- `edit_assets_routes.py`: Python AST解析パス
