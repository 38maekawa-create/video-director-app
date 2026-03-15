import Foundation

private enum ShootDateParser {
    static let formats: [DateFormatter] = {
        ["yyyy/MM/dd", "yyyy-MM-dd"].map { format in
            let formatter = DateFormatter()
            formatter.calendar = Calendar(identifier: .gregorian)
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.timeZone = TimeZone(secondsFromGMT: 0)
            formatter.dateFormat = format
            return formatter
        }
    }()

    static func parse(_ value: String) -> Date? {
        for formatter in formats {
            if let date = formatter.date(from: value) {
                return date
            }
        }
        return nil
    }
}

@MainActor
final class ProjectListViewModel: ObservableObject {
    @Published var projects: [VideoProject] = []
    @Published var searchText: String = ""
    @Published var isLoading = false
    @Published var errorMessage: String?

    private var hasLoaded = false

    var filteredProjects: [VideoProject] {
        if searchText.isEmpty { return projects }
        return projects.filter {
            $0.guestName.localizedCaseInsensitiveContains(searchText) ||
            $0.title.localizedCaseInsensitiveContains(searchText) ||
            $0.shootDate.contains(searchText)
        }
    }

    var recentFeedbackProjects: [VideoProject] {
        projects.filter { $0.unreviewedCount > 0 }
    }

    var actionRequiredProjects: [VideoProject] {
        projects.filter { $0.hasUnsentFeedback }
    }

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
            projects = fetched.sorted { lhs, rhs in
                let leftDate = ShootDateParser.parse(lhs.shootDate)
                let rightDate = ShootDateParser.parse(rhs.shootDate)

                switch (leftDate, rightDate) {
                case let (l?, r?):
                    if l != r { return l > r }
                case (_?, nil):
                    return true
                case (nil, _?):
                    return false
                case (nil, nil):
                    break
                }

                return lhs.shootDate > rhs.shootDate
            }
            errorMessage = nil
        } catch {
            if projects.isEmpty {
                errorMessage = "APIサーバーに接続できません。(\(error.localizedDescription))"
            }
            print("API Error: \(error)")
        }
    }
}
