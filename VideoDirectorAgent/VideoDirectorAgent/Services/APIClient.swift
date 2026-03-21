import Foundation
import Network

// MARK: - ConnectionOrchestrator（probe競合防止 actor）

/// 接続先の自動検出・切り替えを排他制御するactor
/// 多重probe抑止: 既存のprobeTaskをcancelしてから新しいprobeを開始
actor ConnectionOrchestrator {
    enum Route: Equatable {
        case local(URL)
        case tailscale(URL)
        case cloud(URL)

        var url: URL {
            switch self {
            case .local(let u), .tailscale(let u), .cloud(let u): return u
            }
        }

        var label: String {
            switch self {
            case .local: return "🏠 ローカル"
            case .tailscale: return "🔗 Tailscale"
            case .cloud: return "☁️ クラウド"
            }
        }

        var priority: Int {
            switch self {
            case .local: return 0
            case .tailscale: return 1
            case .cloud: return 2
            }
        }
    }

    enum State: Equatable {
        case idle
        case probing
        case connected(Route)
        case disconnected
    }

    private(set) var state: State = .idle
    private var probeTask: Task<Route?, Never>?

    private let routes: [Route]
    private let primaryURL: URL

    init(routes: [Route], primaryURL: URL) {
        self.routes = routes
        self.primaryURL = primaryURL
    }

    /// probe実行（多重抑止付き）
    /// 既存のprobeが走っていればcancelしてから新しいprobeを開始
    func reprobe(trigger: String = "unknown") async -> Route? {
        // 既存probeをキャンセル
        probeTask?.cancel()
        state = .probing

        probeTask = Task {
            await raceRoutes()
        }
        let result = await probeTask?.value
        if let route = result {
            state = .connected(route)
        } else {
            state = .disconnected
        }
        return result
    }

    /// 優先度付き並列probe
    /// Phase 1: local + tailscale を並列（短タイムアウト3秒）
    /// Phase 2: 失敗時のみ cloud を試行（モバイル通信考慮で10秒）
    private func raceRoutes() async -> Route? {
        // Phase 1: ローカル・Tailscaleを並列probe
        let fastRoutes = routes.filter { $0.priority < 2 }
        let cloudRoute = routes.first { $0.priority == 2 }

        if !fastRoutes.isEmpty {
            let winner = await withTaskGroup(of: Route?.self, returning: Route?.self) { group in
                for route in fastRoutes {
                    group.addTask {
                        if await self.probe(route: route, timeout: 3) {
                            return route
                        }
                        return nil
                    }
                }
                // 優先度順で最初に成功したものを返す
                var results: [Route] = []
                for await result in group {
                    if let r = result { results.append(r) }
                }
                return results.sorted { $0.priority < $1.priority }.first
            }
            if let w = winner { return w }
        }

        // Phase 2: クラウドを試行（モバイル通信＋Cloudflareトンネル＋TLSハンドシェイクを考慮し15秒）
        if let cloud = cloudRoute {
            if await probe(route: cloud, timeout: 15) {
                return cloud
            }
        }

        return nil
    }

    /// 単一ルートのヘルスチェック（/healthz を使用）
    private func probe(route: Route, timeout: TimeInterval) async -> Bool {
        let testURL = route.url.appendingPathComponent("/healthz")
        var request = URLRequest(url: testURL)
        request.httpMethod = "GET"
        request.timeoutInterval = timeout
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            if let http = response as? HTTPURLResponse {
                return (200...299).contains(http.statusCode)
            }
            return false
        } catch {
            return false
        }
    }

    /// 現在の接続先URLを取得（disconnected時はprimaryURL）
    func activeURL() -> URL {
        switch state {
        case .connected(let route): return route.url
        default: return primaryURL
        }
    }
}

// MARK: - APIClient

@MainActor
final class APIClient: ObservableObject {
    static let shared = APIClient()

    /// Info.plistで指定されたプライマリURL（クラウド経由）
    let primaryURL: URL
    /// 現在アクティブなベースURL（自動切り替え対象）
    @Published private(set) var activeBaseURL: URL
    /// 後方互換: 既存コードが baseURL を参照している箇所向け
    var baseURL: URL { activeBaseURL }
    let actorName: String

    /// ネットワーク状態監視（WiFi↔4G切り替え・復帰を自動検知）
    private let networkMonitor = NWPathMonitor()
    private let monitorQueue = DispatchQueue(label: "com.maekawa.networkMonitor")
    private var lastPathStatus: NWPath.Status = .satisfied

    /// 接続状態
    @Published private(set) var connectionStatus: ConnectionStatus = .connecting
    /// 初回接続完了フラグ（初回probe完了前はdisconnectedバナーを抑制）
    @Published private(set) var hasEverConnected: Bool = false

