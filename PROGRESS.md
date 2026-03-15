# PROGRESS.md — 映像品質追求・自動ディレクションシステム（AI開発10）

## 最終更新日時
2026-03-15（webapp YouTube素材UI完成・524件全PASS）

## 現在の作業状態
**完了（webapp YouTube素材3機能UI追加済み）**

webapp/app.js・webapp/styles.css に YouTube素材3機能UIを追加。既存コードへの削除・変更なし（追加のみ）。Python 524テスト全PASS。

### webapp YouTube素材UI追加内容（2026-03-15 最新）
<!-- authored: T3/兵隊B/AI開発10/2026-03-15 [TASK指示書に基づく] -->

**変更ファイル:**
- `webapp/app.js`: YouTube素材タブ追加 + 描画関数群追加
- `webapp/styles.css`: YouTube素材UI用CSSクラス追加

**追加した3機能:**
1. **サムネ生成ディレクション（Z型4ゾーン指示書）**
   - `renderYouTubeAssets()` が API `GET /api/projects/{id}/youtube-assets` からデータ取得
   - `thumbnail_design` の4ゾーン（top_left/top_right/diagonal/bottom_right）をカードUIで表示
   - 各ゾーンに色分け（①赤=左上フック、②青=右上人物、③黄=対角テーマ、④緑=右下CTA）
   - APIオフライン時はプロジェクトデータからローカル生成（フォールバック）

2. **タイトル案（タップでコピー）**
   - `title_proposals.candidates` を縦リスト表示（推薦案には「推薦」バッジ）
   - タップで `navigator.clipboard.writeText()` → 古いブラウザは `execCommand` フォールバック
   - コピー完了時に「✓ コピー完了！」表示（2秒後に元に戻る）

3. **概要欄テキスト**
   - `description_edited` または `description_original` を `<pre>` でテキスト整形保持
   - 右上の「コピー」ボタンでワンタップコピー

**実装方針（既存コード無変更）:**
- `renderReportTabs()` 内のtabs配列に `'YouTube素材'` を追記
- click handlerに `else if (tabName === 'YouTube素材')` を追記
- 新関数群は全てIIFEのクロージング直前に追記

### テスト実行結果（2026-03-15 最新）
- **総テスト件数: 524件 全PASS（所要時間: 約25秒）**
- テストファイル数: 36ファイル（tests/内）
- 備考: `test_api_phase3_4.py`・`test_feedback_learning_api.py` の2ファイルは `fastapi` パッケージが必要（python3.11環境にインストール済みで実行可能）
- warnings: 2件（fastapiの `on_event` 非推奨警告、動作には影響なし）

### 直近の作業（2026-03-15）
- エッジケーステスト25件追加（499 → 524件）
- 追加テストファイル: `tests/test_edge_cases.py`（25件）
  - 空データ系（6件）: 空ハイライト/空プロファイル/空文字列/空FB/空URLなど
  - 不正フォーマット系（8件）: 不正タイムスタンプ/不正JSON/存在しないファイル/特殊文字/極端に長いテキスト
  - タイムアウト系（3件）: yt-dlpタイムアウト/コマンド未インストール/LLMタイムアウト
  - 並行実行系（3件）: VideoTracker/FeedbackLearner/generate_directionsの並行呼び出し
  - 境界値・その他（5件）: ハイライト1件/重複URL/存在しないID参照/カテゴリ自動推定
- バグ修正: `_timestamp_to_seconds`（`"abc:def"` 形式でValueErrorが発生）→ try-except でガード
- 全524件 PASS 確認

### 2件前の作業（2026-03-15）
- テスト未カバーモジュール3件（video_tracker / video_learner / video_analyzer）を特定
- ユニットテスト56件追加（443 → 499件）
- 追加テストファイル: `tests/test_video_tracker.py`（20件）、`tests/test_video_learner.py`（22件）、`tests/test_video_analyzer.py`（14件）
- 全499件 PASS 確認

---

## 次にやるべき作業（優先順位付き）

### [P0] TestFlight配布実行（Mac1（hime）で）

**前提条件（なおとさん操作）**:
1. App-Specific Password 発行
   - https://appleid.apple.com → セキュリティ → App-Specific Password
   - Mac1（hime）で: `echo 'xxxx-xxxx-xxxx-xxxx' > ~/.config/maekawa/asc-password`
2. Apple IDはXcodeに登録済み（`7010mae@gmail.com`）
3. App Store Connect でアプリ未登録なら登録
   - Bundle ID: `com.maekawa.VideoDirectorAgent` / 主言語: 日本語 / カテゴリ: ユーティリティ

**スクリプト実行**:
```bash
cd ~/AI開発10
./deploy-testflight.sh
```

**完了後**:
- App Store Connect → TestFlight → テスター追加（5〜15分待機後）

