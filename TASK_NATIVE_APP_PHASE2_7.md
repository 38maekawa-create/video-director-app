# タスク指示書: 映像ディレクションエージェント ネイティブアプリ Phase 2-7

## 目的
映像ディレクションエージェントのiOSアプリを完成させる。なおとさんとパグさん（編集者）が全機能をスマホから使えるようにする。Phase1で構築したAPI接続基盤の上に、残りタブの実データ化・音声フィードバック・ポーリング同期を実装する。

## 背景
- Phase1が完了済み: APIClient.swift, YouTubeAssetsView.swift, Models.swift Codable化, DirectionReportView 7タブ化
- Xcodeビルド成功確認済み（iPhone 17 Pro Simulator, iOS 26.3.1）
- APIサーバー（localhost:8210 / mac-mini-m4.local:8210）が31プロジェクトのデータを保持
- 現状、ProjectListViewModelはAPI接続済みだが初期表示でMockDataにフォールバックしている
- DirectionReportViewの7タブのうち、YouTube素材タブ（index 2）のみ実装済み。他は仮表示

## 全体工程における位置づけ
Phase 1（完了）→ **Phase 2-7（本タスク）** → Phase 3（TestFlight配布・品質向上）

本タスク完了により:
- 全7タブが実データで動作し、スマホから全機能を使える状態になる
- 音声録音→文字起こし→FB投稿のフローが動作する
- なおとさんとパグさんの編集がポーリングで同期される

---

## Codex CLIがやるべき作業（Swift側のみ）

### 1. ProjectListViewModelのAPI接続改善

**対象ファイル**: `ViewModels/ProjectListViewModel.swift`

現状の `loadProjects()` は既にAPIClient接続済みだが、pull-to-refreshに対応していない。

**修正内容**:
- `loadProjects()` を外部から呼べるように pull-to-refresh 対応する
- `hasLoaded` フラグをリセットする `refresh()` メソッドを追加

```swift
func refresh() async {
    hasLoaded = false
    await loadProjects()
}
```

**対応するView側**（`Views/ProjectListView.swift`）:
- ScrollView または List に `.refreshable { await viewModel.refresh() }` を追加

---

### 2. 残りタブの実データ化（DirectionReportView.swift内）

**対象ファイル**: `Views/DirectionReportView.swift`

各タブの実装内容:

#### タブ0: 概要タブ — 実データ表示
現状 `overviewSection` はハードコードされた表示。`displayProject` の実データを使用するよう修正。

```swift
private var overviewSection: some View {
    VStack(spacing: 12) {
        overviewCard(
            title: "プロジェクト概要",
            icon: "doc.text.magnifyingglass",
            items: [
                "ゲスト: \(displayProject.guestName)",
                displayProject.guestAge.map { "年齢: \($0)歳" } ?? "年齢: 未設定",
                displayProject.guestOccupation.map { "職業: \($0)" } ?? "職業: 未設定",
                "撮影日: \(displayProject.shootDate)",
                "状態: \(displayProject.status.label)",
                "品質スコア: \(displayProject.qualityScore.map(String.init) ?? "未算出")"
            ].compactMap { $0 }
        )
        overviewCard(
            title: "進行サマリー",
            icon: "chart.bar.xaxis",
            items: [
                "未レビュー: \(displayProject.unreviewedCount)件",
                "未送信FB: \(displayProject.hasUnsentFeedback ? "あり" : "なし")"
            ]
        )
    }
}
```
※ 概要タブは既に `displayProject` のデータを使っているため、大きな変更は不要。年齢・職業が nil の場合の表示を改善する程度。

#### タブ1: ディレクションタブ — WKWebView埋め込み
`displayProject.directionReportURL` をWKWebViewで表示する。

**新規ファイル作成**: `Views/WebViewRepresentable.swift`

```swift
import SwiftUI
import WebKit

struct WebViewRepresentable: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.scrollView.backgroundColor = .clear
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        let request = URLRequest(url: url)
        webView.load(request)
    }
}
```

