import Foundation

@MainActor
final class DashboardViewModel: ObservableObject {
    @Published var trend: [QualityTrendPoint] = MockData.qualityTrend
    @Published var categoryScores: [CategoryScore] = MockData.categoryScores
    @Published var suggestions: [ImprovementSuggestion] = MockData.improvementSuggestions
    @Published var skills: [EditorSkill] = MockData.editorSkills
    @Published var alerts: [QualityAlert] = MockData.alerts

    // 最新スコア
    var latestScore: Int {
        trend.last?.score ?? 0
    }

    // 前回比
    var scoreDelta: Int {
        guard trend.count >= 2 else { return 0 }
        return trend[trend.count - 1].score - trend[trend.count - 2].score
    }

    // カテゴリ平均
    var averageCategoryScore: Int {
        guard !categoryScores.isEmpty else { return 0 }
        return categoryScores.map(\.score).reduce(0, +) / categoryScores.count
    }
}
