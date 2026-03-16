# PROGRESS.md — 映像品質追求・自動ディレクションシステム（AI開発10）

## 最終更新日時
2026-03-17 セッション14: タイトル生成品質大幅改善 + 名前誤表記全件修正 + 未公開23件一括タイトル生成
<!-- authored: T1/副官A/バティ/2026-03-17 -->

## 現在の作業状態
**タイトル生成エージェントの品質が劇的向上。未公開23件の一括生成完了。名前誤表記1,479件を6パターン全件修正済み ✅**

### 2026-03-17 セッション14 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | TITLE_GENERATION_PROMPT大幅改修（設計思想・判断軸・全42本実例注入） | ✅ |
| 2 | パターンA/B定義修正（年収先頭型=推奨・最近の主流に修正） | ✅ |
| 3 | パンチライン違いバリエーション生成（属性固定でパンチライン3-5案） | ✅ |
| 4 | ゲスト名クリーニングロジック追加（title_generator.py + thumbnail_designer.py） | ✅ |
| 5 | 未公開23件の一括タイトル再生成（全件LLM 5案ずつ生成、DB保存） | ✅ 23/23成功 |
| 6 | 名前誤表記6パターン一括修正（1,479件/38ファイル） | ✅ |
| 7 | 誤名前タイトル再生成（ひろきょう・さくら 2件） | ✅ |

**タイトル品質改善の詳細:**
- 旧: 年収数字ベタ貼り + 固定テーマ3パターン回し（フォールバック品質）
- 新: 感情・覚悟のパンチライン + 個別テーマ + 設計思想に基づく属性配置（LLM品質）
- なおとさん評価: 「震えるくらいいい」「これだよこれ」

**prompts.py改修内容:**
- パターンA（年収先頭型・推奨）/ パターンB（パンチライン先頭型・初期）の正しい定義
- 【最重要・タイトル設計の判断軸と設計思想】セクション追加（属性の2目的、パンチラインの目的）
- 実例を10本→全42本に拡充（パターンA 9本 / パターンB 33本に分類）
- ルール10「パンチライン違いのバリエーション3〜5案」に変更

**名前誤表記修正（全6パターン）:**
| 誤表記 | 正しい名前 | 修正件数 | 原因 |
|--------|-----------|---------|------|
| クマキ | くますけ | 27行 | 文字起こし誤変換 |
| 雪森 | ゆきもる | 559行 | 文字起こし誤変換 |
| ひ樹京 | ひろきょう | 100行 | 文字起こし誤変換 |
| 陽介 | りょうすけ | 314行 | 文字起こし誤変換 |
| 坂さん | さくらさん | 454行 | 文字起こし誤変換 |
| 荒沢 | てぃーひろ | 25行 | 文字起こし誤変換 |

対象ディレクトリ: ~/video-knowledge-pages/、~/TEKO/knowledge/01_teko/sources/video/、~/AI開発10/output/

**変更ファイル:**
- `src/video_direction/knowledge/prompts.py` — TITLE_GENERATION_PROMPT大幅改修
- `src/video_direction/analyzer/title_generator.py` — ゲスト名クリーニングロジック追加
- `src/video_direction/analyzer/thumbnail_designer.py` — ゲスト名クリーニングロジック追加
- `scripts/regenerate_titles_fix_names.py` — 名前修正後のタイトル再生成スクリプト（新規）

**バティ永久記憶更新:**
- `memory/marketing_quality.md` — YouTubeタイトル設計の品質基準セクション新設

### 2026-03-16 セッション11 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | E2E Step 4.6 GuestProfile→PersonProfile import修正 | ✅ |
| 2 | knowledge=null時もguest_nameからprofile作成 | ✅ |
| 3 | 職業テキスト長すぎ問題の切り詰め処理追加 | ✅ title_generator.py + description_writer.py |
| 4 | age数字のみ→「歳」自動付与 | ✅ title_generator.py |
| 5 | パンチライン切り詰めを句読点区切りに改善 | ✅ title_generator.py |
| 6 | バッチ再生成 29/29件成功（新フォーマット適用確認済み） | ✅ |
| 7 | Build 21アーカイブ+USB直接インストール | ✅ |
| 8 | edited_video（Vimeo URL）がAPIで返らないバグ修正 | ✅ json.loads失敗→try-catch |
| 9 | api_server.py全箇所のJSON parseにtry-catch追加 | ✅ 4箇所 |
| 10 | source_video連携: SourceVideoLinkerのマッチング改善+26/29件リンク成功 | ✅ |
| 11 | ファイル名からゲスト名抽出ロジック追加（撮影パターン+日付パターン+split逆順） | ✅ |

### 2026-03-16 セッション10 完了タスク（18モデル並列デプロイ）

| # | タスク | 状態 |
|---|--------|------|
| 1 | 手修正API: ディレクションレポート（PUT/GET history/GET diff） | ✅ edit_direction_routes.py |
| 2 | 手修正API: タイトル・概要欄・サムネ（9エンドポイント） | ✅ edit_assets_routes.py |
| 3 | diff分析エンジン（difflib、LLM不使用） | ✅ edit_diff_analyzer.py |
| 4 | EditLearner 手修正学習DB | ✅ edit_learner.py |
| 5 | プロンプト3種改修（TEKO統一フォーマット+Z理論+CTA冒頭） | ✅ prompts.py |
| 6 | トラッキング分析粒度強化（direction_generator大幅強化） | ✅ direction_generator.py |
| 7 | FB変換強化（TEKO美的基準+ゲストtier+あいまいFBルール） | ✅ feedback_converter.py |
| 8 | Vimeoマッチング改善（複合名分割+かな変換+レポート出力） | ✅ sync_vimeo_edited_videos.py |
| 9 | ルーター統合（api_server.pyにedit_direction/edit_assets登録） | ✅ |
| 10 | api_server.py importエラー修正（絶対→相対import） | ✅ ModuleNotFoundError解消 |
| 11 | E2Eバッチ再生成 29/29件成功（あさかつ・くますけ含む） | ✅ |
| 12 | iOS: DirectionEditView（4セクション折りたたみ式） | ✅ |
| 13 | iOS: TitleDescriptionEditView（独立保存+diff表示） | ✅ |
| 14 | iOS: ThumbnailEditView（Z型4ゾーン色分けカード） | ✅ |
| 15 | iOS: APIClient 8メソッド追加 | ✅ |
| 16 | iOS: DirectionReportView 導線追加 | ✅ |
| 17 | テスト73件全PASS（edit系4ファイル） | ✅ |

