import Foundation
import Combine

/// Vimeo APIコメントのレスポンス
struct VimeoCommentsResponse: Codable {
    let projectId: String
    let total: Int?
    let comments: [VimeoCommentItem]?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case projectId = "project_id"
        case total, comments, message
    }
}

/// Vimeo APIから取得した個別コメント
struct VimeoCommentItem: Codable, Identifiable {
    var id: String { uri.isEmpty ? UUID().uuidString : uri }
    let vimeoId: String
    let versionLabel: String
    let text: String
    let timecode: String?
    let createdTime: String
    let user: String
    let uri: String
    let error: Bool?

    enum CodingKeys: String, CodingKey {
        case vimeoId = "vimeo_id"
        case versionLabel = "version_label"
        case text, timecode
        case createdTime = "created_time"
        case user, uri, error
    }
}

/// Vimeoレビュー画面のViewModel
/// - Vimeo APIからのコメント取得
/// - 再生状態の保持
/// - 接続ステータスの表示
@MainActor
final class VimeoReviewViewModel: ObservableObject {
    /// Vimeo APIから取得したコメント一覧
    @Published var vimeoComments: [VimeoCommentItem] = []
    /// API接続ステータスメッセージ
    @Published var statusMessage: String?
    /// API接続成功フラグ（nil=未取得、true=成功、false=エラー）
    @Published var apiConnected: Bool?
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
    /// Vimeo動画ID（VimeoReviewTabViewからeditedVideoURLベースで設定される）
    @Published var vimeoVideoId: String = ""

    // 後方互換: feedbacksを参照している箇所のために残す
    @Published var feedbacks: [VimeoFeedbackItem] = []

    /// Vimeo APIからコメントを取得
    func loadVimeoComments(projectId: String) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await fetchVimeoComments(projectId: projectId)
            vimeoComments = response.comments ?? []
            apiConnected = true

            if let msg = response.message {
                // APIからのメッセージ（トークン未設定等）
                statusMessage = msg
                apiConnected = false
            } else if vimeoComments.isEmpty {
                statusMessage = "Vimeo API接続OK — レビューコメントはまだありません"
            } else {
                statusMessage = "Vimeo API接続OK — \(vimeoComments.count)件のコメント"
            }

            // エラーコメントがあればステータスに反映
            let errors = vimeoComments.filter { $0.error == true }
            if !errors.isEmpty {
                statusMessage = errors.first?.text
                apiConnected = false
            }
        } catch {
            apiConnected = false
            statusMessage = "API接続エラー: \(error.localizedDescription)"
            vimeoComments = []
        }
    }

    /// 後方互換: loadFeedbacksを呼ばれたらloadVimeoCommentsに委譲
    func loadFeedbacks(projectId: String) async {
        await loadVimeoComments(projectId: projectId)
    }

    /// Vimeoコメントを編集（Vimeo APIのPATCHで直接書き換え）
    func editComment(comment: VimeoCommentItem, newText: String, projectId: String) async {
        // URIからcomment_idを抽出（"/videos/12345/comments/67890" → "67890"）
        let commentId = comment.uri.components(separatedBy: "/").last ?? ""
        guard !commentId.isEmpty else {
            errorMessage = "コメントIDが取得できません"
            return
        }

        do {
            try await APIClient.shared.editVimeoComment(
                commentId: commentId,
                videoId: comment.vimeoId,
                newText: newText
            )
            // 成功したらコメント一覧を再読み込み
            await loadVimeoComments(projectId: projectId)
        } catch {
            errorMessage = "コメント編集エラー: \(error.localizedDescription)"
        }
    }

    /// 指定タイムコードへシーク
    func seek(to seconds: TimeInterval) {
        seekTarget = seconds
        currentTime = seconds
    }

    // MARK: - Private

    private func fetchVimeoComments(projectId: String) async throws -> VimeoCommentsResponse {
        // APIClient経由で統一（フォールバック・リトライ機構を活用）
        return try await APIClient.shared.fetchVimeoComments(projectId: projectId)
    }
}
