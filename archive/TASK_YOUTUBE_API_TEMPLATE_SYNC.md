# タスク指示書: YouTube Data API v3 連携 — 概要欄テンプレート自動同期

> 作成: 2026-03-29 バティ（意識）
> 実行者: 右腕（Claude Code CLI / Opus 4.6）
> 対象WS: ~/AI開発10/

## 目的
概要欄生成時に、YouTube Data API v3でTEKOチャンネルの最新投稿済み通常動画の概要欄を取得し、テンプレートの正本として使う。これにより、YouTube側でフォーマット変更（例: LINE→メルマガ）があった場合、次回生成から自動で反映される。

## 背景
- 現在はprompts.pyにハードコードされたテンプレートを使用 → YouTube側の変更が反映されない
- 実際にLINE→メルマガの変更があり、古いテンプレのまま生成されてしまった
- YouTube Data API v3のキーは設定済み（~/AI開発10/.env に YOUTUBE_API_KEY）
- チャンネルID: UCNEsgjVHvL4y0suJGwu8ZPg
- Shorts動画は概要欄フォーマットが異なるため除外が必要

## 全体工程における位置づけ
概要欄のプロンプト完結型改修（TASK_DESCRIPTION_PROMPT_FIX.md）の延長。テンプレートをハードコードからAPI取得に進化させる。

## 修正内容

### 修正1: YouTube API から最新の通常動画の概要欄を取得する関数を追加
ファイル: `src/video_direction/knowledge/loader.py` に追加

```python
def fetch_latest_description_template() -> str | None:
    """YouTube Data API v3でTEKOチャンネルの最新通常動画の概要欄を取得する。

    Shorts（タイトルに#shortsを含む or 概要欄が300文字未満）を除外し、
    最新の通常動画の概要欄をテンプレートとして返す。

    取得失敗時はNoneを返す（呼び出し側でフォールバック処理）。
    24時間キャッシュを使用してAPI呼び出し回数を削減する。
    """
```

**実装の要件:**
1. `.env` から `YOUTUBE_API_KEY` を読み込む（dotenv使用）
2. `search.list` でチャンネルの最新動画10件を取得（type=video, order=date）
3. `videos.list` で各動画のsnippet（description含む）を取得
4. Shorts判定: タイトルに `#shorts` を含む OR 概要欄が300文字未満 → 除外
5. 最初にヒットした通常動画の概要欄を返す
6. キャッシュ: `.cache/youtube_template.json` に保存（24時間有効）
7. API呼び出し失敗時・キー未設定時はNoneを返す（例外を投げない）
8. urllib.request を使用（外部ライブラリ依存を最小化）。URLパラメータは urllib.parse.urlencode でエンコードすること

### 修正2: description_writer.py で API取得テンプレートを優先使用
ファイル: `src/video_direction/analyzer/description_writer.py`

`generate_description()` の冒頭で:
1. `fetch_latest_description_template()` を呼び出す
2. 取得できた場合 → その概要欄からテンプレート固定部分（CTA・メルマガ・チャンネル紹介・運営者情報・SNSリンク）を抽出
3. 抽出した固定部分を `DESCRIPTION_GENERATION_PROMPT` の `{youtube_template}` 変数に注入
4. 取得できなかった場合 → 現在のハードコードテンプレートをそのまま使用（フォールバック）

### 修正3: prompts.py のテンプレート部分を変数化
ファイル: `src/video_direction/knowledge/prompts.py`

現在のハードコードされたお手本テンプレート部分を `{youtube_template}` 変数に置き換える:

```
【お手本テンプレート — 最新の投稿済み概要欄をベースにしたもの】
以下がそのまま使う概要欄の構成。ゲスト紹介フック、タイムスタンプ、ハッシュタグの3箇所だけAIが生成する。
テンプレート固定部分は一字一句変えないこと。

{youtube_template}
```

**重要**: ハードコードテンプレートは削除せず、description_writer.py内にフォールバック用として残すこと。

### 修正4: generate_description() のformat呼び出しに youtube_template を追加
`prompt = DESCRIPTION_GENERATION_PROMPT.format(...)` に `youtube_template=template_text` を追加。

## テンプレート抽出ロジック（修正2の詳細）

YouTube投稿済み概要欄から以下の構造を認識してテンプレートを組み立てる:
- **ゲスト紹介フック**: 先頭〜「チャンネル登録はこちらから」の前まで → `{{ゲスト紹介フック}}` に置換
- **タイムスタンプ**: 「▼タイムスタンプ▼」の後〜「━━━」の前まで → `{{タイムスタンプ}}` に置換
- **ハッシュタグ**: 「━━━」で囲まれた部分 → `{{ハッシュタグ}}` に置換
- **運営者情報**: 「【運営者情報】」〜 TEKO設立の行まで → `{{運営者情報}}` に置換（ゲストカテゴリによる分岐は維持）
- **それ以外**: テンプレート固定部分としてそのまま使用

## 完了条件と検証
1. `python3 -c "import ast; ast.parse(open('src/video_direction/knowledge/prompts.py').read())"` で構文チェック
2. `python3 -c "import ast; ast.parse(open('src/video_direction/analyzer/description_writer.py').read())"` で構文チェック
3. `python3 -c "import ast; ast.parse(open('src/video_direction/knowledge/loader.py').read())"` で構文チェック
4. API取得テスト: `python3 -c "from src.video_direction.knowledge.loader import fetch_latest_description_template; t = fetch_latest_description_template(); print(f'取得: {len(t) if t else 0}文字')"` が正常に動作すること
5. メンイチさん1件で再生成テスト: `python3 scripts/regenerate_descriptions.py --execute --project-id p-20260101-メンイチ --yes` が成功すること
6. 生成結果にメルマガCTA（「メールマガジン」）が含まれ、旧LINE CTA（「LINEで繋がり」）が含まれないことを確認
7. PROGRESS.md に修正完了を追記

## 禁止事項
- iOS側（Swift）ファイルには一切触れない
- タイトル生成（TITLE_GENERATION_PROMPT）には触れない
- ハードコードのフォールバックテンプレートを削除しない（API障害時のセーフティネット）
- APIサーバーの再起動は行わない
- YouTube Data API v3のクォータに注意（1日10,000ユニット。search.listは100ユニット/回、videos.listは1ユニット/回）
