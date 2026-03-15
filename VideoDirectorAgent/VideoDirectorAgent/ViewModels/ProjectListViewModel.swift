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
        await loadProjects()
    }

    func loadProjects() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let fetched = try await APIClient.shared.fetchProjects()
            // 撮影日の新しい順にソート
            projects = fetched.sorted { $0.shootDate > $1.shootDate }
            errorMessage = nil
        } catch {
            // 本番運用: API未接続時はエラーを表示
            if projects.isEmpty {
                errorMessage = "APIサーバーに接続できません。(\(error.localizedDescription))"
            }
            // データが既にある場合はエラー表示しない（前回データをそのまま表示）
            print("API Error: \(error)")
        }
    }
}
