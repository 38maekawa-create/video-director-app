import Foundation
import SwiftUI

/// YouTube素材ViewModel: GET /api/projects/{id} の youtube_assets フィールドを取得
@MainActor
class YouTubeAssetsViewModel: ObservableObject {
    @Published var assets: YouTubeAssets?
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let baseURL = "http://localhost:8210"

    /// プロジェクトIDを指定してYouTube素材を取得する。
    /// APIが利用できない場合はモックデータにフォールバック。
    func fetchAssets(projectID: String) async {
        isLoading = true
        errorMessage = nil

        guard let url = URL(string: "\(baseURL)/api/projects/\(projectID)") else {
            // URLが不正な場合はモックで代替
            assets = MockData.youtubeAssets
            isLoading = false
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                // HTTPエラー時はモックで代替
                assets = MockData.youtubeAssets
                isLoading = false
                return
            }
            let decoded = try JSONDecoder().decode(ProjectResponse.self, from: data)
            assets = decoded.youtubeAssets ?? MockData.youtubeAssets
        } catch {
            // ネットワーク未接続・パース失敗時はモックで代替
            assets = MockData.youtubeAssets
        }

        isLoading = false
    }
}

/// GET /api/projects/{id} のレスポンス全体（youtube_assets フィールドのみ使用）
private struct ProjectResponse: Codable {
    let youtubeAssets: YouTubeAssets?

    enum CodingKeys: String, CodingKey {
        case youtubeAssets = "youtube_assets"
    }
}
