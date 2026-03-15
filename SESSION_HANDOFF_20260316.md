# セッション引き継ぎ — 2026-03-16 映像エージェント Build 19

## 現在の状態
- **Build 19**: ビルド成功（626テストPASS）、USB実機インストール済み
- **TestFlight**: 上限到達中。リセット後に `/tmp/VideoDirectorAgent_B19.xcarchive` からアップロード
- **ホーム/レポート空表示**: ✅修正済み（ProjectStatus snake_case decode修正）
- **カルーセルタップ**: ✅Build 15で解決済み（UICollectionView+didSelectItemAt）
- **撮影日**: けー・ゆりかは2026/01/25が正。DB修正済み

## Build 19で追加された主な機能
1. VimeoPlayerView + VimeoTimelineView + VimeoReviewTabView（レポート「レビュー」タブ）
2. EditFeedbackView（before/after差分UI、グレードバッジ付き）
3. VideoTrackingView改善（学習状況サマリーカード）
4. QualityDashboardView改善（グレード分布カード）
5. ProjectStatus snake_case→camelCase decode修正（Build 18空表示バグの根本修正）

## 未解決・次にやるべきこと

### すぐやるべき
1. **VimeoReviewViewModel.swift L27**: `localhost:8210` がハードコード → APIClient.shared.baseURL に修正
2. **大阪撮影7名のshoot_date**: API側で2026/01/01に誤設定されている件（DBは修正済みだが要確認）
3. **さくらさんの撮影日確認**: 「202512オフ会」で2025/12/13だが、大阪2/28組かどうかなおとさんに要確認

### 中期
- source/edited_video: DBフィールドはあるが全件null
- トラッキング実データ投入（NEW-4〜7のUIはあるがデータなし）
- Mac3のgit同期（古い状態のまま）
- test_vimeo_api_server.pyのimportパス統合

### TestFlight
- アーカイブ: `/tmp/VideoDirectorAgent_B19.xcarchive`
- 上限リセット後に `xcodebuild -exportArchive` → `xcrun altool --upload-app`

## 今セッションで発生したインシデント
1. **compactionによるキャラ消失**: セッション途中でcompactionが入り、バティの口調・行動原則が消えた。なおとさんに指摘されるまで気づかなかった
2. **T4虚偽記録**: 兵隊がPROGRESS.mdに撮影日修正を「✅」で記録していたが、実際は誤修正だった
3. **対策**: lint-progress-authorship.sh（署名チェックスクリプト）を ~/mac-dev-config/scripts/ に作成済み

## 重要なファイル
- `/Users/maekawanaoto/AI開発10/PROGRESS.md` — 作業履歴
- `/Users/maekawanaoto/AI開発10/KNOWN_CORRECTIONS.md` — 誤修正記録
- `/Users/maekawanaoto/AI開発10/VideoDirectorAgent/VideoDirectorAgent/Models/Models.swift` — ProjectStatus decode修正箇所
- `/Users/maekawanaoto/AI開発10/VideoDirectorAgent/VideoDirectorAgent/ViewModels/VimeoReviewViewModel.swift` — localhost残存

## チェックリスト現状（Build 19反映）
- NEW-3（編集後動画FB）: Python✅ iOS✅ — Build 19でUI実装完了
- #13-15（YouTube素材）: Python✅ iOS✅ — 変更なし
- NEW-4〜7（トラッキング・学習系）: Python✅ iOS✅ — Build 19でUI追加。実データはまだ
- B-2（品質ダッシュボード）: ✅ UIも改善、実データ29件あり
- C-1（フレーム評価）: ✅ Phase 2スタブ
- 接続問題: ⚠️ VimeoReviewViewModelにlocalhost残存（他は修正済み）

<!-- authored: T1/副官A/バティ/2026-03-16 [セッション引き継ぎ。compaction+continuation sessionからの教訓含む] -->