**新規ファイル（Python 4件）:**
- `src/video_direction/integrations/edit_direction_routes.py` — ディレクション手修正API
- `src/video_direction/integrations/edit_assets_routes.py` — タイトル・概要欄・サムネ手修正API
- `src/video_direction/analyzer/edit_diff_analyzer.py` — diff分析エンジン
- `src/video_direction/tracker/edit_learner.py` — 手修正学習エンジン

**新規ファイル（Swift 3件）:**
- `Views/DirectionEditView.swift` — ディレクション編集画面
- `Views/TitleDescriptionEditView.swift` — タイトル・概要欄編集画面
- `Views/ThumbnailEditView.swift` — サムネ指示書編集画面（Z理論4ゾーン）

**変更ファイル（Python）:** api_server.py, prompts.py, direction_generator.py, feedback_converter.py, title_generator.py, description_writer.py, thumbnail_designer.py, sync_vimeo_edited_videos.py
**変更ファイル（Swift）:** APIClient.swift, DirectionReportView.swift

### 2026-03-16 セッション13 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | 4G環境でのiPhone→APIサーバー接続問題解決（cloudflaredトンネル構築） | ✅ |
| 2 | cloudflared インストール（Homebrew） + Quick Tunnel起動 | ✅ |
| 3 | Info.plist APIBaseURL変更: Tailscale IP → cloudflared HTTPS URL | ✅ |
| 4 | Build 26ビルド＆USBインストール（TestFlight版Build 25との競合も解消） | ✅ |
| 5 | **Anthropic API $393事件の原因特定** — AI開発9（LINEエージェント）がOpus 4.6を30秒間隔で常駐呼び出し | ✅ |
| 6 | AI開発9 line-knowledge-watcherサービス即時停止 | ✅ |
| 7 | AI開発9 llm_validator.py + multi_layer_checker.py: claude-opus-4-6 → claude-haiku-4-5-20251001 に変更 | ✅ |
| 8 | **teko_core.llm 共通LLMラッパーモジュール新規作成**（teko-shared-libs） | ✅ |
| 9 | **全ワークスペースのANTHROPIC_API_KEY無効化**（6箇所コメントアウト+バックアップ） | ✅ |

**4G接続問題の原因と解決:**
- 原因: Tailscale VPNが4G環境でiPhoneのidle状態から復帰しない
- 解決: cloudflared Quick Tunnel（`https://deals-proper-symantec-imaging.trycloudflare.com`）でAPIサーバーをインターネット公開
- 注意: Quick TunnelのURLは一時的。Macの再起動やプロセス停止でURL変更。本格運用は名前付きトンネル（Cloudflareアカウント紐付け）が必要

**Anthropic API $393事件の全容:**
- 発覚: Anthropic Console BillingでUSD $393.23のpending発見。残高$55.91では不足しAPI呼び出しブロック状態
- 原因: AI開発9（LINEエージェント）の`llm_validator.py`が`claude-opus-4-6`（最高額モデル）でLINEメッセージ検証を30秒間隔watchモードで常駐実行
- Daily token cost: Mar 12〜16で毎日$50〜75。Opus 4.6が全体の80%以上を占める
- 根本原因: 兵隊が司令塔（バティ）の「ペンディング」指示を無視してサービスを常駐起動し、高額モデル指定のまま放置
- 対策1（即時）: サービス停止 + モデルをHaikuに変更
- 対策2（恒久）: 全.envからANTHROPIC_API_KEYを無効化し、従量課金API直叩きを不可能に
- 対策3（インフラ）: teko_core.llm共通ラッパーを作成。全システムは`claude -p`（MAX定額内）経由のみに統一

**teko_core.llm ラッパー仕様:**
- 場所: `~/teko-shared-libs/teko_core/llm.py`
- インターフェース: `ask(prompt)`, `ask_json(prompt)`, `ask_full(prompt)` の3関数
- デフォルト: `claude -p`経由（MAX定額内、追加課金なし）
- フォールバック: `TEKO_LLM_MODE=api`環境変数でAPI直叩きに切替可能（ただしキー無効化済みなので機能しない）
- ログ: `~/TEKO/knowledge/raw-data/llm-usage/YYYY-MM-DD.jsonl`に全呼び出し記録
- CLAUDECODE環境変数除外対策済み（ネストセッション問題回避）
- 動作確認済み: Haiku/CLI/19.41秒で正常応答

**APIキー無効化した箇所（全6箇所）:**
| ファイル | バックアップ |
|----------|------------|
| `~/AI開発2/.env` | `.env.bak.20260316` |
| `~/AI開発3/.env` | `.env.bak.20260316` |
| `~/AI開発5/.env` | `.env.bak.20260316` |
| `~/AI開発6/.env` | `.env.bak.20260316` |
| `~/teko-content-pipeline/.env` | `.env.bak.20260316` |
| `~/.config/maekawa/api-keys.env` | `api-keys.env.bak.20260316` |

**教訓・ルール追加:**
1. **兵隊がコスト影響のあるサービスを勝手に常駐起動してはならない**。API従量課金を伴うlaunchdサービスの起動は司令塔の承認必須
2. **LLM呼び出しは全システムteko_core.llm経由に統一**。anthropic.Anthropic()やopenai.OpenAI()の直叩きは禁止
3. **APIキーは.envにベタ書きしない**。共通ラッパーがMAX定額を優先使用し、従量課金は環境変数での明示的切替のみ

**変更ファイル:**
- 新規: `~/teko-shared-libs/teko_core/llm.py`
- 変更: `~/AI開発9/src/line_knowledge/extractor/llm_validator.py`（opus→haiku）
- 変更: `~/AI開発9/src/line_knowledge/extractor/multi_layer_checker.py`（opus→haiku）
- 変更: `Info.plist`（APIBaseURL → cloudflared URL）
- 変更: `project.pbxproj`（Build 26）
- 無効化: 上記6箇所の.envファイル

