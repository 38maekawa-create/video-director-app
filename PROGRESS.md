# PROGRESS.md — 映像品質追求・自動ディレクションシステム（AI開発10）

## 最終更新日時
2026-03-13 02:45 (シミュレータ実データ表示成功・Codex CLIにUI品質向上タスク委譲)

## 現在の作業状態
**本番運用可能** — E2Eテスト完了、GitHub Pages公開+スプシ連携動作確認済み。**WebアプリMVP完成**。**ネイティブiOSアプリ: シミュレータ動作確認済み、UI品質向上中**

### ネイティブiOSアプリ化（2026-03-13 シミュレータ実データ表示成功）
スマホからYouTube素材（サムネ指示書・タイトル案・概要欄）の閲覧・編集を可能にするネイティブアプリ。

**Phase1-5 完了（バックエンド+Swift UI+実データ接続）**:
1. **FastAPI + SQLiteバックエンド** — `src/video_direction/integrations/api_server.py`
   - 11エンドポイント（projects CRUD, youtube-assets UPSERT, description/title PATCH, feedbacks, quality summary）
   - SQLite WALモード、DB: `~/.data/video_director.db`、ポート8210
   - launchd自動起動登録済み（`com.maekawa.video-direction-api.plist`、bootstrap成功）
   - DB: 60プロジェクト、60 YouTube素材、1フィードバック
2. **main.pyにAPI同期ステップ追加** — パイプライン実行後、自動的にプロジェクト+YouTube素材をAPIサーバーに投入
3. **データ投入スクリプト** — `scripts/seed_api_data.py`(プロジェクト60件) + `scripts/populate_youtube_assets.py`(YouTube素材60件)
4. **Swift側（Codex CLI実装 + バティ側ビルド修正）**:
   - 14 Swiftファイル（Models, Views, ViewModels, Services）
   - Codex CLIがpaoで9ファイル新規作成/変更
   - バティ側でビルドエラー3種を修正:
     - VideoProject/FeedbackItem の Encodable準拠（encode(to:) 明示実装）
     - Swift 6 Optional バインディング修正
     - WebViewRepresentable.swift の pbxproj登録
   - Info.plist: ATS例外ドメイン追加、マイク/音声認識/ネットワーク権限設定
   - APIレスポンスのBoolean変換修正（SQLite 0/1 → JSON true/false）
5. **シミュレータ動作確認**: iPhone 17 Pro シミュレータで起動、APIから60件の実データ取得・表示成功

**現在進行中（Codex CLI on pao）**:
- TASK_SWIFT_POLISH.md に基づくUI品質向上
  - DirectionReportView 7タブ実装
  - QualityDashboardView/FeedbackHistoryView 実データ対応
  - プルダウンリフレッシュ統一、エラーUI改善

**次のステップ**:
- Codex CLI完了→同期→ビルド検証→エラー修正
- Bundle ID変更（com.example.→本番）+ Team ID設定（UHNBL94PS9）
- iPhone実機テスト→TestFlight配布
- Distribution Certificate作成（Apple Developer Portal、なおとさん操作必要）

### YouTube素材3機能追加（2026-03-12 完了）
ディレクションレポート生成時に、以下3つのYouTube公開用素材を同時生成する機能を追加:
1. **Z型サムネイル指示書** — 青木さんのZ理論に基づく4ゾーン構成の設計指示（LLM生成）
2. **タイトル考案** — 過去タイトルパターン+マーケティング原則から3-5案提案（LLM生成）
3. **概要欄文章** — コピペ可能な完成版テキスト（冒頭フック→サマリー→タイムスタンプ→CTA→ハッシュタグ）

**新規ファイル（5ファイル）**:
- `src/video_direction/knowledge/loader.py` — KnowledgeLoader（Z理論・マーケ原則・過去タイトル・過去概要欄の読み込み）
- `src/video_direction/knowledge/prompts.py` — 3機能分のLLMプロンプトテンプレート
- `src/video_direction/analyzer/thumbnail_designer.py` — Z型サムネ指示書生成
- `src/video_direction/analyzer/title_generator.py` — タイトル考案
- `src/video_direction/analyzer/description_writer.py` — 概要欄文章生成

