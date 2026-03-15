import SwiftUI
import WebKit

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

// MARK: - トラッキング動画詳細画面（YouTube埋め込み再生）
struct TrackingVideoDetailView: View {
    let video: TrackedVideo
    @State private var linkCopied = false

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 16) {
                // YouTube埋め込みプレイヤー（16:9アスペクト比）
                GeometryReader { geo in
                    TrackingYouTubePlayerView(videoURL: video.url)
                        .frame(width: geo.size.width, height: geo.size.width * 9.0 / 16.0)
                }
                .aspectRatio(16.0 / 9.0, contentMode: .fit)
                .clipShape(RoundedRectangle(cornerRadius: 12))

                // タイトル + チャンネル
                VStack(alignment: .leading, spacing: 8) {
                    Text(video.title)
                        .font(.headline)
                        .foregroundStyle(.white)
                    Text(video.channelName ?? "チャンネル未設定")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 4)

                // アクションボタン（リンクコピー + Safari で開く）
                HStack(spacing: 12) {
                    Button {
                        UIPasteboard.general.string = video.url
                        linkCopied = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            linkCopied = false
                        }
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: linkCopied ? "checkmark" : "doc.on.doc")
                                .font(.subheadline)
                            Text(linkCopied ? "コピー済み" : "リンクをコピー")
                                .font(.subheadline)
                                .fontWeight(.medium)
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(linkCopied ? AppTheme.statusComplete : AppTheme.cardBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .overlay(
                            RoundedRectangle(cornerRadius: 10)
                                .strokeBorder(AppTheme.textMuted.opacity(0.3), lineWidth: 1)
                        )
                    }

                    if let url = URL(string: video.url) {
                        Link(destination: url) {
                            HStack(spacing: 6) {
                                Image(systemName: "arrow.up.right.square")
                                    .font(.subheadline)
                                Text("YouTubeで開く")
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                            }
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Color(hex: 0xFF0000).opacity(0.8))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                    }
                }

                // 分析ステータス
                HStack {
                    Text("分析ステータス")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                    Spacer()
                    Text(statusLabel(video.analysisStatus))
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(statusColor(video.analysisStatus))
                        .clipShape(Capsule())
                }
                .padding(16)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))

                // 分析結果
                if let analysis = video.analysisResult {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("分析結果")
                            .font(AppTheme.sectionFont(15))
                            .foregroundStyle(.white)

                        if let score = analysis.overallScore {
                            HStack {
                                Text("総合スコア")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textMuted)
                                Spacer()
                                Text(String(format: "%.0f", score))
                                    .font(.system(size: 28, weight: .heavy, design: .rounded))
                                    .foregroundStyle(scoreColor(Int(score)))
                            }
                        }

                        detailRow("構図", value: analysis.composition ?? "-")
                        detailRow("テンポ", value: analysis.tempo ?? "-")
                        detailRow("カット", value: analysis.cuttingStyle ?? "-")
                        detailRow("色彩", value: analysis.colorGrading ?? "-")

                        if let summary = analysis.summary {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("サマリー")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textMuted)
                                Text(summary)
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textSecondary)
                            }
                        }

                        if let techniques = analysis.keyTechniques, !techniques.isEmpty {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("抽出テクニック")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textMuted)
                                ForEach(techniques, id: \.self) { item in
                                    HStack(spacing: 6) {
                                        Circle()
                                            .fill(AppTheme.accent)
                                            .frame(width: 4, height: 4)
                                        Text(item)
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
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 40)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("トラッキング詳細")
                    .font(AppTheme.heroFont(17))
                    .foregroundStyle(.white)
                    .tracking(1)
            }
        }
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

    private func scoreColor(_ score: Int) -> Color {
        if score >= 85 { return AppTheme.statusComplete }
        if score >= 70 { return Color(hex: 0xF5A623) }
        return AppTheme.accent
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

// MARK: - トラッキング用YouTube埋め込みプレイヤー
struct TrackingYouTubePlayerView: UIViewRepresentable {
    let videoURL: String

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.scrollView.isScrollEnabled = false
        webView.isOpaque = false
        webView.backgroundColor = .clear
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        guard let videoId = extractVideoId(from: videoURL) else { return }
        let embedHTML = """
        <!DOCTYPE html>
        <html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
        <style>
            body { margin: 0; padding: 0; background: #000; }
            .container { position: relative; width: 100%; padding-bottom: 56.25%; }
            iframe { position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0; }
        </style>
        </head>
        <body>
        <div class="container">
            <iframe src="https://www.youtube.com/embed/\(videoId)?playsinline=1&rel=0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowfullscreen></iframe>
        </div>
        </body>
        </html>
        """
        webView.loadHTMLString(embedHTML, baseURL: URL(string: "https://www.youtube.com"))
    }

    private func extractVideoId(from url: String) -> String? {
        // https://www.youtube.com/watch?v=XXXX
        if let range = url.range(of: "v=") {
            let start = range.upperBound
            let remaining = String(url[start...])
            return String(remaining.prefix(while: { $0 != "&" && $0 != "#" }))
        }
        // https://youtu.be/XXXX
        if url.contains("youtu.be/") {
            if let range = url.range(of: "youtu.be/") {
                let start = range.upperBound
                let remaining = String(url[start...])
                return String(remaining.prefix(while: { $0 != "?" && $0 != "#" }))
            }
        }
        return nil
    }
}

