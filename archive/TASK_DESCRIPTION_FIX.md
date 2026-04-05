# タスク指示書: 概要欄生成バグ修正

## 目的
LLMレスポンスのfull_textが空の場合に既存の概要欄を空文字で上書きしてしまうバグを修正する。

## 背景
- Phase 5 QCレポートで29件中12件の概要欄が空文字列だった
- 原因調査完了（docs/DESCRIPTION_INVESTIGATION.md参照）
- 根本原因: プロンプト矛盾 + パースバリデーション欠如 + upsert無条件上書きの複合問題

## 全体工程における位置づけ
TASK_BATCH_REGEN.md（29件再バッチ生成）完了後に実施。修正後に概要欄のみ再生成が必要。

## 修正内容（3つ全て実施）

### 修正A: パース後バリデーション追加
**ファイル**: `src/video_direction/analyzer/description_writer.py` 103行付近
- `_parse_description_response()` の戻り値で `full_text` が空文字列の場合、フォールバック処理に回す
- フォールバック: テンプレートベースの概要欄生成（ゲスト名・タイトル・3行要約から構成）

### 修正B: プロンプト矛盾解消
**ファイル**: `src/video_direction/knowledge/prompts.py` 282行付近
- 「AIはハッシュタグとタイムスタンプのみ生成すればよい」の記述を削除 or 修正
- 「full_textにそのままコピペして使える全文を必ず入れること」を明確に最優先指示として配置

### 修正C: DB上書き防止
**ファイル**: `src/video_direction/integrations/api_server.py` 3338行付近
- `upsert_youtube_assets()` で `description_original` が空文字列の場合、既存値を保持する
- 空文字列 or None の場合は UPDATE句から除外

## 完了条件と検証
1. full_textが空のLLMレスポンスをモックしてもDBの既存概要欄が保持されること
2. 正常なfull_textのレスポンスでは従来通りDBに書き込まれること
3. プロンプト修正後、テスト的に2-3件で概要欄生成して全文が返ること
4. 既存テストが壊れないこと