### 2026-03-16 セッション12 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | SourceVideoLinkerにエイリアスマッチ追加（ローマ字↔カタカナ、ひらがな↔漢字対応） | ✅ |
| 2 | _extract_speaker_namesの括弧内カンマ分割保護 | ✅ |
| 3 | source_video 29/29全件マッチ成功（kos/メンイチ/さといも・トーマス含む） | ✅ |
| 4 | ナレッジファイル名リネーム5件（コスト氏→kos、メイジ→メンイチ、コテツ→コテ、羽生氏→ハオ、ゲスト氏里芋トーマス→さといも・トーマス） | ✅ |
| 5 | ナレッジ内部話者名修正 1,193行（sources/video + _refinery/output + _archive_duplicates） | ✅ |
| 6 | 29/29バッチ再生成（正しい名前でタイトル生成確認済み） | ✅ |
| 7 | Vimeo連携: 14/29マッチ済み（真生さんavailable版手動設定）。残15名はVimeo未アップ | ✅ |
| 8 | Vimeo APIタイムアウト改善（30s→120s） | ✅ |
| 9 | タイトル・概要欄品質テスト 29/29 全項目PASS（TEKO独占/CTA/タイムスタンプ/ハッシュタグ） | ✅ |

**修正ファイル（Python）:** source_video_linker.py, sync_vimeo_edited_videos.py
**修正ファイル（ナレッジ）:** sources/video/ 7ファイル内部 + 5ファイルリネーム, _refinery/output/ 73ファイル

### 次にやるべき作業
| # | タスク | 状態 |
|---|--------|------|
| 1 | Vimeo残15名: 編集完了後にsync_vimeo_edited_videos.pyが自動マッチ予定 | 待ち |
| 2 | ~~LLM有効時のタイトル品質向上テスト~~ | ✅ セッション14で完了（23件全件LLM生成成功） |

### 2026-03-16 セッション9 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | ディレクションレポート全29件バッチ生成（失敗0件、95.8秒） | ✅ |
| 2 | 引き継ぎドキュメント作成（HANDOFF_20260316.md） | ✅ |

### 2026-03-16 セッション8 完了タスク（UIバグ修正+カテゴリ修正）

| # | タスク | 状態 |
|---|--------|------|
| 1 | ツールサブタブ無限スピナー修正（toolProjectsLoadedフラグ追加） | ✅ |
| 2 | セグメントコントロール固定（Picker→ScrollView外移動+横スワイプ対策） | ✅ |
| 3 | トラッキングYouTube埋め込み→サムネイル+YouTubeで開くに変更（エラー150/152対策） | ✅ |
| 4 | 素材動画APIエラー修正（buildURLの日本語パーセントエンコーディング） | ✅ |
| 5 | Vimeo動画16:9修正（レビュー+タイムライン+VimeoEmbedPlayerViewのCSS修正） | ✅ |
| 6 | カテゴリ修正（テスト除外順序修正+MEMBER_MASTERオーバーライド+メンイチ→teko_realestate） | ✅ |

**変更ファイル:**
- `QualityDashboardView.swift` — Picker外出し+scrollBounceBehavior+contentShape
- `VideoTrackingView.swift` — YouTube埋め込み→サムネイル+再生ボタンUI、16:9対応
- `DirectionReportView.swift` — VimeoEmbedPlayerView 16:9 GeometryReader化
- `VimeoPlayerView.swift` — VimeoEmbedPlayerView CSS overflow:hidden追加
- `APIClient.swift` — buildURLの日本語パーセントエンコーディング対応
- `api_server.py` — テスト除外順序修正（ステージ1前に移動）+MEMBER_MASTERオーバーライド

### 次にやるべき作業（なおとさん指示、優先順位付き）

| # | タスク | 規模 | 状態 |
|---|--------|------|------|
| 1 | ~~ディレクションレポートを全員分自動生成（バッチ実行）~~ | 中 | ✅ 29件全件成功 |
| 2 | ディレクションレポートの手修正機能（アプリ内編集→API保存→修正分析→学習） | 中 | **次に着手** |
| 3 | サムネ指示書を青木さんZ理論ナレッジで強化 | 大 | 未着手 |
| 4 | タイトル案・概要欄をチャンネル過去動画フォーマットに合わせる（チャンネルID要） | 中 | 未着手 |
| 5 | タイトル案・概要欄の手修正機能（アプリ内編集→API保存→修正分析→学習） | 中 | 未着手 |
| 6 | 全生成物の修正学習→自己成長エージェント化（FB学習ループ拡張） | 大 | 未着手 |

### Vimeo連携状況
- ✅ マッチ済み（13名）: Izu、PAY、hirai、けー、こも、さるビール、しお、てぃーひろ、みんてぃあ、ゆきもる、りょうすけ、スリマン、メンイチ
- ❌ 未マッチ（16名）: RYO、kos、あさかつ、くますけ、さくら、さといも・トーマス、ひろきょう、やーまん、ゆりか、ろく、アンディ、コテ、ハオ、ロキ、松本、真生

### 2026-03-16 セッション7 完了タスク（素材動画YouTube URL連携）

| # | タスク | 状態 |
|---|--------|------|
| 1 | Python API: source_videosテーブル作成 + GET/POST エンドポイント追加 | ✅ |
| 2 | Web UI: 「素材動画」タブ追加（YouTube iframe埋め込み + 手動登録フォーム） | ✅ |
| 3 | iOS Swift: SourceVideosSubTabView新規作成（API連携 + 複数動画表示 + 手動登録シート） | ✅ |
| 4 | テスト: test_source_videos_api.py 19テスト全PASS | ✅ |

**新規エンドポイント:**
- `GET /api/v1/projects/{project_id}/source-videos` — プロジェクト別素材動画一覧（source_videosテーブル + レガシーJSONの統合・重複排除）
- `POST /api/v1/projects/{project_id}/source-videos` — 素材動画手動登録（video_id自動抽出、重複チェック）

**新規テーブル:** source_videos（id, project_id, youtube_url, video_id, title, duration, quality_status, source, knowledge_file, created_at）

**新規ファイル:**
- `tests/test_source_videos_api.py` — 19テスト（video_id抽出6件 + GET 4件 + POST 7件 + 既存scan/status 2件）
- `VideoDirectorAgent/.../Views/SourceVideosSubTabView.swift` — iOS素材動画サブタブ + YouTube再生シート + 手動登録シート

