import SwiftUI

struct QualityDashboardView: View {
    @StateObject private var editorViewModel = EditorManagementViewModel()
    @StateObject private var trackingViewModel = VideoTrackingViewModel()
    @ObservedObject var viewModel: DashboardViewModel
    @State private var showNotificationSettings = false

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 20) {
                Picker("表示切替", selection: $viewModel.selectedSection) {
                    ForEach(DashboardViewModel.Section.allCases) { section in
                        Text(section.rawValue).tag(section)
                    }
                }
                .pickerStyle(.segmented)

                if let message = viewModel.errorMessage {
                    infoBanner(message)
                }

                switch viewModel.selectedSection {
                case .quality:
                    qualitySection
                case .tracking:
                    VideoTrackingView(viewModel: trackingViewModel)
                case .editors:
                    EditorManagementView(viewModel: editorViewModel)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 40)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .task {
            await loadAll()
        }
        .refreshable {
            await loadAll(forceRefresh: true)
        }
        .sheet(isPresented: $showNotificationSettings) {
            NotificationSettingsView()
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("品質ダッシュボード")
                    .font(AppTheme.heroFont(17))
                    .foregroundStyle(.white)
                    .tracking(1)
            }
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showNotificationSettings = true
                } label: {
                    Image(systemName: "gearshape.fill")
                        .foregroundStyle(AppTheme.textSecondary)
                }
            }
        }
    }

    private var qualitySection: some View {
        VStack(spacing: 20) {
            if viewModel.isLoading {
                ProgressView()
                    .tint(AppTheme.accent)
                    .frame(maxWidth: .infinity)
            }

            mainScoreCard
            summaryCard
            trendCard
            categoryScoreCard
            suggestionsCard
            auditCard

            if !viewModel.alerts.isEmpty {
                alertsCard
            }
        }
    }

    private var mainScoreCard: some View {
        VStack(spacing: 12) {
            Text("映像品質スコア")
                .font(AppTheme.labelFont(13))
                .foregroundStyle(AppTheme.textMuted)
                .tracking(2)

            Text("\(viewModel.latestScore)")
                .font(AppTheme.heroFont(72))
                .foregroundStyle(scoreColor(viewModel.latestScore))

            HStack(spacing: 4) {
                Image(systemName: viewModel.scoreDelta >= 0 ? "arrow.up.right" : "arrow.down.right")
                    .font(.caption)
                Text("\(viewModel.scoreDelta >= 0 ? "+" : "")\(viewModel.scoreDelta) 前回比")
                    .font(.caption)
            }
            .foregroundStyle(viewModel.scoreDelta >= 0 ? AppTheme.statusComplete : AppTheme.accent)
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                (viewModel.scoreDelta >= 0 ? AppTheme.statusComplete : AppTheme.accent).opacity(0.15)
            )
            .clipShape(Capsule())
        }
        .padding(.vertical, 32)
        .frame(maxWidth: .infinity)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var summaryCard: some View {
        let summary = viewModel.summary ?? DashboardSummary(totalProjects: 0, withAssets: 0, avgQualityScore: nil, statusCounts: [:], recentFeedbacks: [], unsentFeedbackCount: 0)
        return VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "square.stack.3d.up.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("運用サマリー")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                metricCard("案件数", value: "\(summary.totalProjects)")
                metricCard("素材あり", value: "\(summary.withAssets)")
                metricCard("平均品質", value: summary.avgQualityScore.map { String(format: "%.1f", $0) } ?? "-")
                metricCard("未送信FB", value: "\(summary.unsentFeedbackCount)")
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("ステータス内訳")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                ForEach(summary.statusCounts.keys.sorted(), id: \.self) { key in
                    HStack {
                        Text(statusLabel(for: key))
                            .font(.caption)
                            .foregroundStyle(AppTheme.textSecondary)
                        Spacer()
                        Text("\(summary.statusCounts[key] ?? 0)")
                            .font(.caption)
                            .foregroundStyle(.white)
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var trendCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "chart.xyaxis.line")
                    .foregroundStyle(AppTheme.accent)
                Text("スコア推移")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            GeometryReader { geo in
                let width = geo.size.width
                let height: CGFloat = 120
                let points = viewModel.trend
                let maxScore = CGFloat(points.map(\.score).max() ?? 100)
                let minScore = CGFloat(points.map(\.score).min() ?? 0)
                let range = max(maxScore - minScore, 1)

                ZStack(alignment: .bottomLeading) {
                    ForEach(0..<4, id: \.self) { i in
                        let y = height * CGFloat(i) / 3.0
                        Path { path in
                            path.move(to: CGPoint(x: 0, y: y))
                            path.addLine(to: CGPoint(x: width, y: y))
                        }
                        .stroke(AppTheme.textMuted.opacity(0.15), lineWidth: 1)
                    }

                    Path { path in
                        for (index, point) in points.enumerated() {
                            let x = width * CGFloat(index) / CGFloat(max(points.count - 1, 1))
                            let y = height - (height * (CGFloat(point.score) - minScore) / range)
                            if index == 0 {
                                path.move(to: CGPoint(x: x, y: y))
                            } else {
                                path.addLine(to: CGPoint(x: x, y: y))
                            }
                        }
                    }
                    .stroke(AppTheme.accent, lineWidth: 2.5)

                    ForEach(Array(points.enumerated()), id: \.element.id) { index, point in
                        let x = width * CGFloat(index) / CGFloat(max(points.count - 1, 1))
                        let y = height - (height * (CGFloat(point.score) - minScore) / range)
                        Circle()
                            .fill(AppTheme.accent)
                            .frame(width: 8, height: 8)
                            .position(x: x, y: y)
                    }
                }
                .frame(height: height)
            }
            .frame(height: 120)

            HStack {
                ForEach(Array(viewModel.trend.enumerated()), id: \.element.id) { index, point in
                    if index % 2 == 0 || index == viewModel.trend.count - 1 {
                        Text(point.label)
                            .font(.caption2)
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    if index < viewModel.trend.count - 1 {
                        Spacer(minLength: 0)
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var categoryScoreCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "square.grid.2x2.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("カテゴリ別スコア")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(viewModel.categoryScores) { cat in
                    VStack(spacing: 10) {
                        Image(systemName: cat.icon)
                            .font(.system(size: 24))
                            .foregroundStyle(scoreColor(cat.score))
                        Text("\(cat.score)")
                            .font(.system(size: 28, weight: .heavy, design: .rounded))
                            .foregroundStyle(scoreColor(cat.score))
                        Text(cat.category)
                            .font(.caption)
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var suggestionsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "lightbulb.fill")
                    .foregroundStyle(Color(hex: 0xF5A623))
                Text("AIからの改善提案")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            ForEach(viewModel.suggestions) { suggestion in
                HStack(alignment: .top, spacing: 12) {
                    Text(suggestion.priority.rawValue)
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .frame(width: 24, height: 24)
                        .background(suggestion.priority.color)
                        .clipShape(Circle())

                    VStack(alignment: .leading, spacing: 4) {
                        Text(suggestion.category)
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundStyle(AppTheme.accent)
                        Text(suggestion.suggestion)
                            .font(.caption)
                            .foregroundStyle(AppTheme.textSecondary)
                    }
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var auditCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "checklist.unchecked")
                    .foregroundStyle(AppTheme.accent)
                Text("巡回監査")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            if let audit = viewModel.latestAudit {
                HStack {
                    Text(audit.pipelineStatus.uppercased())
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(healthColor(for: audit.overallHealth))
                        .clipShape(Capsule())
                    Spacer()
                    Text(audit.runAt)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                }

                Text("未処理動画 \(audit.pendingVideos)件")
                    .font(.subheadline)
                    .foregroundStyle(.white)

                ForEach(audit.qualityAnomalies, id: \.self) { anomaly in
                    labelRow(systemName: "exclamationmark.triangle.fill", text: anomaly, color: Color(hex: 0xF5A623))
                }
                ForEach(audit.staleProjects, id: \.self) { project in
                    labelRow(systemName: "clock.badge.exclamationmark", text: "滞留案件: \(project)", color: AppTheme.accent)
                }
            }

            if !viewModel.auditHistory.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("過去監査")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                    ForEach(viewModel.auditHistory.prefix(3)) { report in
                        HStack {
                            Text(report.runAt)
                                .font(.caption2)
                                .foregroundStyle(AppTheme.textSecondary)
                            Spacer()
                            Text(report.overallHealth)
                                .font(.caption2)
                                .foregroundStyle(healthColor(for: report.overallHealth))
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var alertsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("品質アラート")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            ForEach(viewModel.alerts) { alert in
                HStack(spacing: 10) {
                    Circle()
                        .fill(alert.level == "High" ? AppTheme.accent : Color(hex: 0xF5A623))
                        .frame(width: 8, height: 8)
                    Text(alert.message)
                        .font(.caption)
                        .foregroundStyle(AppTheme.textSecondary)
                }
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func scoreColor(_ score: Int) -> Color {
        if score >= 85 { return AppTheme.statusComplete }
        if score >= 70 { return Color(hex: 0xF5A623) }
        return AppTheme.accent
    }

    private func healthColor(for value: String) -> Color {
        switch value.lowercased() {
        case "good", "healthy":
            return AppTheme.statusComplete
        case "critical", "error":
            return AppTheme.accent
        default:
            return Color(hex: 0xF5A623)
        }
    }

    private func metricCard(_ title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)
            Text(value)
                .font(.system(size: 28, weight: .heavy, design: .rounded))
                .foregroundStyle(.white)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func labelRow(systemName: String, text: String, color: Color) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: systemName)
                .foregroundStyle(color)
            Text(text)
                .font(.caption)
                .foregroundStyle(AppTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func statusLabel(for key: String) -> String {
        switch key {
        case "directed": return "ディレクション済"
        case "editing": return "編集中"
        case "reviewPending": return "レビュー待ち"
        case "published": return "公開"
        default: return key
        }
    }

    private func infoBanner(_ message: String) -> some View {
        Text(message)
            .font(.caption)
            .foregroundStyle(AppTheme.textSecondary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(Color(hex: 0x2A1717))
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func loadAll(forceRefresh: Bool = false) async {
        if !forceRefresh, viewModel.isLoading { return }
        await viewModel.loadDashboard()
        await editorViewModel.loadEditors()
        await trackingViewModel.load()
    }
}
