import Foundation

@MainActor
final class ProjectListViewModel: ObservableObject {
    @Published var projects: [VideoProject] = MockData.projects
}
