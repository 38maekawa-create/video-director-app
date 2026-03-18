# タスク指示書: Python API通信修正（Codex CLI / 左腕）

## 目的
3者体制通信監査で検出されたPython API側のCritical+Moderate問題を修正する。

## 背景
- cloudflaredで `video-api.legit-marc.com` 経由でlocalhost:8210を外部公開中（DNS設定完了済み）
- 外部公開状態でCORS `*`、レート制限なし、内部情報漏洩がある
- 監査レポート: `~/AI開発10/AUDIT_NETWORK_PYTHON.md`

## 修正内容（優先順位順）

### P0（即修正）
1. **CORS `*` を廃止** — `allow_origins` を明示列挙に変更。iOSネイティブはCORS不要なので、開発用ローカルオリジンのみ許可
   - 対象: `api_server.py:300-302`

2. **レート制限導入** — slowapiを使用。healthzは緩め(30/s)、生成系は厳しめ(5/min)
   - `pip install slowapi` が必要
   - 対象: `api_server.py`

3. **`/api/health` から `db_path` 削除** — 内部パス情報を返さない
   - 対象: `api_server.py:4354-4363`

4. **生例外文字列をクライアントに返さない** — `str(e)` をレスポンスに含めている箇所を全件修正。詳細はサーバーログへ、クライアントには一般化メッセージのみ
   - 対象: `api_server.py` 内の `raise HTTPException(500, str(e))` 等全箇所

### P1（修正推奨）
5. **`/healthz` + `/readyz` エンドポイント追加** — probe用の超軽量エンドポイント
   - `/healthz`: `{"status": "ok"}` のみ返す（DB不要）
   - `/readyz`: DB疎通確認付き

6. **SQLite `timeout` / `busy_timeout` 追加** — 全接続箇所に `timeout=10`, `PRAGMA busy_timeout=10000`, `PRAGMA journal_mode=WAL` を設定
   - 対象: `api_server.py:33-35`, `edit_assets_routes.py:32-35`

7. **共通エラーハンドラ追加** — HTTPExceptionと未処理例外の共通ハンドラで `{"error": {"code", "message", "retryable"}}` 形式に統一

## 完了条件
- [ ] CORS が `*` でないこと
- [ ] `/healthz` が200を返すこと
- [ ] `/api/health` のレスポンスに `db_path` が含まれないこと
- [ ] `str(e)` がレスポンスに露出していないこと（grep確認）
- [ ] slowapiのレート制限が有効なこと
- [ ] SQLite接続に timeout/busy_timeout が設定されていること
- [ ] APIサーバーが正常起動すること（uvicorn）
- [ ] 既存の機能が壊れていないこと

## 注意事項
- `api_server.py` は4,410行ある大規模ファイル。修正箇所以外には触らない
- APIサーバーは現在稼働中（port:8210）。修正後は `--reload` で自動反映される
- slowapiが未インストールの場合は `pip install slowapi` を実行すること

## 出力先
修正は直接コードに適用。完了後 `~/AI開発10/FIX_REPORT_PYTHON.md` に修正箇所一覧を出力。