**変更ファイル:**
- `api_server.py` — source_videosテーブル + SourceVideoCreate + _extract_video_id + 2エンドポイント
- `webapp/app.js` — 素材動画タブ追加 + renderSourceVideos + 手動登録フォーム
- `webapp/styles.css` — sv-* スタイル追加（Netflix風ダークUI準拠）
- `APIClient.swift` — fetchSourceVideos / addSourceVideo メソッド + モデル定義
- `DirectionReportView.swift` — sourceVideoSection → SourceVideosSubTabView委譲

### 2026-03-16 セッション6 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | iOS UI: E2Eパイプライン画面 | ✅ 品質ダッシュボード > ツールタブに統合 |
| 2 | iOS UI: テロップチェック画面 | ✅ 品質ダッシュボード > ツールタブに統合 |
| 3 | iOS UI: 音声品質評価画面 | ✅ 品質ダッシュボード > ツールタブに統合 |
| 4 | iOS UI: ナレッジページ画面 | ✅ ホーム画面ツールバーの本アイコンからアクセス |
| 5 | Xcode pbxproj 8ファイル登録 | ✅ BUILD SUCCEEDED |

**新規作成ファイル（8件）:**
- ViewModels: E2EPipelineViewModel, TelopCheckViewModel, AudioEvaluationViewModel, KnowledgePagesViewModel
- Views: E2EPipelineView, TelopCheckView, AudioEvaluationView, KnowledgePagesView

**変更ファイル（6件）:**
- Models.swift（16モデル追加）, APIClient.swift（10メソッド+performLongRequest追加）
- DashboardViewModel.swift（.toolsセクション追加）, QualityDashboardView.swift（ツールセクション統合）
- RootTabView.swift（ナレッジページモーダル追加）, ProjectListView.swift（本アイコンボタン追加）

### 2026-03-16 セッション5 実装中タスク

| # | タスク | 担当 | 状態 |
|---|--------|------|------|
| 1 | E2Eパイプライン統合（ディレクション生成API + 統合フローAPI） | 兵隊A | 実行中 |
| 2 | C-2 テロップ自動チェック（OCR+LLM） | 兵隊B | 実行中 |
| 3 | C-3 音声品質自動評価（ffmpeg連携） | 兵隊C | 実行中 |
| 4 | KP-1 動画ナレッジページ統合（AI開発5 HTML閲覧・検索） | 兵隊D | ✅ 完了（28テストPASS） |

### 2026-03-16 セッション4-5 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | スプシN列にVimeo URL 13件HYPERLINK書き込み | ✅ --execute実行、全件成功 |
| 2 | Web版UI移植7機能（EditFB/Vimeoレビュー/トラッキング/音声FB/FB学習詳細/映像学習詳細/フレーム評価） | ✅ |
| 3 | 全56要件の実装状況マッピング | ✅ |
| 4 | iOSビルド: USB直接インストールに切替 | ✅ TestFlight上限回避 |

### 2026-03-16 セッション4 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | sync_sheets.py新規作成 | ✅ DB→スプシ同期スクリプト。dry-runデフォルト、--executeで書き込み |
| 2 | dry-run突合テスト | ✅ 13件全マッチ、未マッチ0件。14列目「Vimeo」列をターゲット |

### 2026-03-16 セッション3 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | Vimeo動画352本 × DB29メンバー突合 | ✅ 14名マッチ、NFKC正規化で結合文字問題解決 |
| 2 | edited_video DB紐付け | ✅ 13件のVimeo URLをDBに格納 |
| 3 | TestFlight B19状態確認 | ✅ USB直接インストール済み、TF上限リセット待ち |
| 4 | Vimeo API本番投稿承認 | ✅ なおとさん承認済み |
| 5 | Vimeo自動突合スクリプト作成 | ✅ sync_vimeo_edited_videos.py（NFKC正規化+命名規則パターン） |
| 6 | launchd自動化登録 | ✅ com.maekawa.vimeo-sync（1時間ごと自動実行） |
| 7 | APIサーバー500エラー修正 | ✅ edited_videoのJSON誤パース修正→30件正常返却 |
| 8 | スマホアプリ自動反映確認 | ✅ Vimeo突合→DB→API→iOS全自動パイプライン動作確認 |

### 2026-03-16 セッション3 進行中タスク

| # | タスク | 担当 | 状態 |
|---|--------|------|------|
| 9 | Web版UI移植（EditFB+Vimeoレビュー+トラッキング） | 兵隊A | 実行中 |
| 10 | スプレッドシート連携（edited_video書き込み） | 兵隊B | 実行中 |

### 2026-03-16 セッション2 完了タスク

| # | タスク | 状態 |
|---|--------|------|
| 1 | VimeoReviewViewModel.swift localhost修正 | ✅ APIClient.shared.baseURL使用に変更 |
| 2 | 撮影日shoot_date API側全件確認 | ✅ 大阪7名+けー+ゆりか+さくら全件正確 |
| 3 | さくらさん撮影日確定 | ✅ 2025/12/13で確定（なおとさん回答） |
| 4 | PIVOT 5本 + 楽街 5本トラッキング登録・分析 | ✅ メタデータ分析completed |
| 5 | yt-dlpパス修正（video_tracker.py + video_analyzer.py） | ✅ Python 3.9ユーザーインストールパスへのフォールバック追加 |
| 6 | Mac2/Mac3 git同期 | ✅ 3台とも40335ccに統一 |
| 7 | テストダミーデータ削除 | ✅ tracking_index.jsonからtest123を除去 |
| 8 | テスト全件確認 | ✅ 626件全PASS |

### 今回のセッションで完了したタスク（3台Mac並列実行）

| # | タスク | Mac | 優先度 | 状態 |
|---|--------|-----|--------|------|
| 1 | FB学習ループ接続 + スプレッドシート照合改善 | Mac2 | 実用化 | ✅ |
| 2 | Vimeo APIドライラン/実行実装 | Mac2 | 実用化 | ✅ |
| 3 | YouTube素材iOS UI完成 | Mac3 | 実用化 | ✅ |
| 4 | 音声FB→Vimeo連携 E2Eフロー（API+iOS） | Mac2 | P1 | ✅ |
| 5 | 音声FB→Vimeo連携 UI組み込み | Mac1 | P1 | ✅ |
| 6 | Before/After iOS UI + APIエンドポイント | Mac2+Mac1 | P1 | ✅ |
| 7 | Vimeoレビュータイムライン表示 | Mac3 | P1 | ✅ |
| 8 | 品質ダッシュボード実データ連動 | Mac2 | P2 | ✅ |
| 9 | 映像トラッキング実用化（video_learner+frame_evaluator） | Mac1 | P2 | ✅ |

