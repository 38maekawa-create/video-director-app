import SwiftUI

// 簡易FlowLayout（タグ表示用）
struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var lineHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > maxWidth && currentX > 0 {
                currentY += lineHeight + spacing
                currentX = 0
                lineHeight = 0
            }
            currentX += size.width + spacing
            lineHeight = max(lineHeight, size.height)
        }

        return CGSize(width: maxWidth, height: currentY + lineHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var currentX: CGFloat = bounds.minX
        var currentY: CGFloat = bounds.minY
        var lineHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > bounds.maxX && currentX > bounds.minX {
                currentY += lineHeight + spacing
                currentX = bounds.minX
                lineHeight = 0
            }
            subview.place(at: CGPoint(x: currentX, y: currentY), proposal: .unspecified)
            currentX += size.width + spacing
            lineHeight = max(lineHeight, size.height)
        }
    }
}

struct VideoTrackingView: View {
    @ObservedObject var viewModel: VideoTrackingViewModel

    var body: some View {
        VStack(spacing: 16) {
            if let message = viewModel.errorMessage {
                Text(message)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textSecondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(Color(hex: 0x2A1717))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }

            ForEach(viewModel.videos) { video in
                VStack(alignment: .leading, spacing: 12) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(video.title)
                                .font(.headline)
                                .foregroundStyle(.white)
                            Text(video.channelName ?? "チャンネル未設定")
                                .font(.caption)
                                .foregroundStyle(AppTheme.textMuted)
                        }
                        Spacer()
                        Text(statusLabel(video.analysisStatus))
                            .font(.caption2)
                            .foregroundStyle(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(statusColor(video.analysisStatus))
                            .clipShape(Capsule())
                    }

                    if let analysis = video.analysisResult {
                        detailRow("総合", value: analysis.overallScore.map { String(format: "%.0f", $0) } ?? "-")
                        detailRow("構図", value: analysis.composition ?? "-")
                        detailRow("テンポ", value: analysis.tempo ?? "-")
                        detailRow("カット", value: analysis.cuttingStyle ?? "-")
                        detailRow("色彩", value: analysis.colorGrading ?? "-")

                        if let techniques = analysis.keyTechniques, !techniques.isEmpty {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("抽出テクニック")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textMuted)
                                ForEach(techniques, id: \.self) { item in
                                    Text("・\(item)")
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.textSecondary)
                                }
                            }
                        }
                    }
                }
                .padding(16)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            // 学習状況サマリーセクション
            if let summary = viewModel.learningSummary {
                learningSummarySection(summary)
            }

            VStack(alignment: .leading, spacing: 12) {
                Text("学習済みインサイト")
                    .font(AppTheme.sectionFont(15))
                    .foregroundStyle(.white)

                if viewModel.insights.isEmpty {
                    Text("学習済みインサイトはまだありません")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                } else {
                    ForEach(viewModel.insights) { insight in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(insight.category)
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.accent)
                                Spacer()
                                Text("信頼度 \(Int(insight.confidence * 100))%")
                                    .font(.caption2)
                                    .foregroundStyle(AppTheme.textMuted)
                            }
                            Text(insight.pattern)
                                .font(.caption)
                                .foregroundStyle(AppTheme.textSecondary)
                            Text("参照映像 \(insight.sourceCount)件")
                                .font(.caption2)
                                .foregroundStyle(AppTheme.textMuted)
                        }
                        .padding(12)
                        .background(AppTheme.cardBackgroundLight)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                }
            }
            .padding(16)
            .background(AppTheme.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }

    // 学習状況サマリーカード
    private func learningSummarySection(_ summary: LearningSummary) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("学習状況")
                .font(AppTheme.sectionFont(15))
                .foregroundStyle(.white)

            HStack(spacing: 16) {
                // FB学習
                summaryStatCard(
                    title: "FB学習",
                    icon: "text.bubble.fill",
                    patterns: summary.feedbackLearning?.totalPatterns ?? 0,
                    rules: summary.feedbackLearning?.activeRules ?? 0
                )
                // 映像学習
                summaryStatCard(
                    title: "映像学習",
                    icon: "film.fill",
                    patterns: summary.videoLearning?.totalPatterns ?? 0,
                    rules: summary.videoLearning?.activeRules ?? 0,
                    videos: summary.videoLearning?.totalSourceVideos
                )
            }

            // カテゴリ分布（映像学習の場合）
            if let dist = summary.videoLearning?.categoryDistribution, !dist.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("カテゴリ分布")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                    FlowLayout(spacing: 6) {
                        ForEach(dist.sorted(by: { $0.value > $1.value }), id: \.key) { key, value in
                            Text("\(categoryLabel(key)) \(value)")
                                .font(.caption2)
                                .foregroundStyle(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(categoryColor(key))
                                .clipShape(Capsule())
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func summaryStatCard(title: String, icon: String, patterns: Int, rules: Int, videos: Int? = nil) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundStyle(AppTheme.accent)
                Text(title)
                    .font(AppTheme.labelFont(12))
                    .foregroundStyle(.white)
            }
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(patterns)")
                        .font(AppTheme.heroFont(20))
                        .foregroundStyle(.white)
                    Text("パターン")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(rules)")
                        .font(AppTheme.heroFont(20))
                        .foregroundStyle(AppTheme.statusComplete)
                    Text("ルール")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                }
                if let videos = videos {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(videos)")
                            .font(AppTheme.heroFont(20))
                            .foregroundStyle(Color(hex: 0x4A90D9))
                        Text("映像")
                            .font(.caption2)
                            .foregroundStyle(AppTheme.textMuted)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func categoryLabel(_ key: String) -> String {
        let labels: [String: String] = [
            "cutting": "カット",
            "color": "色彩",
            "tempo": "テンポ",
            "technique": "テクニック",
            "composition": "構図",
            "telop": "テロップ",
            "bgm": "BGM",
            "camera": "カメラ",
            "general": "全般",
        ]
        return labels[key] ?? key
    }

    private func categoryColor(_ key: String) -> Color {
        let colors: [String: Color] = [
            "cutting": Color(hex: 0xE50914),
            "color": Color(hex: 0xF5A623),
            "tempo": Color(hex: 0x4A90D9),
            "technique": AppTheme.statusComplete,
            "composition": Color(hex: 0x9B59B6),
        ]
        return colors[key] ?? AppTheme.textMuted
    }

    private func detailRow(_ title: String, value: String) -> some View {
        HStack(alignment: .top) {
            Text(title)
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)
                .frame(width: 48, alignment: .leading)
            Text(value)
                .font(.caption)
                .foregroundStyle(AppTheme.textSecondary)
            Spacer()
        }
    }

    private func statusLabel(_ status: String) -> String {
        switch status {
        case "completed": return "分析完了"
        case "analyzing": return "分析中"
        default: return "待機中"
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "completed": return AppTheme.statusComplete
        case "analyzing": return Color(hex: 0xF5A623)
        default: return AppTheme.textMuted
        }
    }
}
