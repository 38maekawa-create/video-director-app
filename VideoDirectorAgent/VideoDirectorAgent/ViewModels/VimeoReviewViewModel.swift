import Foundation
import Combine

/// Vimeoレビュー画面のViewModel
/// - フィードバック一覧の取得・管理
/// - 再生状態の保持
@MainActor
final class VimeoReviewViewModel: ObservableObject {
    /// 表示するフィードバック一覧（timestamp_markでソート済み）
    @Published var feedbacks: [VimeoFeedbackItem] = []
    /// 動画の総再生時間（秒）
    @Published var duration: TimeInterval = 0
    /// 現在の再生位置（秒）
    @Published var currentTime: TimeInterval = 0
    /// 再生中フラグ
    @Published var isPlaying: Bool = false
    /// ローディング状態
    @Published var isLoading: Bool = false
    /// エラーメッセージ
    @Published var errorMessage: String?

    /// シーク先タイムコード（VimeoPlayerView へ伝播）
    @Published var seekTarget: TimeInterval?
    /// Vimeo動画ID
    @Published var vimeoVideoId: String = MockData.sampleVimeoVideoId

    private let baseURL = "http://localhost:8210"

    /// APIからフィードバック一覧を取得（失敗時はモックにフォールバック）
    func loadFeedbacks(projectId: String) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let fetched = try await fetchFeedbacksFromAPI(projectId: projectId)
            // timestamp_mark 昇順でソート
            feedbacks = fetched.sorted { $0.timestampMark < $1.timestampMark }
        } catch {
            // API未到達時: モックデータにフォールバック
            feedbacks = MockData.vimeoFeedbacks.sorted { $0.timestampMark < $1.timestampMark }
            // ローカルAPIのエラーは無視（開発環境前提）
        }
    }

    /// 指定タイムコードへシーク
    func seek(to seconds: TimeInterval) {
        seekTarget = seconds
        currentTime = seconds
    }

    // MARK: - Private

    private func fetchFeedbacksFromAPI(projectId: String) async throws -> [VimeoFeedbackItem] {
        guard let url = URL(string: "\(baseURL)/api/v1/projects/\(projectId)/feedbacks-with-timecodes") else {
            throw URLError(.badURL)
        }
        let (data, response) = try await URLSession.shared.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        let decoded = try JSONDecoder().decode([VimeoFeedbackItem].self, from: data)
        return decoded
    }
}
