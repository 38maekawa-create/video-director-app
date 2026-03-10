import Foundation

@MainActor
final class ProjectListViewModel: ObservableObject {
    @Published var projects: [VideoProject] = MockData.projects
    @Published var searchText: String = ""

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
}
