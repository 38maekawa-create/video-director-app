# SYSTEM_SPEC.md — 映像エージェント部署（AI開発10）

**最終更新**: 2026-04-15
**WS名称**: AI開発10（映像エージェント部署）
**運用状態**: Pythonバッチ稼働中 + Claude Code兵隊（Phase B-1整備完了・実機テスト未実施）
**launchd**: com.maekawa.video-direction-api（ポート8210、KeepAlive）

## 1. 部署ミッション

**映像作品の品質を追求し続ける自己成長型の映像エージェント部署。**

| 柱 | 内容 |
|----|------|
| 品質の追求 | 映像を「コンテンツ」ではなく「作品」として品質を見る。演出・テロップ・カット割り・BGM・構図まで |
| 自己成長 | FB学習・パターン認識で品質基準自体が進化する（feedback_learner: 2パターン2ルール蓄積、edit_learner: 2パターン2ルール蓄積） |
| 3つの機能体系 | ①ディレクションレポート自動生成（品質の再現性）②映像品質トラッキング（品質の可視化）③映像品質ナレッジベース（品質の蓄積・進化） |

## 2. 現在の運用

TEKO対談動画29件を対象に、ディレクションレポート・タイトル・概要欄・サムネ指示書を自動生成。
Python APIサーバー（FastAPI）+ iOS SwiftUIアプリ（TestFlight配布）で構成。

> 🔴 **二層構造（2026-04-15設計確定）**
> - **層1（Pythonバッチ）**: 29件一括再生成・launchd常駐APIサーバー・ルールベース分類・DB/API/iOS連携・FB学習
> - **層2（Claude Code兵隊）**: 個別動画の品質チェック・概要欄個別修正・バグ修正・新しい品質パターンの発見
> - **品質基準は `.claude/rules/` に一元化**。Python側もClaude Code兵隊も同じ正本を参照する。
> - 設計方針の詳細: `~/バティ/docs/video-agent-redesign-20260415.md`

## 3. ディレクトリ構造

```
~/AI開発10/
├── .claude/
│   ├── rules/                          ← 品質基準（兵隊自動参照 + Python参照）
│   │   ├── quality-judgment-guide.md   ← symlink → docs/QUALITY_JUDGMENT_GUIDE.md（正本は1つ）
│   │   ├── codebase-rules.md           ← AI開発10正本（LLM呼び出し・FB承認・設計確定事項）
│   │   └── naming-rules.md             ← AI開発10正本（Drive素材C番号ルール）
│   ├── skills/
│   │   └── video-qc/
│   │       └── SKILL.md               ← 兵隊用：個別動画QC+修正WF
│   └── launch.json
│
├── src/video_direction/                ← Python 25,737行・64モジュール（+ src/__init__.py）
│   ├── analyzer/                       ← 分析（teko_core.llm 4モジュール + 直叩き2モジュール）
│   │   ├── direction_generator.py (723行) ← Opus。演出ディレクション生成
│   │   ├── description_writer.py (603行)  ← Opus。概要欄生成
│   │   ├── title_generator.py (290行)     ← Opus。タイトル案生成
│   │   ├── thumbnail_designer.py (189行)  ← Opus。サムネ設計指示書
│   │   ├── guest_classifier.py            ← ルールベース。ゲスト層分類
│   │   ├── income_evaluator.py            ← ルールベース。年収評価
│   │   ├── proper_noun_filter.py          ← ルールベース。固有名詞フィルタ
│   │   ├── target_labeler.py              ← ルールベース。ターゲットラベリング
│   │   ├── telop_checker.py               ← Anthropic Sonnet直叩き。テロップ正確性チェック
│   │   ├── frame_evaluator.py             ← Anthropic Sonnet直叩き。フレーム品質評価
│   │   └── (他: audio_evaluator, clip_cutter 等)
│   ├── integrations/                   ← 外部連携・API
│   │   ├── api_server.py              ← FastAPI（ポート8210、launchd常駐）。Opus LLM呼び出し3箇所あり
│   │   ├── sheets_manager.py          ← Google Sheets API直叩き
│   │   ├── source_video_linker.py     ← Vimeo API直叩き
│   │   ├── auto_report_trigger.py     ← 新規動画検知→自動生成トリガー
│   │   ├── distributed_processor.py   ← 分散処理（mission-dispatch.shとは別物）
│   │   └── (他: editor_manager, knowledge_pages, notifier 等)
│   ├── knowledge/                      ← ナレッジ・プロンプト
│   │   ├── quality_knowledge_loader.py ← 品質基準ローダー（.claude/rules/ 参照）
│   │   ├── prompts.py (344行)          ← プロンプト本体（動的注入が複雑）
│   │   └── loader.py                  ← 汎用ローダー
│   ├── qc/                            ← 品質管理
│   │   ├── marketing_qc.py (339行)     ← Opus。マーケQC 2段階判定
│   │   ├── auto_qc_runner.py          ← 自動QCランナー（テロップ→マーケQCの統合パイプライン）
│   │   ├── telop_reader.py            ← OpenAI GPT-4o Vision直叩き。テロップ読み取り
│   │   ├── whisper_transcriber.py     ← OpenAI Whisper直叩き。音声文字起こし
│   │   └── (他: frame_extractor, qc_comparator)
│   ├── reporter/                       ← レポート出力
│   │   ├── html_generator.py          ← HTMLレポート生成
│   │   ├── publisher.py               ← GitHub Pages公開
│   │   └── template.py                ← テンプレート
│   └── tracker/                        ← トラッキング・FB学習
│       ├── feedback_learner.py         ← FB学習（2パターン2ルール蓄積）
│       ├── edit_learner.py             ← 編集学習（2パターン2ルール蓄積）
│       ├── video_tracker.py            ← 映像品質トラッキング
│       ├── quality_dashboard.py        ← 品質ダッシュボード
│       ├── video_analyzer.py            ← Opus。映像パターン分析（teko_core.llm経由）
│       ├── editing_feedback_converter.py ← Opus。FB変換（teko_core.llm経由）
│       └── (他: skill_matrix, video_learner 等)
│
├── VideoDirectorAgent/                 ← iOS SwiftUIアプリ（TestFlight Build 30）
├── docs/
│   ├── QUALITY_JUDGMENT_GUIDE.md (326行) ← 品質基準の正本
│   ├── teko_interview_direction_manual.md ← TEKOディレクションマニュアル
│   └── (他: API_REFERENCE, PHASE4_PLAN 等)
├── .data/                              ← ログ・DBファイル
│   ├── api-server.log / api-server-error.log
│   ├── video_direction.db / projects.db / video_director.db ← SQLite
│   ├── learning/                       ← FB学習データ
│   └── (他: audit/, editors/, frame_evaluations/)
├── output/                             ← 生成物出力先（cycle*_reports/, test_reports/ 等）
├── config.yaml                         ← システム設定
├── CLAUDE.md                           ← 部署行動マニュアル
├── PROGRESS.md                         ← 進捗管理
└── archive/                            ← 過去ログ（935行）
```

