# タスク指示書: Phase 3-4 Swift側 全機能実装

## 目的
映像ディレクションエージェントiOSアプリに残り全機能のUI/画面を追加する。バックエンド（Python API）は別途並列で実装されるため、Swift側はAPIエンドポイントを呼び出すViewとViewModelを実装する。

## 背景
- Phase 1-2完了: 5画面+7タブ+YouTube素材+音声FB+API接続済み
- バックエンドAPIサーバー（localhost:8210）が稼働中
- 現在 FeedbackHistoryView と QualityDashboardView がモックデータのまま
- Phase 3-4の新機能用に新しい画面・APIエンドポイントが追加される

## 全体工程における位置づけ
これが完了すれば全28機能のUI側が揃い、TestFlight配布可能。

---

## 作業項目

### 1. FeedbackHistoryView の実データ対応（最優先）

**対象ファイル**: `Views/FeedbackHistoryView.swift`

現在 `MockData.historyItems` を使用している。APIから取得するよう修正。

**APIエンドポイント**: `GET /api/feedbacks?limit=50`
**レスポンス**: `[{id, project_id, content, created_by, created_at, timestamp_mark, feedback_type, is_sent, ...}]`

**修正内容**:
- ViewModel を新規作成するか、View内で直接APIを呼ぶ
- `APIClient.swift` に `fetchAllFeedbacks()` メソッド追加
- `.refreshable` でプルダウンリフレッシュ対応
- API失敗時はモックにフォールバック

```swift
// APIClient.swift に追加
func fetchAllFeedbacks(limit: Int = 50) async throws -> [FeedbackItem] {
    try await request([FeedbackItem].self, path: "/api/feedbacks?limit=\(limit)")
}
```

---

### 2. QualityDashboardView の実データ対応（最優先）

**対象ファイル**: `Views/QualityDashboardView.swift`, `ViewModels/DashboardViewModel.swift`

現在モックデータ。APIから取得するよう修正。

**APIエンドポイント**:
- `GET /api/dashboard/summary` → `{total_projects, with_assets, avg_quality_score, status_counts, recent_feedbacks, unsent_feedback_count}`
- `GET /api/dashboard/quality-trend` → `[{guest_name, shoot_date, quality_score}]`

**修正内容**:

```swift
// APIClient.swift に追加
struct DashboardSummary: Decodable {
    let totalProjects: Int
    let withAssets: Int
    let avgQualityScore: Double?
    let statusCounts: [String: Int]
    let recentFeedbacks: [FeedbackItem]
    let unsentFeedbackCount: Int
}

struct QualityTrendItem: Decodable {
    let guestName: String
    let shootDate: String
    let qualityScore: Int?
}

func fetchDashboardSummary() async throws -> DashboardSummary {
    try await request(DashboardSummary.self, path: "/api/dashboard/summary")
}

func fetchQualityTrend() async throws -> [QualityTrendItem] {
    try await request([QualityTrendItem].self, path: "/api/dashboard/quality-trend")
}
```

DashboardViewModel を修正:
- `loadDashboard()` async メソッド追加
- `@Published var summary: DashboardSummary?`
- `@Published var trend: [QualityTrendItem]`
- API失敗時はモックにフォールバック

---

### 3. 編集者管理画面（NEW-8）— 新規画面

**新規ファイル**:
- `Views/EditorManagementView.swift`
- `ViewModels/EditorManagementViewModel.swift`

**APIエンドポイント**（バックエンド側で新規追加予定）:
- `GET /api/editors` → 編集者一覧
- `GET /api/editors/{id}` → 編集者詳細
- `POST /api/editors` → 編集者追加
- `PUT /api/editors/{id}` → 編集者更新

**画面構成**:
- 編集者カード一覧（名前・稼働状況・スキルサマリー）
- 詳細画面: スキルマトリクス（7要素レーダーチャート風）、担当案件一覧、実績推移
- 追加/編集フォーム

**Model追加** (`Models/Models.swift`):
```swift
struct Editor: Identifiable, Codable {
    let id: String
    let name: String
    let contactInfo: String?
    let status: String          // "active" / "inactive" / "on_leave"
    let contractType: String?   // "fulltime" / "freelance"
    let skills: EditorSkills?
    let activeProjects: Int
    let totalCompleted: Int
    let avgQualityScore: Double?
    let createdAt: String
}

struct EditorSkills: Codable {
    let cutting: Double       // カット割り
    let color: Double         // 色彩
    let telop: Double         // テロップ
    let bgm: Double           // BGM
    let cameraWork: Double    // カメラワーク
    let composition: Double   // 構図
    let tempo: Double         // テンポ
}
```

