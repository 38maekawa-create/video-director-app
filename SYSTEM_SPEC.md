# SYSTEM_SPEC.md — 映像エージェント部署（AI開発10）

**最終更新**: 2026-04-15
**WS名称**: AI開発10（映像エージェント部署）
**運用状態**: 二層構造で稼働中（Pythonバッチ + Claude Code兵隊）
**launchd**: com.maekawa.video-direction-api（ポート8210、KeepAlive）

## 1. 部署概要

TEKO対談動画29件のディレクションレポート・タイトル・概要欄・サムネ指示書を自動生成するシステム。
Python APIサーバー（FastAPI）+ iOS SwiftUIアプリ（TestFlight配布）で構成。

> 🔴 **二層構造（2026-04-15設計確定）**
> - **層1（Pythonバッチ）**: 29件一括再生成・launchd常駐APIサーバー・ルールベース分類・DB/API/iOS連携・FB学習
> - **層2（Claude Code兵隊）**: 個別動画の品質チェック・概要欄個別修正・バグ修正・新しい品質パターンの発見
> - **品質基準は `.claude/rules/` に一元化**。Python側もClaude Code兵隊も同じ正本を参照する。
> - 設計方針の詳細: `~/バティ/docs/video-agent-redesign-20260415.md`

## 2. ディレクトリ構造

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
├── src/video_direction/                ← Python 25,737行・65モジュール
│   ├── analyzer/                       ← 分析（LLM呼び出し5モジュール含む）
│   │   ├── direction_generator.py (723行) ← Sonnet。演出ディレクション生成
│   │   ├── description_writer.py (603行)  ← Sonnet。概要欄生成
│   │   ├── title_generator.py (80+行)     ← Claude。タイトル案生成
│   │   ├── thumbnail_designer.py (80+行)  ← Claude。サムネ設計指示書
│   │   ├── marketing_qc.py (339行)        ← Opus。マーケQC 2段階判定
│   │   ├── guest_classifier.py            ← ルールベース。ゲスト層分類
│   │   ├── income_evaluator.py            ← ルールベース。年収評価
│   │   ├── proper_noun_filter.py          ← ルールベース。固有名詞フィルタ
│   │   ├── target_labeler.py              ← ルールベース。ターゲットラベリング
│   │   └── (他: audio_evaluator, clip_cutter, frame_evaluator 等)
│   ├── integrations/                   ← 外部連携・API
│   │   ├── api_server.py              ← FastAPI（ポート8210、launchd常駐）
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
│   │   ├── marketing_qc.py            ← マーケQC実行
│   │   ├── auto_qc_runner.py          ← 自動QCランナー
│   │   └── (他: frame_extractor, qc_comparator, telop_reader, whisper_transcriber)
│   ├── reporter/                       ← レポート出力
│   │   ├── html_generator.py          ← HTMLレポート生成
│   │   ├── publisher.py               ← GitHub Pages公開
│   │   └── template.py                ← テンプレート
│   └── tracker/                        ← トラッキング・FB学習
│       ├── feedback_learner.py         ← FB学習（10パターン5ルール蓄積済み）
│       ├── edit_learner.py             ← 編集学習（⚠️ 0件未稼働）
│       ├── video_tracker.py            ← 映像品質トラッキング
│       ├── quality_dashboard.py        ← 品質ダッシュボード
│       └── (他: skill_matrix, video_analyzer, video_learner 等)
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
├── output/                             ← 生成物出力先
│   ├── reports/                        ← ディレクションレポート
│   └── tracking/                       ← トラッキング結果
├── config.yaml                         ← システム設定
├── CLAUDE.md                           ← 部署行動マニュアル
├── PROGRESS.md                         ← 進捗管理
└── archive/                            ← 過去ログ（935行）
```

## 3. 外部連携

| 連携先 | モジュール | 方式 | 備考 |
|--------|-----------|------|------|
| Google Sheets | sheets_manager.py | API直叩き | 将来: Google Sheets MCP |
| Vimeo | source_video_linker.py | API直叩き | 将来: Vimeo MCP |
| YouTube Data API v3 | loader.py | API直叩き | 概要欄テンプレート取得（24hキャッシュ） |
| AI開発5（動画ナレッジ） | ai_dev5_connector.py | ファイル参照 | 文字起こしデータ取得 |
| Anthropic LLM | teko_core.llm経由 | API | 直叩き禁止。全てteko_core.llm経由 |

## 4. launchd常駐サービス

| サービス | Label | 状態 |
|----------|-------|------|
| APIサーバー | com.maekawa.video-direction-api | ✅ 稼働中（uvicorn, ポート8210, KeepAlive） |
| 監査ランナー | com.maekawa.video-direction-audit | ⏸ 確認必要 |

## 5. データベース

| DB | パス | 内容 |
|----|------|------|
| video_direction.db | .data/ + ルート | メインDB（対談データ・生成物） |
| projects.db | .data/ | プロジェクト管理 |
| video_director.db | .data/ | ディレクターデータ |

## 6. 品質基準の一元化

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

## 7. 設計確定事項

- FB承認フロー: 事前承認制（なおとさん/パグさんが各々承認してから編集者に流す）
- FBスタイル: 1コメント1テーマ（複合FB分解は不要）
- LLM呼び出し: 全システムteko_core.llm経由に統一（API直叩き禁止）
- 概要欄テンプレート: YouTube API取得→24hキャッシュ→プロンプト注入（フォールバック: ハードコード）
- 層分類: QUALITY_JUDGMENT_GUIDE.md セクション1に準拠（年収+企業ブランド+年齢の5段階）
- Drive素材命名: C番号昇順で連番（_1, _2）。「短尺」禁止

## 8. バティWSとの関係

- **ディレクション**: バティがタスク投入（mission-dispatch.sh経由）
- **品質基準の正本**: docs/QUALITY_JUDGMENT_GUIDE.md（このWS内。バティWSにはない）
- **品質判断の引き継ぎ**: バティ growth/judgment-patterns.md #36, #39, #40 が本WSに関連
- **設計ドキュメント**: `~/バティ/docs/video-agent-redesign-20260415.md`

## 9. 既知の問題

| # | 問題 | 状態 |
|---|------|------|
| 1 | edit_learnerが未稼働（0件） | ⚠️ Supabase移行より先に稼働させる |
| 2 | 概要欄未生成38% | ⏳ 原因調査必要 |
| 3 | Vimeo未マッチ16名 | 待ち（編集完了後に自動マッチ） |
| 4 | .gitが131MB（バイナリ履歴） | P3 |
| 5 | チャンネル移行（退職者Googleアカウント問題） | 👤 なおとさん→事務待ち |