    enum ConnectionStatus: Equatable {
        case connecting
        case connected(String)  // 接続先のラベル
        case disconnected
    }

    /// probe競合防止actor
    let orchestrator: ConnectionOrchestrator

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    private init() {
        guard
            let value = Bundle.main.object(forInfoDictionaryKey: "APIBaseURL") as? String,
            let url = URL(string: value)
        else {
            fatalError("Info.plist に APIBaseURL が設定されていません")
        }
        guard
            let actor = Bundle.main.object(forInfoDictionaryKey: "APIActorName") as? String,
            !actor.isEmpty
        else {
            fatalError("Info.plist に APIActorName が設定されていません")
        }

        primaryURL = url
        actorName = actor

        // フォールバック候補をRoute型で構築
        var routes: [ConnectionOrchestrator.Route] = []
        if let local = URL(string: "http://mac-mini-m4.local:8210") {
            routes.append(.local(local))
        }
        if let tailscale = URL(string: "http://100.110.206.6:8210") {
            routes.append(.tailscale(tailscale))
        }
        routes.append(.cloud(url))

        orchestrator = ConnectionOrchestrator(routes: routes, primaryURL: url)

        // 初期値はプライマリURL（すぐにprobeで上書きされる）
        activeBaseURL = url

        // ネットワーク状態監視を開始
        startNetworkMonitor()
    }

    /// ネットワーク変化時のデバウンス用タスク
    private var networkDebounceTask: Task<Void, Never>?
    /// disconnected遷移のデバウンス用タスク
    private var disconnectDebounceTask: Task<Void, Never>?
    /// 最後にNWPathMonitorが通知したインターフェースタイプ（重複通知フィルタ用）
    private var lastInterfaceTypes: Set<NWInterface.InterfaceType> = []