**修正ファイル（3ファイル）**:
- `src/video_direction/main.py` — パイプラインにYouTube素材生成ステップ追加
- `src/video_direction/reporter/html_generator.py` — 3セクション追加（サムネグリッド/タイトルカード/概要欄プレビュー）
- `src/video_direction/reporter/template.py` — CSS追加

**後方互換性**: `generate_direction_html()` の新引数は全てOptional。既存テスト3件パス確認済み。

**過去概要欄few-shot取得（2026-03-13 完了）**:
- YouTube Data API v3 → yt-dlpに切り替え（APIキー不要）
- TEKOチャンネル（UCNEsgjVHvL4y0suJGwu8ZPg）から最新10件の概要欄を自動取得
- 24時間ローカルキャッシュ（`~/AI開発10/.cache/youtube_descriptions.json`）
- 概要欄生成時のfew-shotとしてプロンプトに注入し、TEKOチャンネルのフォーマット・トーンを学習

### 次の拡張候補（2026-03-11 整理）
- 各動画固有ページで、編集前素材 / ディレクション / 編集後動画 / FB評価 / 素材ナレッジを統合表示する before / after 機能拡張
- 指示書: `TASK_BEFORE_AFTER_INTEGRATION.md`

### before / after 統合カルテ v1（2026-03-11 進行中）
- `data.js` に `videoId` を導入し、各案件へ `sourceVideo / editedVideo / feedbackSummary / knowledge / vimeoReview` を追加
- `historyItems` も `videoId` 紐付けへ拡張し、案件単位の FB タイムラインを追えるようにした
- 詳細ページタブを `概要 / ディレクション / 素材 / 編集後 / FB / 評価 / ナレッジ` 構成へ拡張
- `概要` タブで before / after 比較、連携状況、案件サマリーを表示
- `素材` / `編集後` タブで、それぞれの URL・状態・要約を分離表示
- `FB / 評価` タブで、音声FB → 変換後レビュー → 参考事例URL を含むタイムライン表示を追加
- `ナレッジ` タブで、素材ナレッジ要約 + 既存 knowledge iframe を統合表示
- 対象ファイル: `data.js`, `app.js`, `styles.css`

### 動画ナレッジページ閲覧機能（2026-03-11 完了）
- レポート詳細画面に「ナレッジ」タブを追加。ゲスト名ベースで自動マッチング
- `~/video-knowledge-pages/` のTEKO対談動画HTML 28件から24名分を `knowledge-pages/` にコピー
- ビルドスクリプト `scripts/build_knowledge_pages.py` でマッチング+コピー+マッピングJS生成を自動化
- マッチングロジック: ゲスト名の正規化（小文字化・敬称除去・記号除去）→ 完全一致 → 部分一致
- fix_付きファイル優先、_clean付きファイル優先、日付新しいもの優先
- ナレッジページがないゲストはタブ非表示（既存UI破壊なし）
- iframe埋め込み + 「別タブで開く」リンク
- モックデータ5名中2名（けー、hirai）がマッチ。残3名はナレッジページ未生成
- 全ファイルHTTP 200確認、JS構文チェックOK

### WebアプリMVP（2026-03-11 完了）
- ルート配信ディレクトリにHTML+CSS+JS（フレームワーク不使用）でNetflix風UIを再現
- 4画面実装: ホーム（ヒーロー+カルーセル）、レポート詳細（タブ+折りたたみ）、履歴（フィルタ+日付グループ化）、品質ダッシュボード（Canvas折れ線グラフ）
- PWA対応: manifest.json + service-worker.js + アイコン（192/512）
- 録音モーダル（中央赤丸ボタン）
- レスポンシブ対応（iPhone SE〜Pro Max、タブレット中央寄せ）
- フォント: ゲスト名=Georgia太字letter-spacing:3px、タイトル=Georgiaイタリックweight:300、ヘッダー=コンデンスド赤#E50914 letter-spacing:4px
- ローカル動作確認済み（python3 -m http.server 8080、全ファイルHTTP 200、JS構文チェックOK）
- 残: Phase 4 の高精度化

