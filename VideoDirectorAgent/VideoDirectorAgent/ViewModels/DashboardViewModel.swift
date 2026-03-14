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
    @Published var categoryScores: [CategoryScore] = []
    @Published var suggestions: [ImprovementSuggestion] = []
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
            categoryScores = makeCategoryScores(summary: fetchedSummary, trend: fetchedTrend, audit: fetchedAudit)
            suggestions = makeSuggestions(summary: fetchedSummary, audit: fetchedAudit)
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

    private func makeCategoryScores(summary: DashboardSummary, trend: [QualityTrendItem], audit: AuditReport) -> [CategoryScore] {
        let total = max(summary.totalProjects, 1)
        let assetsRatio = Int((Double(summary.withAssets) / Double(total) * 100).rounded())
        let avgScore = Int((summary.avgQualityScore ?? 0).rounded())
        let unsentHealth = max(0, 100 - min(summary.unsentFeedbackCount * 15, 100))
        let auditScore: Int
        switch audit.overallHealth.lowercased() {
        case "good", "healthy":
            auditScore = 90
        case "critical", "error":
            auditScore = 45
        default:
            auditScore = 70
        }

        let trendScore = trend.last?.qualityScore ?? avgScore

        return [
            CategoryScore(id: UUID(), category: "品質", score: max(trendScore, 0), icon: "waveform.path.ecg"),
            CategoryScore(id: UUID(), category: "素材同期", score: assetsRatio, icon: "externaldrive.fill.badge.checkmark"),
            CategoryScore(id: UUID(), category: "FB運用", score: unsentHealth, icon: "bubble.left.and.exclamationmark.bubble.right.fill"),
            CategoryScore(id: UUID(), category: "監査", score: auditScore, icon: "checklist.checked")
        ]
    }

    private func makeSuggestions(summary: DashboardSummary, audit: AuditReport) -> [ImprovementSuggestion] {
        var items: [ImprovementSuggestion] = []

        if summary.unsentFeedbackCount > 0 {
            items.append(
                ImprovementSuggestion(
                    id: UUID(),
                    category: "フィードバック",
                    suggestion: "未送信FBが\(summary.unsentFeedbackCount)件あります。優先的に送信を完了してください。",
                    priority: .high
                )
            )
        }

        if let avg = summary.avgQualityScore, avg < 75 {
            items.append(
                ImprovementSuggestion(
                    id: UUID(),
                    category: "品質",
                    suggestion: "平均品質スコアが\(String(format: "%.1f", avg))です。ハイライト構成と音量基準を見直してください。",
                    priority: .medium
                )
            )
        }

        if !audit.qualityAnomalies.isEmpty {
            items.append(
                ImprovementSuggestion(
                    id: UUID(),
                    category: "監査",
                    suggestion: "品質異常が\(audit.qualityAnomalies.count)件検知されています。監査ログを確認して修正してください。",
                    priority: .high
                )
            )
        }

        if items.isEmpty {
            items.append(
                ImprovementSuggestion(
                    id: UUID(),
                    category: "運用",
                    suggestion: "重大な改善提案はありません。現在の運用品質を維持してください。",
                    priority: .low
                )
            )
        }

        return items
    }
}