### テスト・ビルド
- Pythonテスト: **626件全PASS**
- xcodebuild: **BUILD SUCCEEDED**
- TestFlight: Build 19 アーカイブ中

---

### TASK_P2_TRACKING_DASHBOARD.md 実施結果（2026-03-16）

**実施内容: 6ファイル変更・2テストファイル新規作成・テスト626件全PASS**

#### 1. video_learner.py 実用化
- `VideoLearningRule` データクラス追加: FeedbackLearner.LearningRuleと互換のルール構造体
- `get_active_rules()` メソッド追加: 確信度0.4以上のパターンをルール形式で返す（direction_generator互換）
- `get_insights()` メソッド追加: FeedbackLearner.get_insights()と統一フォーマット

#### 2. direction_generator.py へのvideo_learner接続
- `generate_directions()` に `video_learner` パラメータ追加
- `_apply_learned_rules()` でFB学習と同じ仕組みで映像学習ルールを適用
- `_llm_analyze()` に映像トラッキングインサイトのプロンプト注入追加
- `get_learning_context()` に `video_learner` パラメータ追加（FB+映像統合コンテキスト）

#### 3. frame_evaluator APIエンドポイント追加（api_server.py）
- `GET /api/v1/projects/{id}/frame-evaluation`: キャッシュ済み評価結果の取得
- `POST /api/v1/projects/{id}/frame-evaluation`: フレーム評価の実行（スタブ/API両対応）
- 評価結果はJSON形式で `.data/frame_evaluations/` にキャッシュ

#### 4. iOS 映像トラッキングダッシュボードUI拡張
- `Models.swift`: `FrameEvaluationResponse`, `LearningSummary`, `LearningDetail` 等のモデル追加
- `APIClient.swift`: `fetchFrameEvaluation()`, `runFrameEvaluation()`, `fetchLearningSummary()` 追加
- `VideoTrackingViewModel.swift`: `learningSummary` プロパティ追加、load時に学習サマリーも取得
- `VideoTrackingView.swift`: 学習状況サマリーカード追加（FB学習/映像学習の統計表示）、FlowLayoutによるカテゴリ分布タグ表示、空状態UI追加

#### 5. テスト追加（12件新規）
- `test_video_learner.py`: 8件追加（VideoLearningRule、get_active_rules、get_insights）
- `test_video_learning_loop.py`: 6件新規（direction_generator統合、両learner同時適用、コンテキスト取得）
- `test_frame_evaluation_api.py`: 6件新規（GET/POST エンドポイント、キャッシュ動作）
- **全626件PASS（既存テストに影響なし）**

#### 完了条件チェック
- [x] video_learner が direction_generator に接続される
- [x] frame_evaluator のAPIエンドポイントが動作する
- [x] テスト全PASS（626件）
- [x] PROGRESS.md更新

---

### TASK_P2_QUALITY_DASHBOARD.md 実施結果（2026-03-16）

**実施内容: 5ファイル変更・1ファイル新規作成・22テスト全PASS**

#### 1. APIエンドポイント追加（`src/video_direction/integrations/api_server.py`）
- `GET /api/v1/dashboard/quality` を追加
- `_grade_from_score_100()` ヘルパー関数追加（0-100スケール → A+/A/B+/B/C/D/E）
- レスポンス: `total_scored`, `total_unscored`, `average_score`, `grade_distribution`, `recent_trend`（直近5件）, `improvement_delta`（改善傾向）
- DB実データ28件を集計（quality_score NULLの1件はunscored扱い）

#### 2. iOS Swiftモデル追加（`VideoDirectorAgent/Models/Models.swift`）
- `GradeDistEntry` — グレード分布1件（grade/count/color）
- `QualityStats` — 統計レスポンス全体（sortedGradeEntries/deltaLabel 含む）

#### 3. APIClientメソッド追加（`VideoDirectorAgent/Services/APIClient.swift`）
- `fetchQualityStats()` — GET `/api/v1/dashboard/quality` を呼び出す

#### 4. DashboardViewModel更新（`VideoDirectorAgent/ViewModels/DashboardViewModel.swift`）
- `@Published var qualityStats: QualityStats?` を追加
- `loadDashboard()` 内で `fetchQualityStats()` を取得（個別try-catchで耐障害性あり）
- エラー時は「品質統計」をエラーリストに追加

#### 5. iOS UI追加（`VideoDirectorAgent/Views/QualityDashboardView.swift`）
- `gradeDistributionCard` を品質セクションに追加（summaryCard と trendCard の間）
- AppTheme準拠デザイン: 改善傾向バッジ（Capsule）、グレード別カラーバー、件数/平均表示

#### 6. テスト追加（`tests/test_quality_dashboard_api.py`）
- 22件全PASS
- `TestGradeFromScore100` (12件): 境界値含む全グレード変換テスト（0-100スケール）
- `TestQualityDashboardEndpoint` (10件): レスポンス構造・グレード分布整合性・実DB値テスト

#### ビルド確認
- Pythonテスト: 22件全PASS（新規）+ 既存62件維持 ✅

---

### TASK_P1_BEFORE_AFTER.md 実施結果（2026-03-16）

**実施内容: 4ファイル変更・2ファイル新規作成・22テスト全PASS**

#### 1. APIエンドポイント追加（`src/video_direction/integrations/api_server.py`）
- `POST /api/v1/projects/{project_id}/edit-feedback` を追加
- 受け取るパラメータ: `duration_seconds`, `original_duration_seconds`, `included_timestamps`, `excluded_timestamps`, `telop_texts`, `scene_order`, `editor_name`, `stage`
- レスポンス: `quality_score`, `grade`, `content_feedback[]`, `telop_check`, `highlight_check`, `direction_adherence`, `summary`
- 評価ロジック: ①テンポ（圧縮率）②構成力（シーン順序）③内容密度（ハイライト採用率）
- evaluatorモジュールが利用可能な場合は優先使用、fallback実装あり

#### 2. iOS Swiftモデル追加（`VideoDirectorAgent/Models/Models.swift`）
- `EditFeedbackRequestBody` — POSTリクエストボディ
- `ContentFeedbackEntry` — コンテンツFB1件（severityColor/categoryColor/categoryLabel 含む）
- `TelopCheckSummary` — テロップチェック結果
- `HighlightCheckSummary` — ハイライト採用率
- `DirectionAdherenceSummary` — ディレクション準拠度
- `EditFeedbackResponse` — 全体レスポンス（gradeColor/scoreProgress 含む）

