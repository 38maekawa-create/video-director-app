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
    @Published var qualityStats: QualityStats?
    @Published var isLoading = false
    @Published var errorMessage: String?
    private var hasLoaded = false

    var latestScore: Int {
        trend.last?.score ?? 0
    }

    var scoreDelta: Int {
        guard trend.count >= 2 else { return 0 }
        return trend[trend.count - 1].score - trend[trend.count - 2].score
    }

    func loadDashboardIfNeeded() async {
        if hasLoaded { return }
        await loadDashboard()
    }

    func loadDashboard() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        var errors: [String] = []

        // 各APIを個別に取得（1つの失敗が他に影響しない）
        var fetchedSummary: DashboardSummary?
        var fetchedTrend: [QualityTrendItem] = []
        var fetchedAudit: AuditReport?
        var fetchedAuditHistory: [AuditReport] = []
        var fetchedQualityStats: QualityStats?

        do {
            fetchedSummary = try await APIClient.shared.fetchDashboardSummary()
        } catch {
            errors.append("サマリー")
        }

        do {
            fetchedTrend = try await APIClient.shared.fetchQualityTrend()
        } catch {
            errors.append("トレンド")
        }

        do {
            fetchedAudit = try await APIClient.shared.fetchLatestAudit()
        } catch {
            errors.append("監査")
        }

        do {
            fetchedAuditHistory = try await APIClient.shared.fetchAuditHistory()
        } catch {
            errors.append("監査履歴")
        }

        do {
            fetchedQualityStats = try await APIClient.shared.fetchQualityStats()
        } catch {
            errors.append("品質統計")
        }

        // 取得成功したデータのみ更新（既存データを保持）
        if let s = fetchedSummary {
            summary = s
        }
        if !fetchedTrend.isEmpty {
            trend = fetchedTrend.enumerated().map { index, item in
                QualityTrendPoint(
                    id: UUID(),
                    label: shortLabel(for: item, index: index),
                    score: item.qualityScore ?? 0
                )
            }
        }
        if let a = fetchedAudit {
            latestAudit = a
        }
        if !fetchedAuditHistory.isEmpty {
            auditHistory = fetchedAuditHistory
        }
        if let qs = fetchedQualityStats {
            qualityStats = qs
        }

        // カテゴリスコア等の派生データを更新
        if let s = summary, let a = latestAudit {
            categoryScores = makeCategoryScores(summary: s, trend: fetchedTrend.isEmpty ? [] : fetchedTrend, audit: a)
            suggestions = makeSuggestions(summary: s, audit: a)
            alerts = makeAlerts(summary: s, audit: a)
        }

        if errors.isEmpty {
            hasLoaded = true
        } else if !hasLoaded {
            // 初回ロード失敗時のみエラー表示（データがあればrefresh失敗は無視）
            errorMessage = "\(errors.joined(separator: "・"))の取得に失敗しました"
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
