import Foundation

@MainActor
final class DashboardViewModel: ObservableObject {
    enum Section: String, CaseIterable, Identifiable {
        case quality = "品質"
        case tracking = "トラッキング"
        case editors = "編集者"

        var id: String { rawValue }
    }

    @Published var selectedSection: Section = .quality
    @Published var summary: DashboardSummary?
    @Published var trend: [QualityTrendPoint] = []
    @Published var categoryScores: [CategoryScore] = MockData.categoryScores
    @Published var suggestions: [ImprovementSuggestion] = MockData.improvementSuggestions
    @Published var alerts: [QualityAlert] = []
    @Published var latestAudit: AuditReport?
    @Published var auditHistory: [AuditReport] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    var latestScore: Int {
        trend.last?.score ?? 0
    }

    var scoreDelta: Int {
        guard trend.count >= 2 else { return 0 }
        return trend[trend.count - 1].score - trend[trend.count - 2].score
    }

    func loadDashboard() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        async let summaryTask = APIClient.shared.fetchDashboardSummary()
        async let trendTask = APIClient.shared.fetchQualityTrend()
        async let auditTask = APIClient.shared.fetchLatestAudit()
        async let auditHistoryTask = APIClient.shared.fetchAuditHistory()

        do {
            let fetchedSummary = try await summaryTask
            let fetchedTrend = try await trendTask
            let fetchedAudit = try await auditTask
            let fetchedAuditHistory = try await auditHistoryTask

            summary = fetchedSummary
            trend = fetchedTrend.enumerated().map { index, item in
                QualityTrendPoint(
                    id: UUID(),
                    label: shortLabel(for: item, index: index),
                    score: item.qualityScore ?? 0
                )
            }
            latestAudit = fetchedAudit
            auditHistory = fetchedAuditHistory
            alerts = makeAlerts(summary: fetchedSummary, audit: fetchedAudit)
        } catch {
            // 本番運用: API失敗時はエラーメッセージを表示、既存データを保持
            errorMessage = "ダッシュボードAPIに接続できません: \(error.localizedDescription)"
        }
    }

    private func shortLabel(for item: QualityTrendItem, index: Int) -> String {
        if !item.guestName.isEmpty {
            return item.guestName
        }
        return "案件\(index + 1)"
    }

    private func makeAlerts(summary: DashboardSummary, audit: AuditReport) -> [QualityAlert] {
        var items: [QualityAlert] = []

        if summary.unsentFeedbackCount > 0 {
            items.append(
                QualityAlert(
                    id: UUID(),
                    level: "High",
                    message: "未送信フィードバックが\(summary.unsentFeedbackCount)件あります"
                )
            )
        }

        items.append(contentsOf: audit.qualityAnomalies.map {
            QualityAlert(id: UUID(), level: audit.overallHealth == "critical" ? "High" : "Medium", message: $0)
        })
        items.append(contentsOf: audit.staleProjects.map {
            QualityAlert(id: UUID(), level: "Medium", message: "滞留案件: \($0)")
        })

        if items.isEmpty {
            items.append(QualityAlert(id: UUID(), level: "Low", message: "現在アラートはありません"))
        }
        return items
    }
}