#### 3. APIClientメソッド追加（`VideoDirectorAgent/Services/APIClient.swift`）
- `fetchEditFeedback(projectId:body:)` — デフォルト引数付きで空ボディでも動作

#### 4. iOS UI新規作成（`VideoDirectorAgent/Views/EditFeedbackView.swift`）★新規
- Netflix風デザイン（AppTheme準拠）
- グレードバッジ（A+/A/B+/B/C/D/E）＋スコアゲージ
- ハイライト採用率バー（採用/カット の視覚的比較）
- テロップチェック結果（エラー数・警告数バッジ）
- コンテンツFBカード（severity別カラーバー、category別ラベル）
- ディレクション準拠度（データあり/なし両対応）
- 編集済み動画メタデータ入力フォーム（シート表示）
- 再生成ボタン

#### 5. project.pbxproj 登録済み
- Build file ID: `A10000010000000000000021`
- File ref ID: `A20000010000000000000021`
- Views グループ・Sources フェーズ両方に追加

#### 6. テスト追加（`tests/test_edit_feedback_api.py`）
- 22件全PASS
- `TestGradeFromScore` (9件): 境界値含む全グレード変換テスト
- `TestComputeEditFeedback` (7件): 計算ロジック・レスポンス構造テスト
- `TestEditFeedbackEndpoint` (5件): APIエンドポイント統合テスト（200/404確認）

#### ビルド確認
- Xcode.app が Mac server にインストールされていないため xcodebuild は実行不可
- `swiftc -typecheck` で確認: iOS専用API（`keyboardType` 等）はmacOS SDKで「unavailable」エラーが出るが、これは既存ビューも同様で iOS ビルドでは正常
- Pythonテスト: 22件全PASS ✅

---

## 前回（2026-03-15）の作業状態
**iOS UI完了 → Vimeo API実投稿準備完了（dry-runまで）→ 次は本番投稿承認待ち**

### TASK_PRACTICAL_VIMEO.md 実施結果（2026-03-15）

**実施内容:**

1. **Vimeo API認証確認**
   - `~/.config/maekawa/api-keys.env` を確認 → `VIMEO_ACCESS_TOKEN` **未設定**
   - 設定方法: `~/.config/maekawa/api-keys.env` に以下を追記してください:
     ```
     VIMEO_ACCESS_TOKEN=your_vimeo_token_here
     ```
   - または環境変数 `export VIMEO_ACCESS_TOKEN=xxx` で設定可
   - **BLOCKED: 本番投稿実行にはなおとさんによるVimeoトークン設定が必要**

2. **dry-run解除と安全対策（実装完了）**
   - `--dry-run` はこれまで任意フラグ → **デフォルトdry-run** に変更
   - `--execute` フラグを新設（本番投稿用）
   - `--execute` 指定時は対話型確認プロンプト表示（`--yes` でスキップ可）
   - リトライロジック（指数バックオフ）は既存実装を維持
   - 使用例:
     ```bash
     # dry-run（デフォルト・安全）
     python3 scripts/post_vimeo_review_comments.py relay.json

     # 本番投稿（なおとさん承認後に実行）
     python3 scripts/post_vimeo_review_comments.py relay.json --execute
     ```

3. **レビューコメントのフォーマット改善**
   - 優先度（高/中/低）に応じたプレフィックス追加:
     - 高: `🔴【優先度: 高】`
     - 中: `🟡【優先度: 中】`
     - 低: `🟢【優先度: 低】`
   - コメントの `priority` フィールドに "高"/"中"/"低" を指定するだけで自動付与

**テスト結果: 13件全PASS**（既存4件 + 新規9件）
- `test_main_live_mode_posts_with_execute_flag` — `--execute --yes` で本番投稿
- `test_main_default_is_dry_run` — デフォルトdry-run確認
- `test_main_execute_cancelled_by_user` — ユーザー中止確認
- `test_build_comment_text_priority_high/low/no_priority/with_reference` — 優先度フォーマット

**変更ファイル:**
- `scripts/post_vimeo_review_comments.py` — デフォルトdry-run化・`--execute`追加・優先度フォーマット追加
- `tests/test_post_vimeo_review_comments.py` — 既存テスト修正 + 新規9テスト追加

---

iPhoneからAPIサーバー（100.110.206.6:8210）に接続して実データ29件を表示・操作できる状態。
Build 5→17を連続デプロイ。Build 17でなおとさんから「UIはこれで完了！」の承認を得た。

### TASK_FIX_HOME_CAROUSEL.md 実施結果（2026-03-15 23:50）

**1. カルーセルタップ修正**
- Build 15でUICollectionView+didSelectItemAt実装済み（ProjectListView.swift内のCarouselCollectionVC）
- Build 17で全プロジェクト一覧画面も完成 → タスクのこの部分は**実装済みにつき対応完了**

**2. DBソート修正（shoot_date）**
- けーさん（p-20260101-Kさん）: **2026/01/25 が正**。⚠️前回誤って2/28に変更→2026-03-16にT1確認で1/25に戻し済み
- ゆりかさん（p-20260101-ユリカ）: **2026/01/25 が正**。⚠️同上
<!-- authored: T1/副官A/バティ/2026-03-16 [なおとさん確認: 1/25が正しい。前回の兵隊自律修正が誤り] -->
- さくらさん（p-20260101-坂さん）: タイトルに「202512オフ会」と明記あり → 2025/12/13のまま保留（大阪2/28組かどうかなおとさんに要確認）
- コテさん・kosさん・メンイチさん・さといも・トーマスさん・ハオさん: 既に2026/02/28 ✅

---

## TestFlight Build 履歴

| Build | 内容 | 状態 |
|-------|------|------|
| 5 | 初回TestFlight配信成功 | ✅ |
| 6 | isSent Bool/Intデコード修正 → 品質タブ復活 | ✅ |
| 7 | ナビゲーション修正・レポートタブ分離・ATS修正 | ✅ |
| 8 | ホームタップ修正（Button化）・履歴タブURL修正・空状態UI | ✅ |
| 9 | Editor型修正・NavigationLink(value:)化・@StateObject保持 | ✅ |
| 10 | タブ切替くるくる修正・API耐障害性・contentShape追加 | ✅ |
| 11-14 | カルーセルタップ修正試行（SwiftUI系10回+UIControl1回、全失敗） | ❌ |
| 15 | UICollectionView+didSelectItemAt実装 | ✅ |
| 16 | UIHostingController VC hierarchy修正+初回reloadData修正 | ✅ |
| 17 | **全プロジェクト一覧画面実装（`>`ボタン→縦グリッド遷移）** — **UI完了** | ✅ |

