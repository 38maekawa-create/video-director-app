import Foundation

@MainActor
final class APIClient: ObservableObject {
    static let shared = APIClient()

    let baseURL: URL
    let actorName: String

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
        baseURL = url
        actorName = actor
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

    private func request<T: Decodable>(
        _ type: T.Type,
        path: String,
        method: String = "GET"
    ) async throws -> T {
        try await performRequest(baseURL: baseURL, path: path, method: method)
    }

    private func request<T: Decodable, Body: Encodable>(
        _ type: T.Type,
        path: String,
        method: String,
        body: Body
    ) async throws -> T {
        try await performRequest(baseURL: baseURL, path: path, method: method, body: body)
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
    }

    // クエリパラメータ付きパスを正しくURLに変換するヘルパー
    // URL.appending(path:) はクエリ文字列の ? を %3F にエンコードしてしまうため
    private func buildURL(base: URL, path: String) -> URL {
        guard let url = URL(string: base.absoluteString + path) else {
            // フォールバック: 従来の方式
            return base.appending(path: path)
        }
        return url
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