**RootTabView変更**: タブを追加するか、品質ダッシュボード内にサブセクションとして組み込む。
→ 推奨: 品質ダッシュボード画面の下部に「編集者」セクションを追加（タブ数を増やさない）

---

### 4. 映像トラッキング画面（NEW-4/5）— 新規画面

**新規ファイル**:
- `Views/VideoTrackingView.swift`
- `ViewModels/VideoTrackingViewModel.swift`

**APIエンドポイント**（バックエンド側で新規追加予定）:
- `GET /api/tracking/videos` → トラッキング対象映像一覧
- `GET /api/tracking/videos/{id}` → 映像分析結果
- `POST /api/tracking/videos` → 新規トラッキング登録
- `GET /api/tracking/insights` → 学習済みインサイト一覧

**画面構成**:
- トラッキング中の映像一覧（サムネ・タイトル・チャンネル名・分析ステータス）
- 分析結果詳細（構図・テンポ・カット割り・色彩の要素分解）
- 「新規追加」: YouTube URLを入力してトラッキング登録
- 「インサイト」: 学習から得られたパターン一覧

**Model追加**:
```swift
struct TrackedVideo: Identifiable, Codable {
    let id: String
    let url: String
    let title: String
    let channelName: String?
    let thumbnailUrl: String?
    let analysisStatus: String   // "pending" / "analyzing" / "completed"
    let analysisResult: VideoAnalysis?
    let createdAt: String
}

struct VideoAnalysis: Codable {
    let overallScore: Double?
    let composition: String?
    let tempo: String?
    let cuttingStyle: String?
    let colorGrading: String?
    let keyTechniques: [String]?
    let summary: String?
}

struct TrackingInsight: Identifiable, Codable {
    let id: String
    let category: String       // "cutting" / "color" / "tempo" etc
    let pattern: String        // 発見されたパターンの説明
    let sourceCount: Int       // 何件の映像から導出されたか
    let confidence: Double     // 確信度
    let createdAt: String
}
```

**配置**: DirectionReportView内の新タブではなく、RootTabViewに新しいタブを追加するか、品質ダッシュボードのサブ画面にする。
→ 推奨: QualityDashboardView にセグメントコントロールで「品質」/「トラッキング」/「編集者」を切り替えるUIにする

---

### 5. 巡回監査結果表示（J-3）

**APIエンドポイント**:
- `GET /api/audit/latest` → 最新の監査レポート
- `GET /api/audit/history` → 過去の監査レポート一覧

**画面**: QualityDashboardView 内の「アラート」セクションを拡張して実データを表示。
現在モックの `alerts` を API取得に置き換え。

```swift
struct AuditReport: Codable {
    let runAt: String
    let pipelineStatus: String       // "healthy" / "warning" / "error"
    let pendingVideos: Int           // 未処理動画数
    let qualityAnomalies: [String]   // 品質異常
    let staleProjects: [String]      // 滞留プロジェクト名
    let overallHealth: String        // "good" / "warning" / "critical"
}
```

---

### 6. 通知設定画面（J-4）

**新規ファイル**: `Views/NotificationSettingsView.swift`

**画面構成（シンプル）**:
- Telegram通知 ON/OFF トグル
- LINE通知 ON/OFF トグル
- 通知対象: レポート完成 / 品質警告 / FB受信
- チャットID入力欄

**配置**: 品質ダッシュボードの歯車アイコンから遷移

---

### 7. 品質改善ループ可視化（J-5）

DirectionReportView の「概要」タブ内に、PDCA状態を表示するセクションを追加。

```swift
// 概要タブに追加
VStack(alignment: .leading, spacing: 8) {
    Text("品質改善サイクル")
        .font(.headline)
        .foregroundStyle(AppTheme.accent)
    HStack(spacing: 16) {
        pdcaStep("D", "ディレクション", completed: true)
        pdcaStep("C", "編集", completed: displayProject.editedVideoURL != nil)
        pdcaStep("A", "評価", completed: !feedbacks.isEmpty)
        pdcaStep("R", "ルール更新", completed: false)
    }
}
```