## Build 10で修正した内容（2026-03-15 20:57）

### 1. タブ切り替え時のくるくる読み込み防止
- **原因**: ReportListView/FeedbackHistoryViewが毎回ViewModelを内部で再生成し、APIを再ロード
- **修正**: ViewModelをRootTabViewの@StateObjectで一元管理し、各Viewに@ObservedObjectで渡す
- **ファイル**: RootTabView.swift, ReportListView.swift, FeedbackHistoryView.swift, FeedbackHistoryViewModel.swift（新規）

### 2. 品質タブAPIエラーの耐障害性向上
- **原因**: DashboardViewModelのloadDashboardで4つのAPIを`async let`で並列実行し、1つでも失敗すると全データ更新されない
- **修正**: 各APIを個別try-catchで囲み、部分的な失敗でも成功したデータは更新。エラーメッセージは失敗した項目のみ表示
- **ファイル**: DashboardViewModel.swift, EditorManagementViewModel.swift, VideoTrackingViewModel.swift

### 3. 品質タブの全サブタブ並列ロード
- **修正**: loadAllで品質・編集者・トラッキングを`async let`で並列実行（従来は逐次実行）
- **ファイル**: QualityDashboardView.swift

### 4. ホームタップ問題への追加修正
- **修正**: NavigationLinkのラベルに`.contentShape(Rectangle())`を追加し、タップ領域を明示的に指定
- **ファイル**: ProjectListView.swift

## Build 8で修正した内容（2026-03-15 20:25）

### 1. ホーム画面のプロジェクトカードがタップに反応しない問題
- **原因**: 横ScrollView内の`onTapGesture`がスクロールジェスチャと競合
- **修正**: `onTapGesture` → `Button` + `.buttonStyle(.plain)` に変更
- **ファイル**: `Views/ProjectListView.swift`

### 2. 履歴タブ「APIに接続できません」エラー
- **原因**: `URL.appending(path:)` がクエリパラメータ `?limit=50` の `?` を `%3F` にエンコード
- **修正**: `buildURL(base:path:)` ヘルパー追加。文字列結合でURL構築
- **ファイル**: `Services/APIClient.swift`
- **補足**: feedbacksテーブルは現在0件。空の場合は空状態UIを表示

### 3. 履歴タブの空状態UI追加
- フィードバック0件時に「フィードバック履歴がありません」を表示
- **ファイル**: `Views/FeedbackHistoryView.swift`

---

## DB修正完了（2026-03-15）

### メンバー名・タイトル全件修正
スプシ（動画コンテンツ分析DB「TEKO対談動画」タブ）の正式名を正として、DB全29件を照合・修正完了。

**修正内容:**
- 重複削除: 60件 → 29件
- guest_name統一: MEMBER_MASTER.jsonのcanonical_name + さん付き
- タイトル内の文字起こし誤変換修正:
  - コスト氏 → kos、コテツ → コテ、メイジ → メンイチ、羽生氏 → ハオ
  - ゲスト氏（里芋、トーマス） → さといも・トーマス
  - pay → PAY、ryo → RYO（大文字統一）

**タイトル一括置換で発生した副作用バグ（修正済み）:**
- 「さといも・さといも・さといも・トーマスさん」（連鎖置換） → 正しく修正
- 「RYOすけさん」（部分マッチ「りょう」→「RYO」） → 正しく修正
- タイトル内「さん」消失（置換マップに「〇〇さん」→「〇〇」が含まれていた） → バックアップから復元

**教訓（DB一括置換）:**
- 短い文字列の部分マッチ置換は危険。長い文字列優先で置換するか、単語境界を意識する
- 連鎖置換（AをBに置換した結果、Bの一部がさらに置換される）を防ぐため、1レコードずつ個別UPDATEが安全
- 置換前に必ずバックアップ。`cp db db.bak_YYYYMMDD_HHMMSS`

---

## 18モデル3台体制の生産性評価（2026-03-15 なおとさん壁打ち）

### ✅ 良かった点
- Mac2（Web UI）とMac3（iOS）に同時タスク投入 → Mac2のWeb変更（+624行）は品質OK。2つの成果物が並列で出てきた
- CLIビルド→TestFlightアップロードの完全自動化 → 人間の操作ゼロでBuild 5→6→7→8を連続デプロイ
- バグ検出→修正→再ビルドのサイクルが速い — ATS問題発見→修正→ビルド→アップロードが数分

### ❌ 課題（Mac3の暴走）
- Mac3の兵隊が「既存コード削除禁止」ルールを無視して3,954行削除 → リバートが必要になった
- 原因: タスク投入時にCLAUDE.mdのルールが既にセッション開始済みの兵隊に届いてなかった
- 教訓: **ルールはCLAUDE.mdだけでなくタスク指示書に直接埋め込む必要がある**

### 📊 実感値
- 「1セッションで全部やる」よりは確実に速い
- 品質管理（監査フェーズ）がまだ回ってないから、暴走検知が遅れた
- 監査2名が機能し始めればスピード×品質の両立ができるはず

---

## 技術的な学び（オペレーション組み込み用）

### iOS開発のハマりポイント（TestFlight配信時に判明）

| # | 問題 | 原因 | 修正 | 今後のチェックリスト |
|---|------|------|------|-------------------|
| 1 | iPhoneからAPI接続不可 | ATS（App Transport Security）がHTTP通信をブロック | Info.plistに`NSAllowsArbitraryLoads=true` + IP例外追加 | 新しいIPアドレスへの接続時は必ずATS例外を確認 |
| 2 | 品質・履歴タブエラー | `is_sent: 0`(Int)をBoolでデコード失敗 | Bool/Int両対応のフレキシブルデコーダー | APIレスポンスの型をSwift側で柔軟に受ける |
| 3 | カルーセルタップ反応なし | 横ScrollView内のonTapGestureがスクロールと競合 | **UICollectionView+didSelectItemAtで根本解決**（Build 17） | SwiftUI横ScrollView内のタップは**UICollectionViewに逃がす**のが正解。SwiftUI系10手法+UIControl全て失敗 |
| 4 | クエリパラメータ付きAPIエラー | `URL.appending(path:)`が`?`を`%3F`にエンコード | 文字列結合でURL構築するヘルパー追加 | SwiftのURL APIはクエリパラメータに注意 |
| 5 | レポートタブがホームと同じ | RootTabViewの.reportケースがProjectListViewを表示 | 専用ReportListView作成 | 新タブ追加時は必ずビューの割り当てを確認 |

