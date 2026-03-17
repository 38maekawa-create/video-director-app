import Foundation

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

    /// フォールバック候補URL一覧（優先順）
    /// 1. クラウドURL（DNS経由） 2. Tailscale（どこからでも） 3. ローカルIP（同一WiFi）
    private let candidateURLs: [URL]
    /// 接続状態
    @Published private(set) var connectionStatus: ConnectionStatus = .connecting

    enum ConnectionStatus: Equatable {
        case connecting
        case connected(String)  // 接続先のラベル
        case disconnected
    }

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

        // フォールバック候補を構築（優先順）
        var candidates = [url]
        // Tailscale経由（VPN越しにどこからでもアクセス可能）
        if let tailscale = URL(string: "http://100.110.206.6:8210") {
            candidates.append(tailscale)
        }
        // ローカルネットワーク（同一WiFi時のみ）
        if let local = URL(string: "http://mac-mini-m4.local:8210") {
            candidates.append(local)
        }
        candidateURLs = candidates
        // 初期値はプライマリURL（すぐにprobeで上書きされる）
        activeBaseURL = url
    }

    /// アプリ起動時に呼び出し: 到達可能なURLを自動検出
    func probeAndConnect() async {
        connectionStatus = .connecting
        for candidate in candidateURLs {
            let label = Self.labelFor(url: candidate)
            print("🔍 接続テスト: \(candidate.absoluteString) (\(label))")
            if await isReachable(url: candidate) {
                activeBaseURL = candidate
                connectionStatus = .connected(label)
                print("✅ 接続成功: \(candidate.absoluteString) (\(label))")
                return
            }
            print("❌ 接続失敗: \(candidate.absoluteString)")
        }
        // 全候補到達不可 → プライマリURLで待機
        activeBaseURL = primaryURL
        connectionStatus = .disconnected
        print("⚠️ 全URL到達不可。プライマリURL(\(primaryURL))で待機")
    }

    /// URLの到達可能性テスト（軽量ヘルスチェック）
    private func isReachable(url: URL) async -> Bool {
        let testURL = url.appendingPathComponent("/api/projects")
        var request = URLRequest(url: testURL)
        request.httpMethod = "GET"
        request.timeoutInterval = 3  // 高速タイムアウト
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

    /// ネットワークエラー時に自動再接続を試行
    private func reconnectIfNeeded(error: Error) async {
        // URLErrorの場合のみ再接続（タイムアウト、接続拒否、ホスト解決失敗等）
        guard let urlError = error as? URLError else { return }
        let reconnectCodes: [URLError.Code] = [
            .timedOut, .cannotFindHost, .cannotConnectToHost,
            .networkConnectionLost, .notConnectedToInternet,
            .dnsLookupFailed, .secureConnectionFailed
        ]
        guard reconnectCodes.contains(urlError.code) else { return }
        print("🔄 ネットワークエラー検知。再接続を試行...")
        await probeAndConnect()
    }

    private static func labelFor(url: URL) -> String {
        let host = url.host ?? ""
        if host.contains("legit-marc.com") { return "☁️ クラウド" }
        if host.starts(with: "100.") { return "🔗 Tailscale" }
        if host.contains(".local") { return "🏠 ローカル" }
        if host.starts(with: "192.") || host.starts(with: "172.") || host.starts(with: "10.") {
            return "🏠 ローカル"
        }
        return host
    }

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

    /// 品質ダッシュボード統計（グレード分布・改善傾向）を取得
    func fetchQualityStats() async throws -> QualityStats {
        try await request(QualityStats.self, path: "/api/v1/dashboard/quality")
    }

    /// 編集後フィードバックを取得（Before/After差分分析）
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

    /// E2Eパイプラインを実行する（FB→学習→ディレクション生成→Vimeo投稿）
    /// 長時間処理のためタイムアウトを120秒に設定
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

    /// テロップチェック結果を取得（キャッシュ済み）
    func fetchTelopCheck(projectId: String) async throws -> TelopCheckResponse {
        try await request(TelopCheckResponse.self, path: "/api/v1/projects/\(projectId)/telop-check")
    }

    /// テロップチェックを実行する
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

    /// 音声品質評価結果を取得（キャッシュ済み）
    func fetchAudioEvaluation(projectId: String) async throws -> AudioEvaluationResponse {
        try await request(AudioEvaluationResponse.self, path: "/api/v1/projects/\(projectId)/audio-evaluation")
    }

    /// 音声品質評価を実行する
    func runAudioEvaluation(projectId: String) async throws -> AudioEvaluationResponse {
        try await request(
            AudioEvaluationResponse.self,
            path: "/api/v1/projects/\(projectId)/audio-evaluation",
            method: "POST"
        )
    }

    // MARK: - ナレッジページ

    /// ナレッジページ一覧を取得
    func fetchKnowledgePages(limit: Int = 50, offset: Int = 0) async throws -> KnowledgePagesResponse {
        try await request(
            KnowledgePagesResponse.self,
            path: "/api/v1/knowledge/pages?limit=\(limit)&offset=\(offset)"
        )
    }

    /// ナレッジページ詳細を取得（HTML形式）
    func fetchKnowledgePageDetail(pageId: String) async throws -> KnowledgePageDetail {
        try await request(
            KnowledgePageDetail.self,
            path: "/api/v1/knowledge/pages/\(pageId)?format=html"
        )
    }

    /// ナレッジ検索
    func searchKnowledge(query: String, limit: Int = 20) async throws -> KnowledgeSearchResponse {
        let encodedQuery = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        return try await request(
            KnowledgeSearchResponse.self,
            path: "/api/v1/knowledge/search?q=\(encodedQuery)&limit=\(limit)"
        )
    }

    // MARK: - 素材動画（Source Videos）

    /// プロジェクトに紐づく素材動画一覧を取得
    func fetchSourceVideos(projectId: String) async throws -> SourceVideosResponse {
        try await request(
            SourceVideosResponse.self,
            path: "/api/v1/projects/\(projectId)/source-videos"
        )
    }

    /// 素材動画を手動登録
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

    /// プロジェクトの全動画バージョン一覧を取得（素材 vs 編集後 vs FB後）
    func fetchBeforeAfter(projectId: String) async throws -> BeforeAfterResponse {
        try await request(BeforeAfterResponse.self, path: "/api/v1/projects/\(projectId)/before-after")
    }

    /// 文字起こしdiff分析結果を取得（バージョン指定可能）
    func fetchTranscriptDiff(projectId: String, version: String? = nil) async throws -> TranscriptDiffResponse {
        var path = "/api/v1/projects/\(projectId)/transcript-diff"
        if let ver = version, !ver.isEmpty {
            let encoded = ver.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ver
            path += "?version=\(encoded)"
        }
        return try await request(TranscriptDiffResponse.self, path: path)
    }

    // MARK: - カテゴリ

    /// カテゴリ別プロジェクト一覧を取得
    func fetchProjectsByCategory(_ category: String) async throws -> [VideoProject] {
        try await request([VideoProject].self, path: "/api/v1/projects/by-category/\(category)")
    }

    /// プロジェクトのカテゴリを変更
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
        feedbackType: String
    ) async throws {
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

    /// Vimeoコメントを編集（Vimeo APIのPATCHで直接書き換え）
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

    private func performRequest<T: Decodable>(
        baseURL: URL,
        path: String,
        method: String
    ) async throws -> T {
        let url = buildURL(base: baseURL, path: path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 12

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            guard (200...299).contains(httpResponse.statusCode) else {
                throw APIError.server(statusCode: httpResponse.statusCode)
            }

            if T.self == EmptyResponse.self {
                return EmptyResponse() as! T
            }

            return try decoder.decode(T.self, from: data)
        } catch let error where error is URLError {
            // ネットワークエラー → 自動再接続して1回だけリトライ
            await reconnectIfNeeded(error: error)
            if activeBaseURL != baseURL {
                // 別のURLに切り替わった → リトライ
                return try await performRequest(baseURL: activeBaseURL, path: path, method: method)
            }
            throw error
        }
    }

    private func performRequest<T: Decodable, Body: Encodable>(
        baseURL: URL,
        path: String,
        method: String,
        body: Body
    ) async throws -> T {
        let url = buildURL(base: baseURL, path: path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 12
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

            if T.self == EmptyResponse.self {
                return EmptyResponse() as! T
            }

            return try decoder.decode(T.self, from: data)
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

    // クエリパラメータ付きパスを正しくURLに変換するヘルパー
    // URL.appending(path:) はクエリ文字列の ? を %3F にエンコードしてしまうため
    // 日本語を含むパス（プロジェクトID等）もパーセントエンコーディングで対応
    func buildURL(base: URL, path: String) -> URL {
        let fullString = base.absoluteString + path
        // まず直接URLを試みる
        if let url = URL(string: fullString) {
            return url
        }
        // 日本語等の非ASCII文字をパーセントエンコーディング
        if let encoded = fullString.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
           let url = URL(string: encoded) {
            return url
        }
        // 最終フォールバック
        return base.appending(path: path)
    }
}

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

    /// YouTube埋め込みURL
    var embedURL: String {
        "https://www.youtube.com/embed/\(videoId)?playsinline=1&rel=0"
    }

    /// YouTube視聴URL
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

// MARK: - 手修正API（APIClient拡張）

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
        let url = buildURL(base: baseURL, path: "/api/v1/projects/\(projectId)/direction-report")
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.timeoutInterval = 12
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server(statusCode: httpResponse.statusCode)
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// ディレクション編集履歴を取得
    func fetchDirectionEditHistory(projectId: String) async throws -> [[String: Any]] {
        let url = buildURL(base: baseURL, path: "/api/v1/projects/\(projectId)/direction-report/history")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 12

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server(statusCode: httpResponse.statusCode)
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [[String: Any]]) ?? []
    }

    /// ディレクション編集diff（元 vs 修正）を取得
    func fetchDirectionEditDiff(projectId: String) async throws -> [String: Any] {
        let url = buildURL(base: baseURL, path: "/api/v1/projects/\(projectId)/direction-report/diff")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 12

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server(statusCode: httpResponse.statusCode)
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// タイトルを更新
    func updateTitle(projectId: String, editedContent: String, editedBy: String) async throws -> [String: Any] {
        let body = AssetEditBody(editedContent: editedContent, editedBy: editedBy)
        let url = buildURL(base: baseURL, path: "/api/v1/projects/\(projectId)/assets/title")
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.timeoutInterval = 12
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server(statusCode: httpResponse.statusCode)
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// 概要欄を更新（手修正API用 — 既存のupdateDescriptionとは別エンドポイント）
    func updateDescription(projectId: String, editedContent: String, editedBy: String) async throws -> [String: Any] {
        let body = AssetEditBody(editedContent: editedContent, editedBy: editedBy)
        let url = buildURL(base: baseURL, path: "/api/v1/projects/\(projectId)/assets/description")
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.timeoutInterval = 12
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server(statusCode: httpResponse.statusCode)
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// サムネ指示書を更新
    func updateThumbnailInstruction(projectId: String, editedContent: String, editedBy: String) async throws -> [String: Any] {
        let body = AssetEditBody(editedContent: editedContent, editedBy: editedBy)
        let url = buildURL(base: baseURL, path: "/api/v1/projects/\(projectId)/assets/thumbnail")
        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.timeoutInterval = 12
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server(statusCode: httpResponse.statusCode)
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }

    /// アセット編集履歴を取得（タイトル/概要/サムネ共通）
    func fetchAssetEditHistory(projectId: String, assetType: String) async throws -> [[String: Any]] {
        let url = buildURL(base: baseURL, path: "/api/v1/projects/\(projectId)/assets/\(assetType)/history")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 12

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server(statusCode: httpResponse.statusCode)
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [[String: Any]]) ?? []
    }

    /// アセット編集diff（元 vs 修正）を取得（タイトル/概要/サムネ共通）
    func fetchAssetEditDiff(projectId: String, assetType: String) async throws -> [String: Any] {
        let url = buildURL(base: baseURL, path: "/api/v1/projects/\(projectId)/assets/\(assetType)/diff")
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 12

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.server(statusCode: httpResponse.statusCode)
        }
        return (try? JSONSerialization.jsonObject(with: data) as? [String: Any]) ?? [:]
    }
}