### 配信正本ルール（2026-03-11 追記）
- GitHub Pages が配信する **ルートディレクトリ** を正本とする
- `webapp/` 配下は過去の作業コピーであり、今後の機能追加・修正の正本にしない
- UI修正、ナレッジページ生成、PWA関連ファイル更新はルート配信ディレクトリへ反映する
- `knowledge-pages-map.js` と `knowledge-pages/` もルート配下を正本とする

## ここまでの作業サマリー

### 初期化フェーズ（2026-03-09 完了）
- ワークスペース初期化完了（ディレクトリ構造・CLAUDE.md・config.yaml・requirements.txt）
- ~/TEKO/knowledge/raw-data/video-direction/ 作成（生データ格納プロトコル準拠）

### 要件定義フェーズ（2026-03-10 完了）
- 40機能提案から28機能に取捨選択（なおとさん承認済み）
- docs/REQUIREMENTS.md 作成完了（全要件定義）
- TASK_PHASE1_CORE_ENGINE.md 作成完了（Phase 1タスク指示書）

### Phase 1 コアエンジン実装（2026-03-09 完了）
9機能すべて実装完了:

| 機能ID | 機能名 | ファイル |
|--------|--------|----------|
| A-1 | ゲスト層自動分類（層a/b/c） | `src/video_direction/analyzer/guest_classifier.py` |
| A-2 | 年収演出判断 | `src/video_direction/analyzer/income_evaluator.py` |
| A-3 | 年収以外の強さ発掘 | `src/video_direction/analyzer/income_evaluator.py` |
| A-4 | 固有名詞フィルター | `src/video_direction/analyzer/proper_noun_filter.py` |
| A-5 | ターゲットラベリング | `src/video_direction/analyzer/target_labeler.py` |
| NEW-1 | 演出ディレクション生成 | `src/video_direction/analyzer/direction_generator.py` |
| H-1 | メンバーマスター連携 | `src/video_direction/integrations/member_master.py` |
| J-1 | AI開発5コネクター | `src/video_direction/integrations/ai_dev5_connector.py` |
| J-2 | スプレッドシート連携 | `src/video_direction/integrations/sheets_manager.py` |

#### Phase 1 テスト
- 全50テストパス（pytest）
- テストファイル9本: `tests/test_*.py`
- 実データ30件の一括処理でエラー0件

#### 自走修正3サイクル完了
- **サイクル1**: 9件のバグ修正（年収抽出の誤検出、分類の誤判定等）
- **サイクル2**: 全30件の網羅性チェック、6件の分類精度改善（仮定文脈除外、カンマ数値正規化、非本人属性除外等）
- **サイクル3**: HTML出力のユーザー視点検証、最終レポート出力
- 検証レポート: `output/VERIFICATION_REPORT.md`

#### 分類結果サマリー（全30件）
- 層a: 12件 / 層b: 18件 / 層c: 0件
- 主な層a: Izu(3000万), みんてぃあ(2200万), スリマン(1900万), あさかつ(1500万), てぃーひろ(1400万), RYO(1100万), 松本(1050万), しお(1020万), ゆきもる(1000万), ハオ(1000万), 羽生氏(1000万), 坂さん(監査法人)

### Phase 3 パイプライン統合（2026-03-09 完了）
5機能実装完了 + 100テスト追加:
- config_loader: YAML設定ファイルの読み込みと検証
- pipeline_orchestrator: パイプライン全体の制御
- file_watcher: AI開発5の新規ファイル監視
- batch_processor: 全件一括処理
- pipeline_e2e: パイプラインE2Eテスト

### Phase 2 全機能実装（2026-03-10 完了）
Phase 2の全9機能を実装完了。250テスト全パス。

#### Phase 2 Tier 1: 編集支援基盤（3機能 — 既存）

| 機能ID | 機能名 | ファイル | 行数 |
|--------|--------|----------|------|
| E-1改 | 切り抜きカットポイント提案 | `src/video_direction/analyzer/clip_cutter.py` | 342行 |
| NEW-2 | ハイライトカットポイントディレクション | `src/video_direction/analyzer/highlight_cutter.py` | 343行 |
| B-1 | 7要素品質スコアリング（推定版） | `src/video_direction/analyzer/quality_scorer.py` | 479行 |

#### Phase 2 Tier 2-4（6機能 — 新規）