DirectionReportView の `sectionContent` 内 `case 1:` を修正:

```swift
case 1:
    if let urlString = displayProject.directionReportURL,
       let url = URL(string: urlString) {
        WebViewRepresentable(url: url)
            .frame(minHeight: 600)
            .clipShape(RoundedRectangle(cornerRadius: 12))
    } else {
        overviewCard(
            title: "ディレクションレポート",
            icon: "doc.richtext",
            items: ["レポートURLが未設定です"]
        )
    }
```

#### タブ2: YouTube素材タブ — 変更なし
既存の `YouTubeAssetsView(projectId: displayProject.id)` がそのまま動作。

#### タブ3: 素材タブ — sourceVideo情報表示
VideoProjectモデルに `sourceVideoURL` (String?) を追加し、素材動画の情報を表示する。

**Models.swift に追加するプロパティ**:
```swift
// VideoProject に追加
let sourceVideoURL: String?    // Vimeo等の素材動画URL
let editedVideoURL: String?    // 編集後動画URL
let knowledge: String?         // ナレッジハイライトテキスト
```

DirectionReportView の `case 3:` を修正:
```swift
case 3:
    sourceVideoSection
```

```swift
private var sourceVideoSection: some View {
    VStack(spacing: 12) {
        overviewCard(
            title: "撮影素材",
            icon: "video.badge.waveform",
            items: [
                "ゲスト: \(displayProject.guestName)",
                "撮影日: \(displayProject.shootDate)"
            ]
        )
        if let url = displayProject.sourceVideoURL, !url.isEmpty {
            Link(destination: URL(string: url)!) {
                HStack {
                    Image(systemName: "play.rectangle.fill")
                    Text("素材動画を開く（Vimeo）")
                }
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color(hex: 0x1AB7EA))  // Vimeoブルー
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        } else {
            overviewCard(
                title: "素材動画",
                icon: "exclamationmark.triangle",
                items: ["素材動画URLが未登録です"]
            )
        }
    }
}
```

#### タブ4: 編集後タブ — editedVideo情報表示
```swift
case 4:
    editedVideoSection
```

```swift
private var editedVideoSection: some View {
    VStack(spacing: 12) {
        if let url = displayProject.editedVideoURL, !url.isEmpty {
            overviewCard(
                title: "編集後動画",
                icon: "sparkles.rectangle.stack",
                items: ["編集完了。レビュー可能な状態です。"]
            )
            Link(destination: URL(string: url)!) {
                HStack {
                    Image(systemName: "play.rectangle.fill")
                    Text("編集後動画を開く")
                }
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(AppTheme.statusComplete)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        } else {
            overviewCard(
                title: "編集後動画",
                icon: "sparkles.rectangle.stack",
                items: [
                    "編集後動画はまだアップロードされていません",
                    "パグさんが編集完了後にここに表示されます"
                ]
            )
        }
    }
}
```

#### タブ5: FB・評価タブ — APIからフィードバック取得
APIClient経由で `GET /api/projects/{id}/feedbacks` を呼び出し、フィードバック一覧を表示する。

DirectionReportView に State を追加:
```swift
@State private var feedbacks: [FeedbackItem] = []
@State private var isFeedbackLoading = false
```

```swift
case 5:
    feedbackListSection
```

