import Foundation

@MainActor
final class EditorManagementViewModel: ObservableObject {
    @Published var editors: [Editor] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    func loadEditors() async {
        if isLoading { return }
        isLoading = true
        defer { isLoading = false }

        do {
            editors = try await APIClient.shared.fetchEditors()
            errorMessage = nil
        } catch {
            errorMessage = "編集者APIに接続できません: \(error.localizedDescription)"
        }
    }
}