| 機能ID | 機能名 | ファイル |
|--------|--------|----------|
| C-2 | テロップ自動チェック | `src/video_direction/analyzer/telop_checker.py` |
| C-1 | フレーム画像マルチモデル評価（スタブ） | `src/video_direction/analyzer/frame_evaluator.py` |
| C-3 | 音声品質自動評価（スタブ） | `src/video_direction/analyzer/audio_evaluator.py` |
| B-2 | 品質トラッキングダッシュボード | `src/video_direction/tracker/quality_dashboard.py` |
| B-3 | 編集者別スキルマトリクス | `src/video_direction/tracker/skill_matrix.py` |
| NEW-3 | 編集後動画FB | `src/video_direction/analyzer/post_edit_feedback.py` |

### E2E完走テスト（2026-03-10 完了）

#### direction-pages リポジトリ
- リポジトリ: `38maekawa-create/direction-pages`（既存、GitHub Pages有効）
- 公開URL: https://38maekawa-create.github.io/direction-pages/
- 32件のHTMLディレクションレポートを公開中

#### GitHub Pages E2Eテスト結果
- 全30件のHTMLレポートを生成 → direction-pagesにpush
- 全ページHTTP 200確認（index.html + 個別レポート）
- ブラウザ表示正常（日本語・CSS・レスポンシブ対応）

#### スプシ連携E2Eテスト結果
- スプレッドシートID: `1bW_qb13p747xoa2yf7RHaccNVTFCMxV8a5CjGdNqI6I`
- タブ: 【インタビュー対談動画】管理（84件登録済み）
- ディレクションURL列（65列目）に書き込み成功（Izu/PAY/RYO）
- 既存URL上書き防止機能正常動作

#### バグ修正（E2Eテスト中に発見・修正）
1. **main.py**: ゲスト名フォールバック追加（プロファイル空の場合にタイトルから抽出）
2. **sheets_manager.py**: ゲスト名マッチングをcase-insensitive化 + 番号形式マッチング追加 + 1文字名ガード追加

#### 自走修正3サイクル完了（E2E）
- **サイクル1**: コード品質検証。5件検出（中1件: 1文字誤マッチ → 修正、低2件、情報2件）
- **サイクル2**: 全30件網羅性チェック。不明ゲスト0件（修正前2件→解消）。スプシマッチ15/30件（残りはスプシ側未登録）
- **サイクル3**: ユーザー視点検証。GitHub Pages・個別レポートの表示品質確認
- 検証レポート: `output/E2E_VERIFICATION_REPORT.md`

### Phase 4 計画書作成（2026-03-10 完了）
- `docs/PHASE4_PLAN.md` 作成
- 12機能の実装計画・優先順位・依存関係を整理
- P0: C-1/C-3実映像対応（opencv/ffmpeg）
- P1: 人間FB学習 + 巡回監査 + 通知
- P2-P3: 映像トラッキング + 管理 + インフラ

### スマホアプリ UI Netflix風リデザイン（2026-03-11 完了）
- タスク指示書: `TASK_UI_NETFLIX_REDESIGN.md`
- 全5画面をNetflix風ダークUI（黒#000000 + 赤#E50914 + 白）に全面書き換え
- 画面1（ホーム）: ヒーローバナー + カルーセル横スクロール + 検索バー
- 画面2（レポート詳細）: ゲスト情報ヘッダー + タブ切替 + 折りたたみセクション + Vimeoリンク + 下部固定FBボタン
- 画面3（音声FB）: 全画面モーダル + 大きな録音ボタン + 波形アニメーション + Before/After変換UI
- 画面4（FB履歴）: 日付グループ化タイムライン + フィルタ（すべて/未送信）+ 検索
- 画面5（品質ダッシュボード）: 大きなスコア表示 + 折れ線グラフ + カテゴリ別スコア + AI改善提案
- カスタムタブバー: 中央に大きな赤い録音ボタン（Instagram風）
- モックデータで全画面動作確認
- Xcodeビルド成功（iPhone 17 Simulator, iOS 26.3.1）