```swift
private var feedbackListSection: some View {
    VStack(spacing: 12) {
        if isFeedbackLoading {
            ProgressView()
                .tint(AppTheme.accent)
                .frame(maxWidth: .infinity, minHeight: 100)
        } else if feedbacks.isEmpty {
            overviewCard(
                title: "フィードバック",
                icon: "bubble.left.and.bubble.right",
                items: ["まだフィードバックがありません"]
            )
        } else {
            ForEach(feedbacks) { fb in
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(fb.createdBy)
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundStyle(AppTheme.accent)
                        Spacer()
                        Text(fb.createdAt)
                            .font(.caption2)
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    Text(fb.content)
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.textSecondary)
                    if let timestamp = fb.timestamp {
                        HStack(spacing: 4) {
                            Image(systemName: "clock")
                            Text(timestamp)
                        }
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                    }
                }
                .padding(16)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }
    .task {
        await loadFeedbacks()
    }
}

private func loadFeedbacks() async {
    isFeedbackLoading = true
    defer { isFeedbackLoading = false }
    do {
        feedbacks = try await APIClient.shared.fetchFeedbacks(projectId: displayProject.id)
    } catch {
        feedbacks = []
    }
}
```

#### タブ6: ナレッジタブ — ナレッジハイライト表示
```swift
case 6:
    knowledgeDetailSection
```

```swift
private var knowledgeDetailSection: some View {
    VStack(spacing: 12) {
        if let knowledge = displayProject.knowledge, !knowledge.isEmpty {
            overviewCard(
                title: "ナレッジハイライト",
                icon: "lightbulb.fill",
                items: knowledge.components(separatedBy: "\n").filter { !$0.isEmpty }
            )
        } else {
            overviewCard(
                title: "ナレッジ連携",
                icon: "books.vertical",
                items: [
                    "この案件のナレッジはまだ生成されていません",
                    "動画分析完了後に自動生成されます"
                ]
            )
        }
    }
}
```

---

### 3. Models.swift 拡張

**対象ファイル**: `Models/Models.swift`

#### VideoProject にプロパティ追加
```swift
let sourceVideoURL: String?
let editedVideoURL: String?
let knowledge: String?
```

- `init()` にデフォルト値 `nil` で追加
- `CodingKeys` に追加
- `init(from decoder:)` に `decodeIfPresent` で追加

#### FeedbackItem モデル追加
```swift
struct FeedbackItem: Identifiable, Codable {
    let id: String
    let projectId: String
    let content: String
    let createdBy: String
    let createdAt: String
    let timestamp: String?       // 動画内タイムスタンプ（任意）
    let feedbackType: String?    // "voice" / "text"
}
```

#### FeedbackCreateRequest モデル追加
```swift
struct FeedbackCreateRequest: Encodable {
    let content: String
    let createdBy: String
    let timestamp: String?
    let feedbackType: String
}
```

---

### 4. APIClient.swift 拡張

**対象ファイル**: `Services/APIClient.swift`

以下のメソッドを追加:

```swift
// フィードバック一覧取得
func fetchFeedbacks(projectId: String) async throws -> [FeedbackItem] {
    try await request([FeedbackItem].self, path: "/api/projects/\(projectId)/feedbacks")
}

// フィードバック投稿
func createFeedback(projectId: String, content: String, createdBy: String, timestamp: String?, feedbackType: String) async throws {
    let body = FeedbackCreateRequest(
        content: content,
        createdBy: createdBy,
        timestamp: timestamp,
        feedbackType: feedbackType
    )
    _ = try await request(
        EmptyResponse.self,
        path: "/api/projects/\(projectId)/feedbacks",
        method: "POST",
        body: body
    )
}
```

**注意**: `EmptyResponse` と `FeedbackCreateRequest` の可視性を調整すること。`EmptyResponse` は現在 `private` なので、`createFeedback` から使えるようにファイル内スコープに変更するか、別の空レスポンス型を用意する。

#### baseURL の環境切り替え対応
現状のフォールバック方式（mac-mini-m4.local → localhost）は維持しつつ、将来の設定変更に備えてコメントを追加する程度でOK。既にフォールバック実装済みのため大きな変更は不要。

---

### 5. 音声フィードバック機能の実装

**対象ファイル**:
- `ViewModels/VoiceFeedbackViewModel.swift`
- `Views/VoiceFeedbackView.swift`

現状はモック実装（タイマーで録音時間を表示、ハードコードされた文字起こしテキスト）。これを実機能に置き換える。