## 4. 外部連携

| 連携先 | モジュール | 方式 | 備考 |
|--------|-----------|------|------|
| Google Sheets | sheets_manager.py | API直叩き | 将来: Google Sheets MCP |
| Vimeo | source_video_linker.py | API直叩き | 将来: Vimeo MCP |
| YouTube Data API v3 | loader.py | API直叩き | 概要欄テンプレート取得（24hキャッシュ） |
| AI開発5（動画ナレッジ） | ai_dev5_connector.py | ファイル参照 | 文字起こしデータ取得 |
| Anthropic LLM | teko_core.llm経由 | API | 直叩き禁止。全てteko_core.llm経由（model="opus"） |
| Anthropic API直叩き | telop_checker.py, frame_evaluator.py | API | Vision画像入力のためSonnetで直叩き |
| OpenAI API（GPT-4o Vision） | telop_reader.py | API | テロップ読み取り |
| OpenAI API（Whisper） | whisper_transcriber.py | API | 音声文字起こし |

## 5. launchd常駐サービス

| サービス | Label | 状態 |
|----------|-------|------|
| APIサーバー | com.maekawa.video-direction-api | ✅ 稼働中（uvicorn, ポート8210, KeepAlive） |
| 監査ランナー | com.maekawa.video-direction-audit | ⏸ 確認必要 |

## 6. データベース

| DB | パス | 内容 |
|----|------|------|
| video_director.db | .data/ | メインDB（大半のモジュールが参照。対談データ・FB・承認） |
| video_direction.db | .data/ + ルート | 生成物DB（ディレクションレポート・概要欄） |
| projects.db | .data/ | プロジェクト管理 |

## 7. 品質基準の一元化

```
docs/QUALITY_JUDGMENT_GUIDE.md（正本・326行）
  ↑ symlink
.claude/rules/quality-judgment-guide.md
  ↑ 参照                    ↑ 自動ロード
quality_knowledge_loader.py   Claude Code兵隊
```

- **正本は1つ（docs/QUALITY_JUDGMENT_GUIDE.md）。更新は1箇所で完結。**
- Python側: quality_knowledge_loader.py の DEFAULT_GUIDE_PATH が .claude/rules/ を参照
- Claude Code兵隊: rules/ に自動ロードされて品質基準を常に把握

## 8. 設計確定事項

- FB承認フロー: 事前承認制（なおとさん/パグさんが各々承認してから編集者に流す）
- FBスタイル: 1コメント1テーマ（複合FB分解は不要）
- LLM呼び出し: テキスト生成は全てteko_core.llm経由（API直叩き禁止）。Vision/音声系4モジュールのみ例外（§4参照）
- 概要欄テンプレート: YouTube API取得→24hキャッシュ→プロンプト注入（フォールバック: ハードコード）
- 層分類: QUALITY_JUDGMENT_GUIDE.md セクション1に準拠（層a/b/c + 年収演出ON/OFF/別基準）
- Drive素材命名: C番号昇順で連番（_1, _2）。「短尺」禁止

## 9. バティWSとの関係

- **ディレクション**: バティがタスク投入（タスク指示書配置 or サブエージェント起動）
- **品質基準の正本**: docs/QUALITY_JUDGMENT_GUIDE.md（このWS内。バティWSにはない）
- **品質判断の引き継ぎ**: バティ growth/judgment-patterns.md #36, #39, #40 が本WSに関連
- **設計ドキュメント**: `~/バティ/docs/video-agent-redesign-20260415.md`

## 10. 既知の問題

| # | 問題 | 状態 |
|---|------|------|
| 1 | edit_learnerのデータ量が少ない（2パターン2ルール） | ⚠️ データ蓄積が必要。Supabase移行の前提 |
| 2 | 概要欄未生成38% | ⏳ 原因調査必要 |
| 3 | Vimeo未マッチ16名 | 待ち（編集完了後に自動マッチ） |
| 4 | .gitが131MB（バイナリ履歴） | P3 |
| 5 | チャンネル移行（退職者Googleアカウント問題） | 👤 なおとさん→事務待ち |