### before / after 統合カルテ v1.1（2026-03-11 進行中）
- mock relay server + send CLI で relay ローカル往復成功（sample request 1件 / postedCount=1）
- root正本の `data.js` / `app.js` / `styles.css` を拡張
- 一覧カードで `素材 / 編集後 / KB / Vimeo / FB件数 / 最新FB` を可視化
- 詳細ページを `概要 / ディレクション / 素材 / 編集後 / FB / 評価 / ナレッジ` へ拡張
- `BEFORE / AFTER` 比較ボードを追加
- `FB / 評価` に Vimeoレビューモード風タイムラインとマーカーUIを追加
- 各FBに変換レビュー、参考事例URL、同期状態を表示
- `素材ナレッジ要点` と `transcriptPreview` を統合カルテへ追加
- `レビュー同期キュー` を追加し、未送信レビューを概要/編集後画面から追えるようにした

- `relay送信用 curl` と Mac側中継APIリクエストのプレビュー/コピー導線を追加
- `docs/VIMEO_RELAY_ADAPTER_SPEC.md` を追加し、Mac側 relay adapter の入出力仕様を固定
- `scripts/send_vimeo_relay_package.py` を追加し、relay request JSON を POST するCLI叩き台を作成
- `scripts/mock_vimeo_relay_server.py` を追加し、Mac側 relay adapter の最小モック受け口を用意
- `scripts/post_vimeo_review_comments.py` を追加し、Vimeo API 実投稿アダプタの叩き台を作成（dry-run対応）
- `scripts/mock_vimeo_relay_server.py` を relay 本体寄りに拡張し、`mock / dry_run / post` のモード切替に対応
- relay server(`dry_run`) -> `send_vimeo_relay_package.py` -> `post_vimeo_review_comments.py --dry-run` の往復を成功確認
- 音声フィードバックモーダルに実マイク入力とリアルタイム文字起こしの本線を追加
- 録音中の文字起こし / エラー / ブラウザ対応状況をモーダル内で可視化
- 録音した文字起こしを案件FB履歴へ追加し、そのまま review queue / FBタイムラインへ反映できるようにした
- relay / Vimeo 結果JSONの取り込みUIを追加し、案件ごとの同期状態を戻り線で更新できるようにした
- `send_vimeo_relay_package.py` / `post_vimeo_review_comments.py` に `--output` を追加し、結果JSONをファイル保存できるようにした
- `localStorage` 永続化を追加し、案件状態 / FB履歴 / 同期状態を再読み込み後も保持できるようにした

## 未完了の作業
- Mac側 relay adapter の実投稿運用化（本番トークン / ログ運用 / 再送設計）
- Vimeo API 実コメント投稿
- 音声FBの実録音 / STT 結果をローカル永続ストレージから外部保存先へ拡張
- 映像品質学習の本線実装

## 次にやるべき作業（優先順位付き）
1. **Phase 4A: C-1/C-3実映像対応** — opencv/ffmpegインストール→スタブから実測値への切り替え
2. **Phase 4B: 映像トラッキング+学習** — NEW-4/5/6/7（外部映像収集・分析・FB学習）
3. **Phase 4C: 管理+インフラ** — NEW-8, F-3, J-3/4/5/6（編集者管理・巡回監査・通知・PDCA）
4. **スプシマッチング精度改善** — 15/30 → 目標25/30以上

## 既知の問題・課題
1. **層cの該当者0件**: 現在のデータセット30件に自営業家系の該当者がいない。追加データで検証が必要
2. **Python 3.9 EOL警告**: google-auth, urllib3がPython 3.9サポート終了の警告を出す
3. **LLM分析はオプション**: Claude Sonnet APIキーがない場合でも基本機能は動作するが、追加分析は生成されない
4. **品質スコアリングは推定値**: Phase 2実装は文字起こし・メタデータベースの推定。C-1（opencv）/C-3（ffmpeg）実装後に実測値に切り替え
5. **C-1/C-3はスタブ実装**: opencv/ffmpegの実際のインストールとAPI連携はPhase 4A。現在は文字起こしベースの推定で動作
6. **スプシマッチング**: 30件中15件マッチ。ゲスト名の正規化（括弧・敬称除去）やスプシ側の登録追加で改善可能
7. **index.htmlのURLエンコーディング**: 日本語ファイル名がhrefにURLエンコードなしで入る。主要ブラウザでは動作するがPhase4で改善予定
