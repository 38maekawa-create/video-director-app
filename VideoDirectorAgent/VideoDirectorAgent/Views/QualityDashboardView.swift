import SwiftUI

// MARK: - 画面5: 品質ダッシュボード
struct QualityDashboardView: View {
    @ObservedObject var viewModel: DashboardViewModel

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 20) {
                // メインスコア
                mainScoreCard

                // スコア推移グラフ
                trendCard

                // カテゴリ別スコア
                categoryScoreCard

                // 改善提案
                suggestionsCard

                // アラート
                if !viewModel.alerts.isEmpty {
                    alertsCard
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 40)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("品質ダッシュボード")
                    .font(AppTheme.heroFont(17))
                    .foregroundStyle(.white)
                    .tracking(1)
            }
        }
    }

    // MARK: - メインスコア
    private var mainScoreCard: some View {
        VStack(spacing: 12) {
            Text("映像品質スコア")
                .font(AppTheme.labelFont(13))
                .foregroundStyle(AppTheme.textMuted)
                .tracking(2)

            Text("\(viewModel.latestScore)")
                .font(AppTheme.heroFont(72))
                .foregroundStyle(scoreColor(viewModel.latestScore))

            // 前回比
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

    // MARK: - スコア推移グラフ（折れ線風）
    private var trendCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "chart.xyaxis.line")
                    .foregroundStyle(AppTheme.accent)
                Text("スコア推移（過去10回）")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            // グラフ
            GeometryReader { geo in
                let width = geo.size.width
                let height: CGFloat = 120
                let points = viewModel.trend
                let maxScore = CGFloat(points.map(\.score).max() ?? 100)
                let minScore = CGFloat(points.map(\.score).min() ?? 0)
                let range = max(maxScore - minScore, 1)

                ZStack(alignment: .bottomLeading) {
                    // グリッド線
                    ForEach(0..<4) { i in
                        let y = height * CGFloat(i) / 3.0
                        Path { path in
                            path.move(to: CGPoint(x: 0, y: y))
                            path.addLine(to: CGPoint(x: width, y: y))
                        }
                        .stroke(AppTheme.textMuted.opacity(0.15), lineWidth: 1)
                    }

                    // 折れ線
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

                    // グラデーション塗り
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
                        path.addLine(to: CGPoint(x: width, y: height))
                        path.addLine(to: CGPoint(x: 0, y: height))
                        path.closeSubpath()
                    }
                    .fill(
                        LinearGradient(
                            colors: [AppTheme.accent.opacity(0.3), AppTheme.accent.opacity(0.0)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )

                    // ドット
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

            // ラベル
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

    // MARK: - カテゴリ別スコア
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

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12)
            ], spacing: 12) {
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

                        // プログレスバー
                        GeometryReader { geo in
                            ZStack(alignment: .leading) {
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(AppTheme.textMuted.opacity(0.2))
                                RoundedRectangle(cornerRadius: 3)
                                    .fill(scoreColor(cat.score))
                                    .frame(width: geo.size.width * CGFloat(cat.score) / 100.0)
                            }
                        }
                        .frame(height: 6)
                    }
                    .padding(16)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 改善提案
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
                    // 優先度
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

    // MARK: - アラート
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

    // MARK: - ヘルパー
    private func scoreColor(_ score: Int) -> Color {
        if score >= 85 { return AppTheme.statusComplete }
        if score >= 70 { return Color(hex: 0xF5A623) }
        return AppTheme.accent
    }
}