#### VoiceFeedbackViewModel.swift の修正

**AVFoundation 録音の実装**:
```swift
import AVFoundation
import Speech

@MainActor
final class VoiceFeedbackViewModel: ObservableObject {
    // 既存プロパティに追加
    @Published var projectId: String = ""    // 対象プロジェクトID

    private var audioRecorder: AVAudioRecorder?
    private var audioFileURL: URL?

    // toggleRecording() を実装に置き換え
    func toggleRecording() {
        sentMessage = nil

        if flowState == .recording {
            stopRecordingAndTranscribe()
            return
        }

        startRecording()
    }

    private func startRecording() {
        // AVAudioSession設定
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playAndRecord, mode: .default)
            try session.setActive(true)
        } catch {
            print("AudioSession設定エラー: \(error)")
            return
        }

        // 録音ファイルパス
        let fileName = "feedback_\(Date().timeIntervalSince1970).m4a"
        audioFileURL = FileManager.default.temporaryDirectory.appendingPathComponent(fileName)

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 44100,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]

        do {
            audioRecorder = try AVAudioRecorder(url: audioFileURL!, settings: settings)
            audioRecorder?.record()
            flowState = .recording
            rawTranscript = ""
            convertedText = ""
            structuredItems = []
            recordingDuration = 0

            // 録音タイマー
            recordingTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    self?.recordingDuration += 0.1
                }
            }
        } catch {
            print("録音開始エラー: \(error)")
        }
    }

    private func stopRecordingAndTranscribe() {
        recordingTimer?.invalidate()
        recordingTimer = nil
        audioRecorder?.stop()
        flowState = .transcribing

        // Speech Framework で文字起こし
        guard let audioFileURL = audioFileURL else {
            flowState = .idle
            return
        }

        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            Task { @MainActor in
                guard status == .authorized else {
                    // 権限がない場合はモックにフォールバック
                    self?.rawTranscript = "（音声認識の権限がありません。設定から許可してください）"
                    self?.flowState = .readyToConvert
                    return
                }

                let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "ja-JP"))
                let request = SFSpeechURLRecognitionRequest(url: audioFileURL)
                request.shouldReportPartialResults = false

                recognizer?.recognitionTask(with: request) { result, error in
                    Task { @MainActor in
                        if let result = result, result.isFinal {
                            self?.rawTranscript = result.bestTranscription.formattedString
                            self?.flowState = .readyToConvert
                        } else if let error = error {
                            self?.rawTranscript = "（文字起こしエラー: \(error.localizedDescription)）"
                            self?.flowState = .readyToConvert
                        }
                    }
                }
            }
        }
    }

    // sendFeedback() をAPI投稿に置き換え
    func sendFeedback() {
        guard canSend else { return }

        Task {
            do {
                let timestamp = String(format: "%02d:%02d", Int(selectedTime) / 60, Int(selectedTime) % 60)
                try await APIClient.shared.createFeedback(
                    projectId: projectId,
                    content: convertedText.isEmpty ? rawTranscript : convertedText,
                    createdBy: "naoto",   // ユーザー識別（将来設定画面で変更可能に）
                    timestamp: timestamp,
                    feedbackType: "voice"
                )
                flowState = .sent
                sentMessage = "フィードバックを保存しました"
            } catch {
                sentMessage = "送信エラー: \(error.localizedDescription)"
            }
        }
    }
}
```

#### VoiceFeedbackView.swift の修正
- `VoiceFeedbackViewModel` 初期化時に `projectId` を渡せるようにする
- DirectionReportView の「音声フィードバックを追加」ボタンから `projectId` を注入する

---

### 6. ポーリング同期（YouTubeAssetsView）

**対象ファイル**: `Views/YouTubeAssetsView.swift`

30秒ごとにAPIをポーリングして最新データを取得し、他ユーザーの編集を検知する。