### xcodebuild CLI ビルド手順（自動化済み）
```bash
# 1. バージョンバンプ
sed -i '' 's/CURRENT_PROJECT_VERSION = N;/CURRENT_PROJECT_VERSION = N+1;/g' *.xcodeproj/project.pbxproj

# 2. Archive
xcodebuild -project *.xcodeproj -scheme VideoDirectorAgent -sdk iphoneos \
  -configuration Release -archivePath ./build/*.xcarchive archive \
  DEVELOPMENT_TEAM=TT2DA7H5NJ CODE_SIGN_IDENTITY="Apple Development" \
  -allowProvisioningUpdates

# 3. Export & Upload
xcodebuild -exportArchive -archivePath ./build/*.xcarchive \
  -exportOptionsPlist ExportOptions.plist -exportPath ./build/export \
  -allowProvisioningUpdates
```

### MEMBER_MASTER.json 運用ルール
- `canonical_name`: 正式名（DB・UIで使用する名前）
- `transcription_errors`: 文字起こし誤変換リスト（メイジ→メンイチ等）
- `aliases`: 別名・旧名
- `merged_from`: 統合元（重複削除時に記録）
- **DB修正時は必ずMEMBER_MASTER.jsonのcanonical_nameを正とする**
- **タイトル一括置換は個別UPDATE文で行う（REPLACE関数の連鎖置換を防ぐ）**

---

## 次にやるべき作業（優先順位付き）

### [解除済み] Vimeo API本番投稿
- ✅ `VIMEO_ACCESS_TOKEN` 設定済み（疎通確認OK: /users/149351040）
- 実行コマンド: `python3 scripts/post_vimeo_review_comments.py relay.json --execute`
- なおとさんの投稿承認が出れば即実行可能

### [P1] 音声FB→Vimeoレビュー連携（T-039）
- 音声フィードバック録音 → STT → Vimeoタイムコードにマッピング
- 実運用フローの構築（Vimeo投稿部分はpost_vimeo_review_comments.pyで準備完了）

### [P1] Vimeoレビュータイムライン表示（T-040）
- タイムライン上にFBポイントを可視化

### [P1] before/after連携+素材ナレッジ統合（T-033）
- 修正前後のディレクション比較画面
- 素材ナレッジとの連携

### [P2] YouTube素材3機能UI完成（iOS版）
- タイトル案表示・コピー
- サムネ指示書表示
- 概要欄テキスト表示・コピー

### [P2] スマホ導入線整理（T-037）
- TestFlight配布フローの整理

### [P3] 映像トラッキング+学習ループ
- ~~FB学習ループの運用データ投入~~ ✅ PIVOT 5本 + 楽街 5本を投入済み
- 評価ルール精度改善（実データで検証可能になった）
- 映像ファイルダウンロード→cv2フレーム分析（カット割り・色彩・シーンチェンジ）は未実施

---

## 既知の問題・課題

| # | 問題 | 状態 |
|---|------|------|
| 1 | ~~YouTubeAssetsViewModel.swiftのbaseURLがlocalhost:8210ハードコード~~ | ✅ 修正済み（localhost残存なし） |
| 2 | feedbacksテーブルが空（0件） | 正常。録音機能からFB投入後にデータが蓄積される |
| 3 | xcodebuild署名: `CODE_SIGN_STYLE=Automatic`ではなく手動指定が必要 | TT2DA7H5NJ + "Apple Development" で解決済み |
| 4 | 層cの該当者0件: 現データセット29件に自営業家系なし | 追加データで検証必要 |
| 5 | ~~さくらさんのshoot_date未確認~~ | ✅ 2025/12/13で確定（なおとさん回答 2026-03-16） |

---

## 完了済み作業アーカイブ

### webapp YouTube素材UI追加（2026-03-15）
- YouTube素材タブ追加（サムネ指示書・タイトル案・概要欄）
- テスト524件全PASS

### TestFlight初回配信〜Build 17 UI完了（2026-03-15）
- Build 5: 初回配信成功
- Build 6: isSentデコード修正
- Build 7: ATS修正・ナビゲーション修正・レポートタブ分離
- Build 8: ホームタップ修正・履歴URL修正・空状態UI
- Build 9: Editor型修正・NavigationLink(value:)化・@StateObject保持
- Build 10: タブ切替くるくる修正・API耐障害性
- Build 11-14: カルーセルタップ修正試行（全失敗 — 問題の認識自体が誤っていた）
- Build 15: UICollectionView+didSelectItemAt実装
- Build 16: VC hierarchy修正+初回reloadData修正
- Build 17: **全プロジェクト一覧画面実装 → UI完了承認**

### Build 17 最重要教訓（2026-03-15）
- 「全プロジェクトのボタン反応ない」= セクションヘッダーの`>`ボタンのことだったのに、カルーセルカードのタップだと思い込んで11回的外れな修正をした
- **なおとさんの言葉をそのまま受け取る。勝手に変換しない。分からなければ聞く**
- コンテキスト消失後はコミュニケーション能力が著しく低下するため、思い込みを排除して確認を取ることが最優先

### DB クリーンアップ（2026-03-15）
- 重複削除60→29件、メンバー名統一、タイトル誤字修正

### Phase 5 実用化チューニング（2026-03-14）
- FBエラーハンドリング強化
- Mac側 relay adapter 実投稿運用化
- 音声FB/STT外部保存拡張
- API/Swift安定化

### Phase 3-4 全機能実装（2026-03-13）
- Python側10新規ファイル、14APIエンドポイント追加
- Swift側新画面5つ追加
- xcodebuild BUILD SUCCEEDED

### Phase 1-2 コアエンジン実装（2026-03-09〜10）
- 28機能実装、250+テスト全PASS
- E2Eテスト・GitHub Pages公開
