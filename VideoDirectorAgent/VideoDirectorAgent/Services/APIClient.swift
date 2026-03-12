import Foundation

@MainActor
final class APIClient: ObservableObject {
    static let shared = APIClient()

    private let baseURL = URL(string: "http://mac-mini-m4.local:8210")!
    private let fallbackURL = URL(string: "http://localhost:8210")!

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

    private init() {}

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
        do {
            return try await performRequest(baseURL: baseURL, path: path, method: method)
        } catch {
            return try await performRequest(baseURL: fallbackURL, path: path, method: method)
        }
    }

    private func request<T: Decodable, Body: Encodable>(
        _ type: T.Type,
        path: String,
        method: String,
        body: Body
    ) async throws -> T {
        do {
            return try await performRequest(baseURL: baseURL, path: path, method: method, body: body)
        } catch {
            return try await performRequest(baseURL: fallbackURL, path: path, method: method, body: body)
        }
    }

    private func performRequest<T: Decodable>(
        baseURL: URL,
        path: String,
        method: String
    ) async throws -> T {
        let url = baseURL.appending(path: path)
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
        let url = baseURL.appending(path: path)
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