// MARK: - トラッキング動画一覧
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
                NavigationLink(destination: TrackingVideoDetailView(video: video)) {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(video.title)
                                    .font(.headline)
                                    .foregroundStyle(.white)
                                    .multilineTextAlignment(.leading)
                                Text(video.channelName ?? "チャンネル未設定")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textMuted)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 6) {
                                Text(statusLabel(video.analysisStatus))
                                    .font(.caption2)
                                    .foregroundStyle(.white)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(statusColor(video.analysisStatus))
                                    .clipShape(Capsule())

                                // リンクコピーボタン（カード内）
                                Button {
                                    UIPasteboard.general.string = video.url
                                } label: {
                                    Image(systemName: "doc.on.doc")
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.textMuted)
                                        .padding(6)
                                        .background(AppTheme.cardBackgroundLight)
                                        .clipShape(Circle())
                                }
                                .buttonStyle(.plain)
                            }
                        }

                        if let analysis = video.analysisResult {
                            HStack(spacing: 16) {
                                if let score = analysis.overallScore {
                                    VStack(spacing: 2) {
                                        Text(String(format: "%.0f", score))
                                            .font(.system(size: 20, weight: .heavy, design: .rounded))
                                            .foregroundStyle(scoreColor(Int(score)))
                                        Text("総合")
                                            .font(.caption2)
                                            .foregroundStyle(AppTheme.textMuted)
                                    }
                                }
                                Spacer()
                                miniDetail("構図", value: analysis.composition)
                                miniDetail("テンポ", value: analysis.tempo)
                                miniDetail("カット", value: analysis.cuttingStyle)
                            }
                        }

                        // カード下部: タップで詳細へのヒント
                        HStack {
                            Image(systemName: "play.circle.fill")
                                .font(.caption)
                                .foregroundStyle(Color(hex: 0xFF0000))
                            Text("タップして動画を視聴")
                                .font(.caption2)
                                .foregroundStyle(AppTheme.textMuted)
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.caption2)
                                .foregroundStyle(AppTheme.textMuted)
                        }
                    }
                    .padding(16)
                    .background(AppTheme.cardBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .buttonStyle(.plain)
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

    // ミニ詳細（カード内の横並び表示用）
    private func miniDetail(_ title: String, value: String?) -> some View {
        VStack(spacing: 2) {
            Text(value ?? "-")
                .font(.caption2)
                .foregroundStyle(AppTheme.textSecondary)
                .lineLimit(1)
            Text(title)
                .font(.caption2)
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    private func scoreColor(_ score: Int) -> Color {
        if score >= 85 { return AppTheme.statusComplete }
        if score >= 70 { return Color(hex: 0xF5A623) }
        return AppTheme.accent
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
