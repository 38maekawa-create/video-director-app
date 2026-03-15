import Foundation

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published var trend: [QualityTrendPoint] = MockData.qualityTrend
    @Published var skills: [EditorSkill] = MockData.editorSkills
    @Published var alerts: [QualityAlert] = MockData.alerts
}