    /// ネットワーク状態変化を監視し、復帰時に自動再接続
    /// デバウンス: 短時間の連続変化を無視し、安定してから再接続
    /// モバイル通信(4G/5G)の電波変動・基地局ハンドオーバーによる頻繁な通知を抑制
    private func startNetworkMonitor() {
        networkMonitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor [weak self] in
                guard let self = self else { return }
                let wasDisconnected = self.lastPathStatus != .satisfied
                let isNowConnected = path.status == .satisfied
                self.lastPathStatus = path.status

                // インターフェースタイプの変化を検出（WiFi→4G等の実質的な変化のみ反応）
                let currentInterfaces = Set(path.availableInterfaces.map { $0.type })
                let interfaceActuallyChanged = currentInterfaces != self.lastInterfaceTypes
                self.lastInterfaceTypes = currentInterfaces

                if isNowConnected && (wasDisconnected || interfaceActuallyChanged) {
                    // 復帰時はdisconnectデバウンスをキャンセル（回復したのでバナー不要）
                    self.disconnectDebounceTask?.cancel()
                    self.disconnectDebounceTask = nil

                    // 同一インターフェース内の再通知は無視（モバイル基地局ハンドオーバー等）
                    if !wasDisconnected && !interfaceActuallyChanged {
                        return
                    }

                    // デバウンス: 5秒間安定してから再接続（モバイル通信の電波変動でのチラつき防止）
                    self.networkDebounceTask?.cancel()
                    self.networkDebounceTask = Task {
                        try? await Task.sleep(nanoseconds: 5_000_000_000)
                        guard !Task.isCancelled else { return }
                        print("📡 ネットワーク変化検知（安定後）→ サイレント再接続開始")
                        await self.silentReprobe()
                    }
                } else if !isNowConnected {
                    // 切断デバウンス: 15秒間切断が続いた場合のみdisconnected表示
                    // モバイル通信のWiFi↔4G切り替え・電波変動での瞬断でバナーが出るのを防止
                    self.disconnectDebounceTask?.cancel()
                    self.disconnectDebounceTask = Task {
                        try? await Task.sleep(nanoseconds: 15_000_000_000)
                        guard !Task.isCancelled else { return }
                        self.connectionStatus = .disconnected
                        print("📡 ネットワーク切断検知（15秒持続）")
                    }
                }
            }
        }
        networkMonitor.start(queue: monitorQueue)
    }

    /// probe失敗の連続回数（連続して失敗した場合のみdisconnectedに遷移）
    private var consecutiveProbeFailures = 0
    /// サイレント再probeの重複防止フラグ
    private var isSilentReprobing = false
    /// 最後にdisconnected状態に遷移した時刻（短時間での再遷移を防止）
    private var lastDisconnectedAt: Date?

    /// アプリ起動時・ScenePhase復帰時に呼び出し（UIバナーに影響する公開メソッド）
    /// ConnectionOrchestrator actorにより多重probe抑止
    /// 既に接続済みの場合はバナーを出さずにバックグラウンドでprobeする
    func probeAndConnect() async {
        let wasConnected: Bool
        if case .connected = connectionStatus {
            wasConnected = true
        } else {
            wasConnected = false
        }

        // 既に接続済みの場合はconnectingバナーを出さない（チラつき防止）
        if !wasConnected && !hasEverConnected {
            connectionStatus = .connecting
        }
        print("🔍 probeAndConnect開始（orchestrator経由、wasConnected=\(wasConnected)）")

        if let route = await orchestrator.reprobe(trigger: "probeAndConnect") {
            activeBaseURL = route.url
            connectionStatus = .connected(route.label)
            hasEverConnected = true
            consecutiveProbeFailures = 0
            print("✅ 接続成功: \(route.url.absoluteString) (\(route.label))")
        } else {
            consecutiveProbeFailures += 1
            // connected状態の場合、3回連続probe失敗まではconnected状態を維持
            // モバイル通信の一時的な遅延・パケロスでバナーが出るのを防止
            if wasConnected && consecutiveProbeFailures < 3 {
                print("⚠️ probe失敗（\(consecutiveProbeFailures)/3回目）。connected状態を維持してリトライ")
                // 5秒後に再度probeを試行（バックグラウンドで静かに）
                Task {
                    try? await Task.sleep(nanoseconds: 5_000_000_000)
                    guard !Task.isCancelled else { return }
                    await self.silentReprobe()
                }
            } else if !hasEverConnected {
                // 初回接続前の場合のみdisconnected遷移
                activeBaseURL = primaryURL
                connectionStatus = .disconnected
                print("⚠️ 初回接続失敗（\(consecutiveProbeFailures)回）。プライマリURL(\(primaryURL))で待機")
            } else {
                // 3回連続失敗の場合のみdisconnected遷移（ただし30秒以内の再遷移は防止）
                if let lastDisc = lastDisconnectedAt, Date().timeIntervalSince(lastDisc) < 30 {
                    print("⚠️ probe失敗だが30秒以内の再disconnectedは抑制。リトライ予約")
                    Task {
                        try? await Task.sleep(nanoseconds: 10_000_000_000)
                        guard !Task.isCancelled else { return }
                        await self.silentReprobe()
                    }
                } else {
                    activeBaseURL = primaryURL
                    connectionStatus = .disconnected
                    lastDisconnectedAt = Date()
                    print("⚠️ 全URL到達不可（\(consecutiveProbeFailures)回連続）。プライマリURL(\(primaryURL))で待機")
                }
            }
        }
    }

    /// サイレント再probe（バナー状態を変更せずにバックグラウンドで接続先を更新）
    /// NWPathMonitor変化時・APIエラー時に使用。UIのチラつきを完全に防止する
    private func silentReprobe() async {
        guard !isSilentReprobing else { return }
        isSilentReprobing = true
        defer { isSilentReprobing = false }

        print("🔍 サイレント再probe開始")
        if let route = await orchestrator.reprobe(trigger: "silentReprobe") {
            activeBaseURL = route.url
            // バナーが出ている場合のみ状態を更新（connected復帰）
            if case .disconnected = connectionStatus {
                connectionStatus = .connected(route.label)
            } else if case .connecting = connectionStatus {
                connectionStatus = .connected(route.label)
            }
            hasEverConnected = true
            consecutiveProbeFailures = 0
            print("✅ サイレント再probe成功: \(route.url.absoluteString) (\(route.label))")
        } else {
            consecutiveProbeFailures += 1
            print("⚠️ サイレント再probe失敗（\(consecutiveProbeFailures)回目）")
            // サイレントreprobeでは3回連続失敗かつhasEverConnectedの場合のみdisconnected
            if consecutiveProbeFailures >= 3 {
                if let lastDisc = lastDisconnectedAt, Date().timeIntervalSince(lastDisc) < 30 {
                    // 30秒以内は再遷移しない
                } else {
                    connectionStatus = .disconnected
                    lastDisconnectedAt = Date()
                }
            }
        }
    }

    /// ネットワークエラー時に自動再接続を試行（サイレント — バナー状態に影響しない）
    /// APIリクエストの個別エラーではバナーを出さず、バックグラウンドで静かに再probeする
    private func reconnectIfNeeded(error: Error) async {
        guard let urlError = error as? URLError else { return }
        let reconnectCodes: [URLError.Code] = [
            .timedOut, .cannotFindHost, .cannotConnectToHost,
            .networkConnectionLost, .notConnectedToInternet,
            .dnsLookupFailed, .secureConnectionFailed
        ]
        guard reconnectCodes.contains(urlError.code) else { return }
        print("🔄 ネットワークエラー検知。サイレント再probeを試行...")
        await silentReprobe()
    }

    // MARK: - パブリックAPIメソッド

    func fetchProjects() async throws -> [VideoProject] {
        try await request([VideoProject].self, path: "/api/projects")
    }

    func fetchYouTubeAssets(projectId: String) async throws -> YouTubeAssets {
        try await request(YouTubeAssets.self, path: "/api/projects/\(projectId)/youtube-assets")
    }

    func updateDescription(projectId: String, edited: String, by: String) async throws {
        let body = DescriptionPayload(edited: edited, by: by)
        _ = try await request(
            EmptyResponse.self,
            path: "/api/projects/\(projectId)/youtube-assets/description",
            method: "PATCH",
            body: body
        )
    }

    func selectTitle(projectId: String, index: Int, editedTitle: String?, by: String) async throws {
        let body = TitleSelectionPayload(index: index, editedTitle: editedTitle, by: by)
        _ = try await request(
            EmptyResponse.self,
            path: "/api/projects/\(projectId)/youtube-assets/title",
            method: "PATCH",
            body: body
        )
    }

    func fetchFeedbacks(projectId: String) async throws -> [FeedbackItem] {
        try await request([FeedbackItem].self, path: "/api/projects/\(projectId)/feedbacks")
    }

    func fetchAllFeedbacks(limit: Int = 50) async throws -> [FeedbackItem] {
        try await request([FeedbackItem].self, path: "/api/feedbacks?limit=\(limit)")
    }

    func fetchDashboardSummary() async throws -> DashboardSummary {
        try await request(DashboardSummary.self, path: "/api/dashboard/summary")
    }

    func fetchQualityTrend() async throws -> [QualityTrendItem] {
        try await request([QualityTrendItem].self, path: "/api/dashboard/quality-trend")
    }

    func fetchEditors() async throws -> [Editor] {
        try await request([Editor].self, path: "/api/editors")
    }

    func fetchTrackingVideos() async throws -> [TrackedVideo] {
        try await request([TrackedVideo].self, path: "/api/tracking/videos")
    }

    func fetchTrackingInsights() async throws -> [TrackingInsight] {
        try await request([TrackingInsight].self, path: "/api/tracking/insights")
    }

    func fetchFrameEvaluation(projectId: String) async throws -> FrameEvaluationResponse {
        try await request(FrameEvaluationResponse.self, path: "/api/v1/projects/\(projectId)/frame-evaluation")
    }

    func runFrameEvaluation(projectId: String) async throws -> FrameEvaluationResponse {
        try await request(FrameEvaluationResponse.self, path: "/api/v1/projects/\(projectId)/frame-evaluation", method: "POST")
    }

    func fetchLearningSummary() async throws -> LearningSummary {
        try await request(LearningSummary.self, path: "/api/learning/summary")
    }

    func fetchLatestAudit() async throws -> AuditReport {
        try await request(AuditReport.self, path: "/api/audit/latest")
    }

    func fetchAuditHistory() async throws -> [AuditReport] {
        try await request([AuditReport].self, path: "/api/audit/history")
    }

    func fetchQualityStats() async throws -> QualityStats {
        try await request(QualityStats.self, path: "/api/v1/dashboard/quality")
    }

    func fetchEditFeedback(
        projectId: String,
        body: EditFeedbackRequestBody = EditFeedbackRequestBody()
    ) async throws -> EditFeedbackResponse {
        return try await request(
            EditFeedbackResponse.self,
            path: "/api/v1/projects/\(projectId)/edit-feedback",
            method: "POST",
            body: body
        )
    }

    // MARK: - E2Eパイプライン

    func runE2EPipeline(
        projectId: String,
        body: E2EPipelineRequestBody = E2EPipelineRequestBody()
    ) async throws -> E2EPipelineResponse {
        return try await performLongRequest(
            E2EPipelineResponse.self,
            path: "/api/v1/projects/\(projectId)/e2e-pipeline",
            method: "POST",
            body: body,
            timeout: 120
        )
    }

    // MARK: - テロップチェック

    func fetchTelopCheck(projectId: String) async throws -> TelopCheckResponse {
        try await request(TelopCheckResponse.self, path: "/api/v1/projects/\(projectId)/telop-check")
    }

    func runTelopCheck(
        projectId: String,
        body: TelopCheckRequestBody = TelopCheckRequestBody()
    ) async throws -> TelopCheckResponse {
        return try await request(
            TelopCheckResponse.self,
            path: "/api/v1/projects/\(projectId)/telop-check",
            method: "POST",
            body: body
        )
    }

    // MARK: - 音声品質評価

    func fetchAudioEvaluation(projectId: String) async throws -> AudioEvaluationResponse {
        try await request(AudioEvaluationResponse.self, path: "/api/v1/projects/\(projectId)/audio-evaluation")
    }

    func runAudioEvaluation(projectId: String) async throws -> AudioEvaluationResponse {
        try await request(
            AudioEvaluationResponse.self,
            path: "/api/v1/projects/\(projectId)/audio-evaluation",
            method: "POST"
        )
    }

    // MARK: - ナレッジページ

    func fetchKnowledgePages(limit: Int = 50, offset: Int = 0) async throws -> KnowledgePagesResponse {
        try await request(
            KnowledgePagesResponse.self,
            path: "/api/v1/knowledge/pages?limit=\(limit)&offset=\(offset)"
        )
    }

    func fetchKnowledgePageDetail(pageId: String) async throws -> KnowledgePageDetail {
        try await request(
            KnowledgePageDetail.self,
            path: "/api/v1/knowledge/pages/\(pageId)?format=html"
        )
    }

    func searchKnowledge(query: String, limit: Int = 20) async throws -> KnowledgeSearchResponse {
        let encodedQuery = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        return try await request(
            KnowledgeSearchResponse.self,
            path: "/api/v1/knowledge/search?q=\(encodedQuery)&limit=\(limit)"
        )
    }

    // MARK: - 素材動画（Source Videos）

    func fetchSourceVideos(projectId: String) async throws -> SourceVideosResponse {
        try await request(
            SourceVideosResponse.self,
            path: "/api/v1/projects/\(projectId)/source-videos"
        )
    }

    func addSourceVideo(projectId: String, youtubeURL: String, title: String?, qualityStatus: String = "pending") async throws -> SourceVideoItem {
        let body = SourceVideoCreateBody(youtubeUrl: youtubeURL, title: title, qualityStatus: qualityStatus)
        return try await request(
            SourceVideoItem.self,
            path: "/api/v1/projects/\(projectId)/source-videos",
            method: "POST",
            body: body
        )
    }

    // MARK: - ビフォーアフター比較

    func fetchBeforeAfter(projectId: String) async throws -> BeforeAfterResponse {
        try await request(BeforeAfterResponse.self, path: "/api/v1/projects/\(projectId)/before-after")
    }

    func fetchTranscriptDiff(projectId: String, version: String? = nil) async throws -> TranscriptDiffResponse {
        var path = "/api/v1/projects/\(projectId)/transcript-diff"
        if let ver = version, !ver.isEmpty {
            let encoded = ver.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ver
            path += "?version=\(encoded)"
        }
        return try await request(TranscriptDiffResponse.self, path: path)
    }

    // MARK: - カテゴリ

    func fetchProjectsByCategory(_ category: String) async throws -> [VideoProject] {
        try await request([VideoProject].self, path: "/api/v1/projects/by-category/\(category)")
    }

    func updateProjectCategory(projectId: String, category: String?) async throws {
        let body = CategoryUpdateBody(category: category)
        _ = try await request(
            EmptyResponse.self,
            path: "/api/v1/projects/\(projectId)/category",
            method: "PUT",
            body: body
        )
    }

    func convertFeedback(rawText: String, projectId: String) async throws -> FeedbackConvertResponse {
        let body = FeedbackConvertRequest(rawText: rawText, projectId: projectId)
        return try await request(FeedbackConvertResponse.self, path: "/api/feedback/convert", method: "POST", body: body)
    }

    // MARK: - Vimeoレビューコメント投稿

    func postVimeoReviewComments(
        vimeoVideoId: String,
        comments: [VimeoCommentPayload],
        dryRun: Bool = true
    ) async throws -> VimeoPostReviewResponse {
        let body = VimeoPostReviewRequest(
            vimeoVideoId: vimeoVideoId,
            comments: comments
        )
        let dryRunParam = dryRun ? "true" : "false"
        return try await request(
            VimeoPostReviewResponse.self,
            path: "/api/v1/vimeo/post-review?dry_run=\(dryRunParam)",
            method: "POST",
            body: body
        )
    }

    func createFeedback(
        projectId: String,
        content: String,
        createdBy: String,
        timestamp: String?,
        feedbackType: String,
        feedbackTarget: String = "direction"
    ) async throws {
        let body = FeedbackCreateRequest(
            content: content,
            createdBy: createdBy,
            timestamp: timestamp,
            feedbackType: feedbackType,
            feedbackTarget: feedbackTarget
        )
        _ = try await request(
            EmptyResponse.self,
            path: "/api/projects/\(projectId)/feedbacks",
            method: "POST",
            body: body
        )
    }

    func convertAssetFeedback(rawText: String, projectId: String, assetType: String) async throws -> AssetFeedbackConvertResponse {
        let body = AssetFeedbackConvertRequest(rawText: rawText, projectId: projectId, assetType: assetType)
        return try await request(AssetFeedbackConvertResponse.self, path: "/api/v1/asset-feedback/convert", method: "POST", body: body)
    }

    func updateConvertedText(feedbackId: String, newText: String) async throws {
        struct UpdateBody: Encodable {
            let converted_text: String
        }
        _ = try await request(
            EmptyResponse.self,
            path: "/api/v1/feedbacks/\(feedbackId)/converted-text",
            method: "PUT",
            body: UpdateBody(converted_text: newText)
        )
    }

    // MARK: - FB承認フロー

    /// 承認待ちFB一覧を取得
    func fetchPendingFeedbacks() async throws -> [FeedbackItem] {
        try await request([FeedbackItem].self, path: "/api/v1/feedbacks/pending")
    }

    /// FBを承認する
    func approveFeedback(feedbackId: String) async throws {
        struct ApproveBody: Encodable {
            let approved_by: String
        }
        _ = try await request(
            EmptyResponse.self,
            path: "/api/v1/feedbacks/\(feedbackId)/approve",
            method: "PUT",
            body: ApproveBody(approved_by: actorName)
        )
    }

    /// FBを修正して承認する
    func modifyFeedback(feedbackId: String, modifiedText: String) async throws {
        struct ModifyBody: Encodable {
            let modified_text: String
            let approved_by: String
        }
        _ = try await request(
            EmptyResponse.self,
            path: "/api/v1/feedbacks/\(feedbackId)/modify",
            method: "PUT",
            body: ModifyBody(modified_text: modifiedText, approved_by: actorName)
        )
    }

    /// FBを却下する
    func rejectFeedback(feedbackId: String) async throws {
        struct RejectBody: Encodable {
            let approved_by: String
        }
        _ = try await request(
            EmptyResponse.self,
            path: "/api/v1/feedbacks/\(feedbackId)/reject",
            method: "PUT",
            body: RejectBody(approved_by: actorName)
        )
    }

    // MARK: - FB指示トラッカー

    func fetchFBTracker(projectId: String) async throws -> FBTrackerResponse {
        let encoded = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        return try await request(FBTrackerResponse.self, path: "/api/v1/projects/\(encoded)/fb-tracker")
    }

    func updateFBTrackingStatus(projectId: String, commentUri: String, status: String) async throws {
        struct StatusBody: Encodable {
            let status: String
        }
        let encodedProject = projectId.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? projectId
        let encodedUri = commentUri.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? commentUri
        _ = try await request(
            EmptyResponse.self,
            path: "/api/v1/projects/\(encodedProject)/fb-tracker/\(encodedUri)",
            method: "PATCH",
            body: StatusBody(status: status)
        )
    }

    func editVimeoComment(commentId: String, videoId: String, newText: String) async throws {
        struct EditBody: Encodable {
            let video_id: String
            let text: String
        }
        _ = try await request(
            EmptyResponse.self,
            path: "/api/v1/vimeo/comments/\(commentId)",
            method: "PATCH",
            body: EditBody(video_id: videoId, text: newText)
        )
    }

    /// Vimeoコメント取得（VimeoReviewViewModelから呼ばれる）
    func fetchVimeoComments(projectId: String) async throws -> VimeoCommentsResponse {
        try await request(VimeoCommentsResponse.self, path: "/api/v1/projects/\(projectId)/vimeo-comments")
    }

    // MARK: - Internal request routing

    private func request<T: Decodable>(
        _ type: T.Type,
        path: String,
        method: String = "GET"
    ) async throws -> T {
        try await performRequest(baseURL: activeBaseURL, path: path, method: method)
    }

    private func request<T: Decodable, Body: Encodable>(
        _ type: T.Type,
        path: String,
        method: String,
        body: Body
    ) async throws -> T {
        try await performRequest(baseURL: activeBaseURL, path: path, method: method, body: body)
    }

    /// モバイル通信対応: リトライ可能なURLErrorコード
    private let retryableErrorCodes: [URLError.Code] = [
        .timedOut, .cannotFindHost, .cannotConnectToHost,
        .networkConnectionLost, .notConnectedToInternet,
        .dnsLookupFailed, .secureConnectionFailed
    ]

    private func performRequest<T: Decodable>(
        baseURL: URL,
        path: String,
        method: String,
        retryCount: Int = 0
    ) async throws -> T {
        let url = buildURL(base: baseURL, path: path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        // モバイル通信（4G/5G + Cloudflareトンネル + TLSハンドシェイク）を考慮し25秒
        request.timeoutInterval = 25

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.server(statusCode: httpResponse.statusCode)
            }

            if T.self == EmptyResponse.self, let empty = EmptyResponse() as? T {
                return empty
            }

            return try decoder.decode(T.self, from: data)
        } catch let error as URLError where retryableErrorCodes.contains(error.code) && retryCount < 2 {
            // モバイル通信対応: 最大2回リトライ（1秒→2秒の指数バックオフ）
            let delay = UInt64(pow(2.0, Double(retryCount))) * 1_000_000_000
            print("🔄 APIリトライ \(retryCount + 1)/2: \(path) (\(error.code.rawValue))")
            try? await Task.sleep(nanoseconds: delay)
            // ベースURLが変わっていれば新しいURLでリトライ
            await reconnectIfNeeded(error: error)
            let retryBase = activeBaseURL != baseURL ? activeBaseURL : baseURL
            return try await performRequest(baseURL: retryBase, path: path, method: method, retryCount: retryCount + 1)
        } catch let error where error is URLError {
            await reconnectIfNeeded(error: error)
            if activeBaseURL != baseURL {
                return try await performRequest(baseURL: activeBaseURL, path: path, method: method)
            }
            throw error
        }
    }

    private func performRequest<T: Decodable, Body: Encodable>(
        baseURL: URL,
        path: String,
        method: String,
        body: Body,
        retryCount: Int = 0
    ) async throws -> T {
        let url = buildURL(base: baseURL, path: path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        // モバイル通信（4G/5G + Cloudflareトンネル + TLSハンドシェイク）を考慮し25秒
        request.timeoutInterval = 25
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.server(statusCode: httpResponse.statusCode)
            }

            if T.self == EmptyResponse.self, let empty = EmptyResponse() as? T {
                return empty
            }

            return try decoder.decode(T.self, from: data)
        } catch let error as URLError where retryableErrorCodes.contains(error.code) && retryCount < 2 {
            // モバイル通信対応: 最大2回リトライ（1秒→2秒の指数バックオフ）
            let delay = UInt64(pow(2.0, Double(retryCount))) * 1_000_000_000
            print("🔄 APIリトライ \(retryCount + 1)/2: \(path) (\(error.code.rawValue))")
            try? await Task.sleep(nanoseconds: delay)
            await reconnectIfNeeded(error: error)
            let retryBase = activeBaseURL != baseURL ? activeBaseURL : baseURL
            return try await performRequest(baseURL: retryBase, path: path, method: method, body: body, retryCount: retryCount + 1)
        } catch let error where error is URLError {
            await reconnectIfNeeded(error: error)
            if activeBaseURL != baseURL {
                return try await performRequest(baseURL: activeBaseURL, path: path, method: method, body: body)
            }
            throw error
        }
    }

    /// 長時間実行API用（タイムアウト延長）
    private func performLongRequest<T: Decodable, Body: Encodable>(
        _ type: T.Type = T.self,
        path: String,
        method: String,
        body: Body,
        timeout: TimeInterval
    ) async throws -> T {
        let currentBase = activeBaseURL
        let url = buildURL(base: currentBase, path: path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = timeout
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.server(statusCode: httpResponse.statusCode)
            }
            return try decoder.decode(T.self, from: data)
        } catch let error where error is URLError {
            await reconnectIfNeeded(error: error)
            if activeBaseURL != currentBase {
                return try await performLongRequest(type, path: path, method: method, body: body, timeout: timeout)
            }
            throw error
        }
    }

    /// JSONSerializationベースのperformRequest（[String: Any] / [[String: Any]] 返却用）
    /// 手修正API 8メソッド統合用
    private func performRequestRaw(
        baseURL: URL,
        path: String,
        method: String,
        body: (any Encodable)? = nil
    ) async throws -> Data {
        let url = buildURL(base: baseURL, path: path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        // モバイル通信（4G/5G + Cloudflareトンネル + TLSハンドシェイク）を考慮し25秒
        request.timeoutInterval = 25
        if let body = body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(body)
        }

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.server(statusCode: httpResponse.statusCode)
            }
            return data
        } catch let error where error is URLError {
            await reconnectIfNeeded(error: error)
            if activeBaseURL != baseURL {
                return try await performRequestRaw(baseURL: activeBaseURL, path: path, method: method, body: body)
            }
            throw error
        }
    }

    // クエリパラメータ付きパスを正しくURLに変換するヘルパー
    func buildURL(base: URL, path: String) -> URL {
        let fullString = base.absoluteString + path
        if let url = URL(string: fullString) {
            return url
        }
        if let encoded = fullString.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
           let url = URL(string: encoded) {
            return url
        }
        return base.appending(path: path)
    }
}