```swift
// YouTubeAssetsView に追加
@State private var showUpdateBanner = false
@State private var lastKnownEditedBy: String?
@State private var pollingTimer: Timer?

// onAppear でポーリング開始
.onAppear {
    startPolling()
}
.onDisappear {
    stopPolling()
}

private func startPolling() {
    pollingTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in
        Task { @MainActor in
            await pollForUpdates()
        }
    }
}

private func stopPolling() {
    pollingTimer?.invalidate()
    pollingTimer = nil
}

private func pollForUpdates() async {
    do {
        let latest = try await APIClient.shared.fetchYouTubeAssets(projectId: projectId)
        if let editedBy = latest.lastEditedBy,
           editedBy != "naoto",   // 自分以外の編集
           editedBy != lastKnownEditedBy {
            lastKnownEditedBy = editedBy
            showUpdateBanner = true
            // 3秒後にバナーを消す
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                showUpdateBanner = false
            }
        }
        // データを最新に更新（既存のロード処理を再利用）
    } catch {
        // ポーリングエラーは無視（ネットワーク一時断等）
    }
}
```

バナー表示:
```swift
// body の先頭にオーバーレイ
if showUpdateBanner {
    HStack {
        Image(systemName: "arrow.triangle.2.circlepath")
        Text("パグさんが更新しました")
    }
    .font(.caption)
    .fontWeight(.bold)
    .foregroundStyle(.white)
    .padding(.horizontal, 16)
    .padding(.vertical, 8)
    .background(Color(hex: 0x4A90D9))
    .clipShape(Capsule())
    .transition(.move(edge: .top).combined(with: .opacity))
    .animation(.easeInOut, value: showUpdateBanner)
}
```

---

### 7. Info.plist 設定

**対象ファイル**: `VideoDirectorAgent/Info.plist`

以下のキーを追加:

```xml
<key>NSLocalNetworkUsageDescription</key>
<string>ローカルネットワーク上のAPIサーバーに接続するために必要です</string>
<key>NSMicrophoneUsageDescription</key>
<string>音声フィードバックの録音に使用します</string>
<key>NSSpeechRecognitionUsageDescription</key>
<string>録音した音声をテキストに変換するために使用します</string>
```

**注意**: `NSAppTransportSecurity` の `NSAllowsLocalNetworking` は既に設定済み。追加不要。

---

## 新規作成ファイル一覧

| ファイル | 内容 |
|---------|------|
| `Views/WebViewRepresentable.swift` | WKWebView の UIViewRepresentable ラッパー |

## 修正ファイル一覧

| ファイル | 修正内容 |
|---------|---------|
| `Models/Models.swift` | VideoProject に3プロパティ追加、FeedbackItem/FeedbackCreateRequest 追加 |
| `Models/MockData.swift` | VideoProject のモックデータに新プロパティのデフォルト値追加 |
| `Services/APIClient.swift` | fetchFeedbacks, createFeedback メソッド追加 |
| `ViewModels/ProjectListViewModel.swift` | refresh() メソッド追加 |
| `ViewModels/VoiceFeedbackViewModel.swift` | AVFoundation録音 + Speech文字起こし + API投稿に置き換え |
| `Views/DirectionReportView.swift` | 全7タブの実データ化、feedbacks State追加 |
| `Views/ProjectListView.swift` | .refreshable 追加 |
| `Views/YouTubeAssetsView.swift` | 30秒ポーリング + 更新バナー追加 |
| `Views/VoiceFeedbackView.swift` | projectId の受け渡し対応 |
| `Info.plist` | マイク・音声認識・ローカルネットワークの使用目的追加 |

---

## 完了条件と検証

### ビルド検証
1. `xcodebuild -project VideoDirectorAgent.xcodeproj -scheme VideoDirectorAgent -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=26.3.1' build` でビルドが通ること

