# タスク指示書: 映像エージェント API サーバー側修正

> 作成: 2026-03-28 バティ（意識）
> 実行者: 右腕（Claude Code CLI / Opus 4.6）
> 対象WS: ~/AI開発10/

## 目的
映像エージェントのAPI接続が不安定（WiFi/モバイル両方でエラー、空レスポンス、繋がったり繋がらなかったり）。サーバー側の根本原因3つを修正する。

## 背景
- launchdでuvicornが `--reload` 付きで起動 → ポート多重競合でサーバー起動失敗
- api_server.py のJSONデコード失敗時に `pass` で握り潰し → 空レスポンスの原因
- SQLite busy_timeout が10秒で短い → DB競合でエラー

## 全体工程における位置づけ
iOS側（Swift）の修正はCodex CLI（左腕）が並行で実施済み/実施中。このタスクはサーバー側のみ。両方完了でAPI安定化が完成する。

## 修正内容（3箇所）

### 修正1: launchd plist から `--reload` 削除
- ファイル: `/Users/maekawanaoto/Library/LaunchAgents/com.maekawa.video-direction-api.plist`
- `--reload` フラグを削除する
- 本番環境では不要。これがポート競合の主原因

### 修正2: api_server.py JSONパース修正
- ファイル: `/Users/maekawanaoto/AI開発10/src/video_direction/integrations/api_server.py`
- 行454-455, 479-481 付近: `except: pass` → ログ出力 + None設定に変更
  ```python
  except json.JSONDecodeError as e:
      logger.warning(f"JSON decode failed for field: {e}")
      d[field_name] = None
  ```
- 行467-468 付近: `conn.close()` をデータ構築完了後に移動（fetchone直後ではなく、レスポンス生成完了後）

### 修正3: SQLite タイムアウト延長
- 同ファイル 行39-42 付近: `PRAGMA busy_timeout=10000` → `PRAGMA busy_timeout=30000`

## 完了条件と検証
1. 修正後に `python -c "import ast; ast.parse(open('src/video_direction/integrations/api_server.py').read())"` で構文チェック
2. launchd plistの変更後: `plutil -lint /Users/maekawanaoto/Library/LaunchAgents/com.maekawa.video-direction-api.plist` で構文チェック
3. 各修正箇所の前後差分を明示的に記録
4. PROGRESS.md に修正完了を追記

## 禁止事項
- iOS側（Swift）ファイルには一切触れない（左腕の担当）
- APIサーバーの再起動は行わない（なおとさん確認後に実施）
- 新機能の追加や「改善」は不要。上記3箇所のみ修正
