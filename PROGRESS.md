# PROGRESS.md — 映像品質追求・自動ディレクションシステム（AI開発10）

## 最終更新日時
2026-03-16 （TASK_P2_QUALITY_DASHBOARD.md実施 — 品質ダッシュボード実データ連動完成）
<!-- authored: Claude Code/2026-03-16 [なおとさん指示: P2品質ダッシュボード実データ連動] -->

## 現在の作業状態
**P2完了: 品質ダッシュボード実データ連動 iOS UI + APIエンドポイント実装済み**

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
- けーさん（p-20260101-Kさん）: 2026/01/25 → **2026/02/28** ✅
- ゆりかさん（p-20260101-ユリカ）: 2026/01/25 → **2026/02/28** ✅
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

### [P0-BLOCKED] Vimeo API本番投稿（要なおとさん承認）
- **前提条件**: `~/.config/maekawa/api-keys.env` に `VIMEO_ACCESS_TOKEN` を設定
- 実行コマンド: `python3 scripts/post_vimeo_review_comments.py relay.json --execute`
- 疎通確認: `VIMEO_ACCESS_TOKEN` 設定後に `--dry-run` モードで `/videos/{id}/comments` エンドポイントへの到達確認

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
- FB学習ループの運用データ投入
- 評価ルール精度改善

---

## 既知の問題・課題

| # | 問題 | 状態 |
|---|------|------|
| 1 | YouTubeAssetsViewModel.swiftのbaseURLがlocalhost:8210ハードコード | 未修正（APIClient.sharedを使うべき） |
| 2 | feedbacksテーブルが空（0件） | 正常。録音機能からFB投入後にデータが蓄積される |
| 3 | xcodebuild署名: `CODE_SIGN_STYLE=Automatic`ではなく手動指定が必要 | TT2DA7H5NJ + "Apple Development" で解決済み |
| 4 | 層cの該当者0件: 現データセット29件に自営業家系なし | 追加データで検証必要 |
| 5 | さくらさんのshoot_date未確認 | タイトル「202512オフ会」のため大阪2/28組かどうか不明。現在2025/12/13のまま。なおとさんに要確認 |

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