### 機能検証
2. プロジェクト一覧画面で pull-to-refresh が動作し、APIからデータを再取得すること
3. 概要タブ（index 0）にプロジェクトの実データ（ゲスト名・年齢・職業・撮影日・ステータス・品質スコア）が表示されること
4. ディレクションタブ（index 1）で directionReportURL がある場合にWKWebViewでレポートが表示されること
5. YouTube素材タブ（index 2）は既存動作が維持されること
6. 素材タブ（index 3）に素材動画情報が表示され、URLがある場合はVimeoリンクが開けること
7. 編集後タブ（index 4）に編集後動画情報が表示されること
8. FB・評価タブ（index 5）で `GET /api/projects/{id}/feedbacks` からデータを取得して一覧表示されること
9. ナレッジタブ（index 6）にナレッジハイライトが表示されること
10. 音声録音→文字起こし→「この指示を送信」でAPIにフィードバックがPOSTされること
11. YouTubeAssetsViewで30秒ポーリングが動作し、他ユーザーの編集時にバナーが表示されること

---

## 注意事項

### Swift 6 Concurrency対応
- `@MainActor` を ViewModel・APIClient に付与すること（既に付与済みのものは維持）
- `Sendable` 準拠が必要な型には適切に対応すること
- `Timer` のクロージャから `@MainActor` コンテキストへの遷移は `Task { @MainActor in }` を使用

### UIKit API の使用制限
- `UIFont` は使わない（SwiftUIの `Font` APIのみ）
- `UIViewRepresentable` は WKWebView のラップにのみ使用可

### デザイン統一
- 既存の Netflix風ダークUI（AppTheme）のカラーパレット・フォントスタイルを厳守
- 新規UIもすべて `AppTheme.background`, `AppTheme.cardBackground`, `AppTheme.accent` 等を使用

### テスト環境
- シミュレーター: iPhone 17 Pro（iOS 26.3.1）
- APIサーバー: `http://localhost:8210`（シミュレータからはlocalhost接続）
- プロジェクトパス: `~/AI開発10/VideoDirectorAgent/`

### バックエンドAPI（既に存在/別途対応）
以下のエンドポイントはバックエンド側で提供済みまたは別途対応。Swift側は呼び出すだけでOK:
- `GET /api/projects` — プロジェクト一覧（実装済み）
- `GET /api/projects/{id}` — プロジェクト詳細（実装済み）
- `GET /api/projects/{id}/youtube-assets` — YouTube素材（実装済み）
- `PATCH .../description`, `PATCH .../title` — 編集（実装済み）
- `GET /api/projects/{id}/feedbacks` — フィードバック一覧（実装済み）
- `POST /api/projects/{project_id}/feedbacks` — フィードバック投稿（別途対応）

### 既存ファイルパス
```
~/AI開発10/VideoDirectorAgent/VideoDirectorAgent/
├── Models/
│   ├── Models.swift              ← プロパティ追加 + FeedbackItem追加
│   └── MockData.swift            ← モックデータ更新
├── Views/
│   ├── DirectionReportView.swift ← 全7タブ実データ化
│   ├── YouTubeAssetsView.swift   ← ポーリング追加
│   ├── VoiceFeedbackView.swift   ← projectId対応
│   ├── ProjectListView.swift     ← refreshable追加
│   ├── WebViewRepresentable.swift← 新規作成
│   ├── RootTabView.swift         ← 変更なし
│   ├── QualityDashboardView.swift← 変更なし
│   └── FeedbackHistoryView.swift ← 変更なし
├── ViewModels/
│   ├── ProjectListViewModel.swift ← refresh追加
│   ├── VoiceFeedbackViewModel.swift ← 実録音+STT+API投稿
│   └── DashboardViewModel.swift   ← 変更なし
├── Services/
│   └── APIClient.swift           ← fetchFeedbacks, createFeedback追加
├── Info.plist                    ← マイク・音声認識許可追加
└── VideoDirectorAgentApp.swift   ← 変更なし
```