### [P1] 映像品質学習の本線実装
- FB学習ループの運用データ投入
- 評価ルール精度改善

---

## 既知の問題・課題

| # | 問題 | 状態 |
|---|------|------|
| 1 | 実機ビルド: Provisioning Profile自動生成 | Apple IDはXcodeに登録済み（解消済み） |
| 2 | launchd API起動: `curl http://localhost:8210/api/health` | 正常応答確認済み（PID:17171で稼働中・解消済み） |
| 3 | 層cの該当者0件: 現データセット30件に自営業家系なし | 追加データで検証必要 |
| 4 | スプシマッチング精度: 30件中15件マッチ（50%） | ゲスト名正規化実装済み、スプシ側未登録が主因 |
| 5 | Python 3.9 EOL警告: google-auth, urllib3が警告出力 | 低優先度 |

---

## 完了済み作業アーカイブ

### テストカバレッジ向上（2026-03-15）
カバレッジが低い4モジュールに95件の新規ユニットテストを追加。402テスト全PASS。

| テストファイル | 件数 | 対象モジュール |
|-------------|------|-------------|
| `tests/test_feedback_learner.py` | 31件 | `tracker/feedback_learner.py` |
| `tests/test_sheets_manager_helpers.py` | 32件 | `integrations/sheets_manager.py` |
| `tests/test_knowledge_loader.py` | 16件 | `knowledge/loader.py` |
| `tests/test_direction_generator_extended.py` | 16件 | `analyzer/direction_generator.py` |

テスト数推移: 348 → **402件**

### APIリファレンスドキュメント（2026-03-15）
- `docs/API_REFERENCE.md` 新規作成
- 全40エンドポイントを14カテゴリに整理

### TestFlight配布準備（2026-03-15）
- `deploy-testflight.sh` 作成（Archive→Export→ASC Upload 全工程自動化）
- `VideoDirectorAgent/ExportOptions.plist` 作成
- Bundle ID: `com.maekawa.VideoDirectorAgent` / Team ID: `TT2DA7H5NJ`
- CFBundleVersion: ハードコード→ `$(CURRENT_PROJECT_VERSION)` に修正済み
- **Xcodeは Mac1（hime）に導入済み。スクリプト実行は Mac1（hime）で行う**

### Phase 5 実用化チューニング（2026-03-14）
- FBエラーハンドリング強化（`post_vimeo_review_comments.py`）
- Mac側 relay adapter 実投稿運用化（ログ日付階層化・再送キュー）
- 音声FB/STT外部保存拡張（feedbackOutbox + API自動flush）
- API/Swift安定化（MockData参照除去・APIClient設定駆動化）
- テスト数: 320 → 330 → 334件

### Phase 3-4 全機能実装（2026-03-13）
- Python側: 10新規ファイル実装（frame_evaluator, audio_evaluator, feedback_learner 他）
- APIサーバー: 14エンドポイント追加（合計40+）
- Swift側: 新画面5つ追加（EditorManagement, VideoTracking, NotificationSettings 他）
- xcodebuild BUILD SUCCEEDED（エラー0件）
- iPhone 17 Pro シミュレータで実データ表示確認済み

### ネイティブiOSアプリ化（2026-03-13）
- FastAPI + SQLiteバックエンド（ポート8210）
- 14 Swiftファイル（Models/Views/ViewModels/Services）
- DB: 60プロジェクト・60 YouTube素材・1フィードバック
- Info.plist: ATS例外・マイク/音声認識/ネットワーク権限設定済み

### before/after統合カルテ + Webアプリ（2026-03-11）
- Netflix風ダークUI（5画面）
- PWA対応（manifest.json + service-worker.js）
- localStorage永続化
- relay server → send CLI → Vimeo API 往復確認済み
- 動画ナレッジページ閲覧機能（28件中24名分マッチ）

### YouTube素材3機能追加（2026-03-12）
- Z型サムネイル指示書生成
- タイトル考案（3〜5案）
- 概要欄文章生成（few-shot: TEKOチャンネル最新10件）

### Phase 2 全機能実装（2026-03-10）
- 9機能実装（切り抜きカットポイント、ハイライトディレクション、品質スコアリング 他）
- 250テスト全PASS

### E2Eテスト・GitHub Pages公開（2026-03-10）
- direction-pages リポジトリで32件のHTMLレポート公開
- スプシ連携E2E（ディレクションURL列への書き込み成功）

### Phase 1 コアエンジン実装（2026-03-09）
- 9機能実装（ゲスト層分類・年収演出判断・固有名詞フィルター 他）
- 50テスト全PASS、実データ30件エラー0件

### 初期化・要件定義（2026-03-09〜10）
- ワークスペース初期化
- 40機能から28機能に取捨選択（なおとさん承認済み）
- `docs/REQUIREMENTS.md` 作成