---

### 8. VoiceFeedbackViewModel の convertFeedback() 実装

現在モック（固定テキスト）を返している `convertFeedback()` を、API経由でClaude変換するよう修正。

**APIエンドポイント**（バックエンド側で新規追加予定）:
- `POST /api/feedback/convert` → `{raw_text: "...", project_id: "..."}` → `{converted_text: "...", structured_items: [...]}`

```swift
// APIClient.swift に追加
struct FeedbackConvertRequest: Encodable {
    let rawText: String
    let projectId: String
}

struct FeedbackConvertResponse: Decodable {
    let convertedText: String
    let structuredItems: [StructuredFeedbackItem]
}

struct StructuredFeedbackItem: Decodable, Identifiable {
    let id: String
    let timestamp: String
    let element: String
    let instruction: String
    let priority: String
}

func convertFeedback(rawText: String, projectId: String) async throws -> FeedbackConvertResponse {
    try await request(
        FeedbackConvertResponse.self,
        path: "/api/feedback/convert",
        method: "POST",
        body: FeedbackConvertRequest(rawText: rawText, projectId: projectId)
    )
}
```

---

## pbxproj への新規ファイル登録

新規作成する `.swift` ファイルは必ず `VideoDirectorAgent.xcodeproj/project.pbxproj` に登録すること:
1. PBXBuildFile セクションに追加
2. PBXFileReference セクションに追加
3. PBXGroup の該当グループ（Views/ or ViewModels/）に追加
4. PBXSourcesBuildPhase に追加

既存ファイルの参照IDパターンを踏襲すること。

---

## 新規作成ファイル一覧

| ファイル | 内容 |
|---------|------|
| `Views/EditorManagementView.swift` | 編集者管理画面 |
| `Views/VideoTrackingView.swift` | 映像トラッキング画面 |
| `Views/NotificationSettingsView.swift` | 通知設定画面 |
| `ViewModels/EditorManagementViewModel.swift` | 編集者管理VM |
| `ViewModels/VideoTrackingViewModel.swift` | 映像トラッキングVM |

## 修正ファイル一覧

| ファイル | 修正内容 |
|---------|---------|
| `Models/Models.swift` | Editor, TrackedVideo, VideoAnalysis, TrackingInsight, AuditReport, DashboardSummary, QualityTrendItem 等のモデル追加 |
| `Services/APIClient.swift` | fetchAllFeedbacks, fetchDashboardSummary, fetchQualityTrend, fetchEditors, fetchTrackingVideos, convertFeedback 等のメソッド追加 |
| `ViewModels/DashboardViewModel.swift` | API実データ取得に置き換え |
| `ViewModels/VoiceFeedbackViewModel.swift` | convertFeedback() をAPI呼び出しに置き換え |
| `Views/FeedbackHistoryView.swift` | モック→API実データ |
| `Views/QualityDashboardView.swift` | モック→API実データ + 編集者/トラッキング/監査セクション追加 |
| `Views/DirectionReportView.swift` | 概要タブにPDCAセクション追加 |

---

## 完了条件

1. FeedbackHistoryView が `GET /api/feedbacks` からデータ取得して表示
2. QualityDashboardView が `GET /api/dashboard/summary` + `quality-trend` から実データ表示
3. 編集者管理画面が表示され、`GET /api/editors` からデータ取得
4. 映像トラッキング画面が表示され、`GET /api/tracking/videos` からデータ取得
5. 通知設定画面が表示される
6. VoiceFeedbackViewModel の convertFeedback() が API 呼び出しに置き換え
7. 全画面で `.refreshable` プルダウンリフレッシュが動作
8. エラー時はモックフォールバック + ユーザーフレンドリーなエラー表示
9. `xcodebuild` でビルドが通ること

## 注意事項
- Swift 6 Concurrency: `@MainActor`, `Sendable` を厳守
- UIFont禁止、Font.custom() のみ使用
- AppThemeの色・フォント定義を使うこと
- 新規ファイルは必ず pbxproj に登録
- APIのベースURL: http://localhost:8210
- APIレスポンスはsnake_caseで、Swift側は`.convertFromSnakeCase`で変換済み
- API未実装の場合はモックデータにフォールバックして動作すること（バックエンドは並列で実装中）
- パグさんは編集者ではなくディレクター
