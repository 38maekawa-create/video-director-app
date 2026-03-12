# タスク指示書: Swift UI 品質向上

## 目的
Video Director Agent iOSアプリのUI品質を実運用レベルに引き上げる。現在シミュレータで実データ表示に成功しており、デザイン面の仕上げが必要。

## 背景
- FastAPI + SQLite バックエンドが稼働中（60プロジェクト、60 YouTube素材）
- アプリはAPIからデータ取得に成功（モックデータではなく実データが表示されている）
- Codex CLIが作成したSwiftファイルにXcodeビルドエラーがあったが修正済み（Codable準拠、Swift 6 Optional、pbxproj登録）
- 次ステップはUI磨き→TestFlight配布

## 全体工程における位置づけ
Phase 2-7のうち、Phase 6（UI品質向上）に相当。これが完了すればTestFlight配布可能。

## 作業項目

### 1. DirectionReportView.swift の7タブ実装確認・修正
現在4タブ（演出/テロップ/カメラ/音声FB）を7タブに拡張する指示があったが、実装されているか確認。
必要なタブ: 演出 / テロップ / カメラ / 音声FB / サムネ / タイトル / 概要欄
- 「サムネ」タブ: YouTubeAssetsViewの thumbnail_design セクションを表示
- 「タイトル」タブ: YouTubeAssetsViewの title_proposals セクションを表示
- 「概要欄」タブ: YouTubeAssetsViewの description セクションを表示
すでにYouTubeAssetsView.swiftが3セクション構成で実装されているなら、DirectionReportViewの各タブからそれぞれのセクションを呼び出す形でもよい。

### 2. QualityDashboardView.swift の実データ対応
品質ダッシュボードAPIが存在する:
- GET /api/quality/summary → {total_projects, with_assets, avg_quality_score, recent_feedbacks}
DashboardViewModel.swift からAPIを叩いて実データを表示するよう修正。

### 3. FeedbackHistoryView.swift の実データ対応
フィードバック一覧APIが存在する:
- GET /api/feedbacks?limit=50 → [{id, project_id, content, created_by, created_at, ...}]
現在モックデータを表示している場合、APIから取得するよう修正。

### 4. プルダウンリフレッシュの統一実装
全てのリスト画面（ProjectListView, FeedbackHistoryView）に `.refreshable` モディファイアを適用。

### 5. エラー状態のUI改善
API接続失敗時のエラーメッセージを、現在の長文テキストからユーザーフレンドリーな表示に変更:
- "接続できません。Wi-Fiを確認してください" 程度のシンプルなメッセージ
- リトライボタンを追加

## 対象ファイル
```
VideoDirectorAgent/VideoDirectorAgent/
├── Models/Models.swift
├── Models/MockData.swift
├── Services/APIClient.swift
├── ViewModels/ProjectListViewModel.swift
├── ViewModels/VoiceFeedbackViewModel.swift
├── ViewModels/DashboardViewModel.swift
├── Views/RootTabView.swift
├── Views/ProjectListView.swift
├── Views/DirectionReportView.swift
├── Views/YouTubeAssetsView.swift
├── Views/WebViewRepresentable.swift
├── Views/VoiceFeedbackView.swift
├── Views/FeedbackHistoryView.swift
└── Views/QualityDashboardView.swift
```

## 完了条件
1. DirectionReportViewに7タブが表示される
2. QualityDashboardViewがAPIから実データを取得して表示する
3. FeedbackHistoryViewがAPIから実データを取得して表示する
4. 全リスト画面でプルダウンリフレッシュが動作する
5. エラー表示がユーザーフレンドリー

## 注意事項
- Swift 6 Concurrency: `@MainActor`, `Sendable` を厳守
- UIFont禁止、Font.custom() のみ使用
- AppThemeの色・フォント定義を使うこと
- Xcodeはこのマシンにないため、xcodebuildでのビルド確認は不要。Swiftファイルの編集のみ行う
- APIのベースURL: http://localhost:8210（テスト時）
- APIレスポンスはsnake_caseで、Swift側は`.convertFromSnakeCase`で変換済み