// MARK: - APIError

enum APIError: Error {
    case invalidResponse
    case server(statusCode: Int)
}

struct EmptyResponse: Decodable {}

private struct DescriptionPayload: Encodable {
    let edited: String
    let by: String
}

private struct TitleSelectionPayload: Encodable {
    let index: Int
    let editedTitle: String?
    let by: String
}

struct CategoryUpdateBody: Encodable {
    let category: String?
}

// MARK: - 素材動画モデル

struct SourceVideoItem: Codable, Identifiable {
    let id: Int?
    let projectId: String
    let youtubeUrl: String
    let videoId: String
    let title: String?
    let duration: String?
    let qualityStatus: String?
    let source: String?
    let knowledgeFile: String?
    let createdAt: String?

    var embedURL: String {
        "https://www.youtube.com/embed/\(videoId)?playsinline=1&rel=0"
    }

    var watchURL: String {
        "https://www.youtube.com/watch?v=\(videoId)"
    }
}

struct SourceVideosResponse: Codable {
    let projectId: String
    let total: Int
    let videos: [SourceVideoItem]
}

struct SourceVideoCreateBody: Encodable {
    let youtubeUrl: String
    let title: String?
    let qualityStatus: String
}

// MARK: - 手修正APIリクエストボディ

private struct DirectionEditBody: Encodable {
    let editedContent: String
    let editedBy: String
    let editNotes: String?
}

