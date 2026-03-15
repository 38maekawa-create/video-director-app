import Foundation
import SwiftUI

/// YouTube素材ViewModel: APIClient.shared経由でYouTube素材を取得
/// （YouTubeAssetsViewが直接APIClient.sharedを使用しているため、このViewModelは
///   将来的なリファクタリングや他画面からの利用に備えて残している）
@MainActor
class YouTubeAssetsViewModel: ObservableObject {
    @Published var assets: YouTubeAssets?
    @Published var isLoading = false
    @Published var errorMessage: String?

    /// プロジェクトIDを指定してYouTube素材を取得する。
    /// APIClient.shared経由で接続し、失敗時はエラーメッセージを表示。
    func fetchAssets(projectID: String) async {
        isLoading = true
        errorMessage = nil

        do {
            assets = try await APIClient.shared.fetchYouTubeAssets(projectId: projectID)
        } catch {
            assets = nil
            errorMessage = "YouTube素材の取得に失敗しました: \(error.localizedDescription)"
        }

        isLoading = false
    }
}
