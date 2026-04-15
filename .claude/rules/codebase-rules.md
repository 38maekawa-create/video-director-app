# AI開発10 コードベースルール

> 兵隊（Claude Code CLI）が自動参照する。開発・修正時に必ず従うこと。

## LLM呼び出しルール

- **原則teko_core.llm経由**: LLMテキスト生成は `from teko_core.llm import ...` を使う。API直叩き禁止
- **モデル**: teko_core.llm経由の全モジュールは `model="opus"`（MAX定額内）
- **例外: Vision/音声系4モジュールのみAPI直叩き可**:
  - telop_checker.py — Anthropic API直叩き（Claude Sonnet）。Vision画像入力のため
  - frame_evaluator.py — Anthropic API直叩き（Claude Sonnet）。Vision画像入力のため
  - telop_reader.py — OpenAI API直叩き（GPT-4o Vision）。テロップ読み取り
  - whisper_transcriber.py — OpenAI API直叩き（Whisper）。音声文字起こし
- **プロンプトの動的注入**: prompts.py（344行）の構造を理解してから修正。変数名の意味を確認
- **品質基準の注入**: quality_knowledge_loader.py 経由で `.claude/rules/quality-judgment-guide.md` から読み込む。ハードコードしない

## FB承認フロー

- **事前承認制**: なおとさん/パグさんが各々承認してから編集者に流す
- **FBスタイル**: 1コメント1テーマ（複合FB分解は不要）
- **承認APIエンドポイント**: api_server.py 内の4エンドポイント
- **iOS承認画面**: VideoDirectorAgent 内の2View（FeedbackApprovalListView, FeedbackApprovalDetailView）+ 1ViewModel

## ルールベース分類（if文/Regexの領域）

以下はLLMではなくPythonルールベースで処理する。勝手にLLM化しない:
- ゲスト層分類（guest_classifier.py）
- 年収評価（income_evaluator.py）
- 固有名詞フィルタ（proper_noun_filter.py）
- ターゲットラベリング（target_labeler.py）
- コンテンツライン判定（quality_knowledge_loader.py の determine_content_line）

## DB操作

- SQLite: `.data/video_direction.db`, `.data/projects.db`, `.data/video_director.db`
- busy_timeout: 30秒（競合回避。変更するな）
- JSONパース: エラーハンドリング必須

## テスト

- pytest: `~/AI開発10/tests/`
- 変更後は `pytest tests/ -v` で全件通過を確認
- 2026-04-15時点: 1,417テスト

## 禁止事項

- prompts.py のプロンプト構造を大幅に変更すること（344行の動的注入が壊れる）
- quality_knowledge_loader.py を「もっとシンプルにできる」と書き直すこと（セクション抽出・コンテンツライン判定が必要）
- launchd plistの `--reload` オプションを追加すること（ポート多重競合の原因。過去に修正済み）
- distributed_processor.py を mission-dispatch.sh に統合すること（目的が違う。別物として維持）