private struct AssetEditBody: Encodable {
    let editedContent: String
    let editedBy: String
}

// MARK: - 手修正API（performRequestRaw経由に統合）

extension APIClient {

    /// ディレクションレポートを更新（PUT）
    func updateDirectionReport(
        projectId: String,
        editedContent: String,
        editedBy: String,
        editNotes: String? = nil
    ) async throws -> [String: Any] {
        let body = DirectionEditBody(
            editedContent: editedContent,
            editedBy: editedBy,
            editNotes: editNotes
        )
        let data = try await performRequestRaw(
            baseURL: activeBaseURL,
            path: "/api/v1/projects/\(projectId)/direction-report",
            method: "PUT",
            body: body
        )
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// ディレクション編集履歴を取得
    func fetchDirectionEditHistory(projectId: String) async throws -> [[String: Any]] {
        let data = try await performRequestRaw(
            baseURL: activeBaseURL,
            path: "/api/v1/projects/\(projectId)/direction-report/history",
            method: "GET"
        )
        return (try? JSONSerialization.jsonObject(with: data) as? [[String: Any]]) ?? []
    }

    /// ディレクション編集diff（元 vs 修正）を取得
    func fetchDirectionEditDiff(projectId: String) async throws -> [String: Any] {
        let data = try await performRequestRaw(
            baseURL: activeBaseURL,
            path: "/api/v1/projects/\(projectId)/direction-report/diff",
            method: "GET"
        )
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// タイトルを更新
    func updateTitle(projectId: String, editedContent: String, editedBy: String) async throws -> [String: Any] {
        let body = AssetEditBody(editedContent: editedContent, editedBy: editedBy)
        let data = try await performRequestRaw(
            baseURL: activeBaseURL,
            path: "/api/v1/projects/\(projectId)/title",
            method: "PUT",
            body: body
        )
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// 概要欄を更新（手修正API用 — 既存のupdateDescriptionとは別エンドポイント）
    func updateDescription(projectId: String, editedContent: String, editedBy: String) async throws -> [String: Any] {
        let body = AssetEditBody(editedContent: editedContent, editedBy: editedBy)
        let data = try await performRequestRaw(
            baseURL: activeBaseURL,
            path: "/api/v1/projects/\(projectId)/description",
            method: "PUT",
            body: body
        )
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// サムネ指示書を更新
    func updateThumbnailInstruction(projectId: String, editedContent: String, editedBy: String) async throws -> [String: Any] {
        let body = AssetEditBody(editedContent: editedContent, editedBy: editedBy)
        let data = try await performRequestRaw(
            baseURL: activeBaseURL,
            path: "/api/v1/projects/\(projectId)/thumbnail-instruction",
            method: "PUT",
            body: body
        )
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// アセット編集履歴を取得（タイトル/概要/サムネ共通）
    func fetchAssetEditHistory(projectId: String, assetType: String) async throws -> [[String: Any]] {
        let pathType = assetType == "thumbnail" ? "thumbnail-instruction" : assetType
        let data = try await performRequestRaw(
            baseURL: activeBaseURL,
            path: "/api/v1/projects/\(projectId)/\(pathType)/history",
            method: "GET"
        )
        return (try? JSONSerialization.jsonObject(with: data) as? [[String: Any]]) ?? []
    }

    /// アセット編集diff（元 vs 修正）を取得（タイトル/概要/サムネ共通）
    func fetchAssetEditDiff(projectId: String, assetType: String) async throws -> [String: Any] {
        let pathType = assetType == "thumbnail" ? "thumbnail-instruction" : assetType
        let data = try await performRequestRaw(
            baseURL: activeBaseURL,
            path: "/api/v1/projects/\(projectId)/\(pathType)/diff",
            method: "GET"
        )
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }
}
