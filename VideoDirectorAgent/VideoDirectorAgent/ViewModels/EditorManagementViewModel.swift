import Foundation

@MainActor
final class EditorManagementViewModel: ObservableObject {
    @Published var editors: [Editor] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    private var hasLoaded = false

    func loadEditors(forceRefresh: Bool = false) async {
        if !forceRefresh && hasLoaded { return }
        if isLoading { return }
        isLoading = true
        defer { isLoading = false }

        do {
            editors = try await APIClient.shared.fetchEditors()
            errorMessage = nil
            hasLoaded = true
        } catch {
            // API失敗時は既存データを保持してエラーのみ表示
            if editors.isEmpty {
                errorMessage = "編集者APIに接続できません: \(error.localizedDescription)"
            }
        }
    }
}
