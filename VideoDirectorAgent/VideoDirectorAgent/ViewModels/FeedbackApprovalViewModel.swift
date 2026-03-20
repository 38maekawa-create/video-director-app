import Foundation
import SwiftUI

/// FB承認フローのViewModel
/// 承認待ちFBの一覧取得・承認・修正・却下を管理する
@MainActor
final class FeedbackApprovalViewModel: ObservableObject {
    @Published var pendingFeedbacks: [FeedbackItem] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var successMessage: String?

    /// 承認待ちFB件数（バッジ表示用）
    var pendingCount: Int { pendingFeedbacks.count }

    /// 承認待ちFB一覧を取得
    func fetchPending() async {
        isLoading = true
        errorMessage = nil
        do {
            pendingFeedbacks = try await APIClient.shared.fetchPendingFeedbacks()
        } catch {
            errorMessage = "承認待ちFBの取得に失敗: \(error.localizedDescription)"
        }
        isLoading = false
    }

    /// FBを承認する
    func approve(feedbackId: String) async {
        errorMessage = nil
        successMessage = nil
        do {
            try await APIClient.shared.approveFeedback(feedbackId: feedbackId)
            // 一覧から除去
            pendingFeedbacks.removeAll { $0.id == feedbackId }
            successMessage = "承認しました"
        } catch {
            errorMessage = "承認に失敗: \(error.localizedDescription)"
        }
    }

    /// FBを修正して承認する
    func modify(feedbackId: String, modifiedText: String) async {
        errorMessage = nil
        successMessage = nil
        do {
            try await APIClient.shared.modifyFeedback(
                feedbackId: feedbackId,
                modifiedText: modifiedText
            )
            // 一覧から除去
            pendingFeedbacks.removeAll { $0.id == feedbackId }
            successMessage = "修正承認しました"
        } catch {
            errorMessage = "修正承認に失敗: \(error.localizedDescription)"
        }
    }

    /// FBを却下する
    func reject(feedbackId: String) async {
        errorMessage = nil
        successMessage = nil
        do {
            try await APIClient.shared.rejectFeedback(feedbackId: feedbackId)
            // 一覧から除去
            pendingFeedbacks.removeAll { $0.id == feedbackId }
            successMessage = "却下しました"
        } catch {
            errorMessage = "却下に失敗: \(error.localizedDescription)"
        }
    }
}
