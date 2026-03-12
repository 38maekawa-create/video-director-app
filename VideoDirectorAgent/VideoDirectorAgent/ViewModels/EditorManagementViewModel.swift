import Foundation

@MainActor
final class EditorManagementViewModel: ObservableObject {
    @Published var editors: [Editor] = MockData.editorDirectory
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
            editors = MockData.editorDirectory
            errorMessage = "編集者APIに接続できなかったためモックデータを表示しています"
        }
    }
}
