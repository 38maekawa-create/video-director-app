import Foundation

// フィードバック履歴のデータ管理をViewから分離し、タブ切り替え時の再ロードを防止
@MainActor
final class FeedbackHistoryViewModel: ObservableObject {
    @Published var items: [FeedbackHistoryItem] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    private var hasLoaded = false

    func loadIfNeeded() async {
        if hasLoaded || isLoading { return }
        await load()
    }

    func load(forceRefresh: Bool = false) async {
        if !forceRefresh && isLoading { return }
        isLoading = true
        defer { isLoading = false }

        do {
            let fetched = try await APIClient.shared.fetchAllFeedbacks()
            items = fetched.map(makeHistoryItem)
            errorMessage = nil
            hasLoaded = true
        } catch {
            errorMessage = "履歴APIに接続できません: \(error.localizedDescription)"
        }
    }

    private func makeHistoryItem(from item: FeedbackItem) -> FeedbackHistoryItem {
        FeedbackHistoryItem(
            id: UUID(),
            projectTitle: item.projectTitle ?? item.projectId,
            guestName: item.guestName ?? "ゲスト未設定",
            date: groupedDate(from: item.createdAt),
            timestamp: item.timestamp ?? "--:--",
            rawVoiceText: item.rawVoiceText ?? item.content,
            convertedText: item.convertedText ?? item.content,
            isSent: item.isSent,
            editorStatus: item.isSent ? "送信済み" : "未送信",
            learningEffect: item.feedbackType == "voice" ? "音声FB" : ""
        )
    }

    private func groupedDate(from value: String) -> String {
        if value.count >= 10 {
            return String(value.prefix(10)).replacingOccurrences(of: "-", with: "/")
        }
        return value.isEmpty ? "日付不明" : value
    }
}
