import Foundation

@MainActor
final class ProjectListViewModel: ObservableObject {
    @Published var projects: [VideoProject] = []
    @Published var searchText: String = ""
    @Published var isLoading = false
    @Published var errorMessage: String?

    private var hasLoaded = false

    // フィルタ済みプロジェクト
    var filteredProjects: [VideoProject] {
        if searchText.isEmpty { return projects }
        return projects.filter {
            $0.guestName.localizedCaseInsensitiveContains(searchText) ||
            $0.title.localizedCaseInsensitiveContains(searchText) ||
            $0.shootDate.contains(searchText)
        }
    }

    // 最近のFBがあるプロジェクト
    var recentFeedbackProjects: [VideoProject] {
        projects.filter { $0.unreviewedCount > 0 }
    }

    // 要対応（未送信FBあり）
    var actionRequiredProjects: [VideoProject] {
        projects.filter { $0.hasUnsentFeedback }
    }

    // ヒーロープロジェクト（最新）
    var heroProject: VideoProject? {
        projects.first
    }

    func loadProjectsIfNeeded() async {
        guard !hasLoaded else { return }
        hasLoaded = true
        await loadProjects()
    }

    func refresh() async {
        hasLoaded = false
        await loadProjectsIfNeeded()
    }

    func loadProjects() async {
        isLoading = true
        defer { isLoading = false }

        do {
            projects = try await APIClient.shared.fetchProjects()
            errorMessage = nil
        } catch {
            // 本番運用: API未接続時はエラーを表示し、空リストを維持
            if projects.isEmpty {
                errorMessage = "APIサーバーに接続できません。サーバーが起動しているか確認してください。(\(error.localizedDescription))"
            } else {
                errorMessage = "データ更新に失敗しました。前回取得データを表示中。(\(error.localizedDescription))"
            }
            print("API Error: \(error)")
        }
    }
}
