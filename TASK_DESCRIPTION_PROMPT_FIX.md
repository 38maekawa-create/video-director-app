# タスク指示書: 概要欄生成をプロンプト完結型に改修

> 作成: 2026-03-28 バティ（意識）
> 実行者: 右腕（Claude Code CLI / Opus 4.6）
> 対象WS: ~/AI開発10/

## 目的
概要欄生成の設計を「テンプレ結合はシステム側」から「プロンプトが全文を返す」に変更する。
LLMが毎回テンプレ固定部分を含む完全な概要欄全文を出力するようにし、description_writer.pyの結合処理を廃止する。

## 背景
- 現状: プロンプト282行に「テンプレ固定部分はdescription_writer.py側で付与するため不要」と書いてあり、LLMが動的部分のみ返すことがある
- 結果: メンイチさん等12件でテンプレ部分（CTA・運営者情報・SNSリンク）が欠落した概要欄がDBに入ってしまった
- なおとさんの設計意図: **概要欄の全責任をプロンプト（エージェント側）に集約する。システム側のテンプレ結合処理は不要。保守コスト・エラーリスクを最小化する**

## 全体工程における位置づけ
API安定化修正（TASK_API_SERVER_FIX.md）の完了後に実施。iOS側修正はCodex CLI（左腕）が完了済み。このタスクは概要欄の品質問題を修正する。

## 修正内容

### 修正1: prompts.py — DESCRIPTION_GENERATION_PROMPT を全面改修
ファイル: `src/video_direction/knowledge/prompts.py` 237行〜296行

**やること:**
1. 282行の矛盾する指示（「テンプレはdescription_writer.py側で付与するため不要」）を**削除**
2. テンプレート全文をプロンプト内にお手本として**丸ごと挿入**する。お手本は以下の `_fallback_description()` のフルテンプレート（description_writer.py 286行〜316行）をベースにする
3. プロンプトの指示を以下に変更:

```
【最重要】full_textには、以下のお手本と完全に同じ構成で、そのままYouTubeにコピペできる概要欄の全文を入れること。

テンプレート固定部分（CTA・チャンネル紹介・運営者情報・SNSリンク）は一字一句変えずにそのまま含めること。
AIが動画ごとに変えるのは以下の部分のみ:
- ゲスト紹介フック文（3〜5行。動画の核心を伝える導入文）
- タイムスタンプ（ハイライト情報から生成）
- ハッシュタグ（動画内容に合った5-10個）

full_textを空にすることは絶対に禁止。テンプレート固定部分が欠落した出力も禁止。
```

4. お手本の中で `{ゲスト紹介フック}` `{タイムスタンプ}` `{ハッシュタグ}` をプレースホルダーとして明示し、「ここだけAIが生成する」と指示する

5. 運営者情報テンプレートは**不動産カテゴリ（teko_realestate）と汎用カテゴリで異なる**。プロンプトに `{guest_category}` を渡し、カテゴリに応じた運営者情報を使うよう指示すること。2パターンの運営者情報全文は description_writer.py の234-283行にある

6. JSONスキーマも修正 — sectionsは不要。full_textのみでOK:
```json
{{
  "full_text": "テンプレ固定部分+動的部分を含む完全な概要欄全文（必須・空文字禁止）"
}}
```

### 修正2: description_writer.py — パース処理の簡素化
ファイル: `src/video_direction/analyzer/description_writer.py`

**やること:**
1. `generate_description()` のプロンプトformat呼び出し（74行）に `guest_category` パラメータを追加
2. `_parse_description_response()` を簡素化:
   - sectionsのパースを削除（full_textのみ取得）
   - full_textが空 or 200文字未満（テンプレ欠落の検知）の場合はフォールバックに回す
3. `_fallback_description()` はそのまま残す（LLM障害時のセーフティネット）

### 修正3: prompts.py の DESCRIPTION_GENERATION_PROMPT に guest_category 変数追加
- `<video_data>` セクション内に `- ゲストカテゴリ: {guest_category}` を追加
- 「ゲストカテゴリが teko_realestate の場合は不動産版運営者情報を、それ以外は汎用版を使うこと」と指示

## 完了条件と検証
1. `python -c "import ast; ast.parse(open('src/video_direction/knowledge/prompts.py').read())"` で構文チェック
2. `python -c "import ast; ast.parse(open('src/video_direction/analyzer/description_writer.py').read())"` で構文チェック
3. 修正後のプロンプトを目視確認: テンプレート全文がプロンプト内に含まれていること
4. 修正前→修正後の差分を明示的に記録
5. PROGRESS.md に修正完了を追記

## 禁止事項
- iOS側（Swift）ファイルには一切触れない
- タイトル生成（TITLE_GENERATION_PROMPT）には触れない
- _fallback_description() のテンプレート内容を変更しない（参照元として使うだけ）
- APIサーバーの再起動は行わない
- フォーマット以外の概要欄品質改善（フック文の品質向上等）はこのタスクのスコープ外
