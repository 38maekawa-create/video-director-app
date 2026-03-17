import SwiftUI
import WebKit

// MARK: - ビフォーアフター比較画面
/// 編集前素材(YouTube) vs 編集後動画(Vimeo) vs FB後再編集版(Vimeo)を比較するUI
struct BeforeAfterView: View {
    let projectId: String
    let projectTitle: String

    @Environment(\.dismiss) private var dismiss

    @State private var beforeAfterData: BeforeAfterResponse?
    @State private var transcriptData: TranscriptDiffResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var compareMode = 0  // 0: 素材 vs 編集後, 1: 編集後 vs FB後
    @State private var selectedSourceIndex = 0
    @State private var showTranscript = false

    var body: some View {
        NavigationView {
            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: 0) {
                    if isLoading {
                        loadingView
                    } else if let error = errorMessage {
                        errorView(error)
                    } else {
                        compareModeSelector
                        videoComparisonSection
                        diffHighlightsSection
                        transcriptDiffSection
                    }
                    Spacer(minLength: 40)
                }
            }
            .background(AppTheme.background.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "xmark")
                            Text("閉じる")
                        }
                        .font(.subheadline)
                        .foregroundStyle(.white)
                    }
                }
                ToolbarItem(placement: .principal) {
                    HStack(spacing: 6) {
                        Image(systemName: "rectangle.on.rectangle.angled")
                            .foregroundStyle(AppTheme.accent)
                        Text("ビフォーアフター")
                            .font(.headline)
                            .foregroundStyle(.white)
                    }
                }
            }
            .toolbarBackground(AppTheme.cardBackground, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .task {
            await loadData()
        }
    }

    // MARK: - サブビュー

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .tint(AppTheme.accent)
                .scaleEffect(1.2)
            Text("データを読み込み中...")
                .font(.subheadline)
                .foregroundStyle(AppTheme.textMuted)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }

    private func errorView(_ message: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(AppTheme.accent)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(AppTheme.textSecondary)
                .multilineTextAlignment(.center)
        }
        .padding(32)
    }

    // セグメントピッカー: 比較モード切替
    private var compareModeSelector: some View {
        VStack(spacing: 12) {
            Text(projectTitle)
                .font(AppTheme.heroFont(22))
                .foregroundStyle(.white)
                .padding(.top, 16)

            Picker("比較モード", selection: $compareMode) {
                Text("素材 vs 編集後").tag(0)
                Text("編集後 vs FB後").tag(1)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 16)
            .padding(.bottom, 8)
        }
    }

    // 上下2段レイアウトで動画比較
    private var videoComparisonSection: some View {
        GeometryReader { geo in
            let videoWidth = geo.size.width - 32 // padding 16*2
            let videoHeight = videoWidth * 9.0 / 16.0
            VStack(spacing: 2) {
                // 上段
                VStack(spacing: 4) {
                    upperVideoLabel
                    upperVideoPlayer
                        .frame(width: videoWidth, height: videoHeight)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .padding(.horizontal, 16)

                // 下段
                VStack(spacing: 4) {
                    lowerVideoLabel
                    lowerVideoPlayer
                        .frame(width: videoWidth, height: videoHeight)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                .padding(.horizontal, 16)
            }
        }
        // GeometryReaderの高さを明示（ラベル含む上下2段分）
        .frame(height: (UIScreen.main.bounds.width - 32) * 9.0 / 16.0 * 2 + 60)
        .padding(.vertical, 8)
    }

    // 上段ラベル
    private var upperVideoLabel: some View {
        HStack {
            Circle()
                .fill(Color(hex: 0x4A90D9))
                .frame(width: 8, height: 8)
            Text(compareMode == 0 ? "素材（YouTube）" : editedVideoLabel)
                .font(AppTheme.labelFont(13))
                .foregroundStyle(AppTheme.textSecondary)
            Spacer()
            // 素材動画が複数ある場合の選択
            if compareMode == 0, let data = beforeAfterData, data.sourceVideos.count > 1 {
                Picker("素材", selection: $selectedSourceIndex) {
                    ForEach(0..<data.sourceVideos.count, id: \.self) { i in
                        Text("素材\(i + 1)").tag(i)
                    }
                }
                .pickerStyle(.menu)
                .tint(AppTheme.accent)
            }
        }
    }

    // 下段ラベル
    private var lowerVideoLabel: some View {
        HStack {
            Circle()
                .fill(AppTheme.accent)
                .frame(width: 8, height: 8)
            Text(compareMode == 0 ? editedVideoLabel : fbRevisedVideoLabel)
                .font(AppTheme.labelFont(13))
                .foregroundStyle(AppTheme.textSecondary)
            Spacer()
        }
    }

    /// 編集後動画のラベル（バージョン名を動的表示）
    private var editedVideoLabel: String {
        if let label = beforeAfterData?.editedVideo?.versionLabel {
            return "編集後（\(label)）（Vimeo）"
        }
        return "編集後（Vimeo）"
    }

    /// FB後動画のラベル（バージョン名を動的表示）
    private var fbRevisedVideoLabel: String {
        if let label = beforeAfterData?.fbRevisedVideo?.versionLabel {
            return "FB後（\(label)）（Vimeo）"
        }
        return "FB後（Vimeo）"
    }

    // 上段プレイヤー
    private var upperVideoPlayer: some View {
        Group {
            if compareMode == 0 {
                // 素材 YouTube
                if let data = beforeAfterData,
                   selectedSourceIndex < data.sourceVideos.count {
                    let video = data.sourceVideos[selectedSourceIndex]
                    IframePlayerView(embedURL: video.embedUrl)
                } else {
                    placeholderView("素材動画が未登録です")
                }
            } else {
                // 編集後 v1 Vimeo
                if let edited = beforeAfterData?.editedVideo,
                   let embedUrl = edited.embedUrl {
                    IframePlayerView(embedURL: embedUrl)
                } else {
                    placeholderView("編集後動画が未登録です")
                }
            }
        }
    }

    // 下段プレイヤー
    private var lowerVideoPlayer: some View {
        Group {
            if compareMode == 0 {
                // 編集後 Vimeo
                if let edited = beforeAfterData?.editedVideo,
                   let embedUrl = edited.embedUrl {
                    IframePlayerView(embedURL: embedUrl)
                } else {
                    placeholderView("編集後動画が未登録です")
                }
            } else {
                // FB後 v2
                if let revised = beforeAfterData?.fbRevisedVideo,
                   let embedUrl = revised.embedUrl {
                    IframePlayerView(embedURL: embedUrl)
                } else {
                    placeholderView("FB後再編集版はまだありません")
                }
            }
        }
    }

    private func placeholderView(_ message: String) -> some View {
        ZStack {
            AppTheme.cardBackground
            VStack(spacing: 8) {
                Image(systemName: "film")
                    .font(.system(size: 32))
                    .foregroundStyle(AppTheme.textMuted)
                Text(message)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
    }

    // 差分ハイライトリスト（FBタイムスタンプ一覧）
    private var diffHighlightsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let data = beforeAfterData, !data.diffHighlights.isEmpty {
                HStack {
                    Image(systemName: "clock.badge.exclamationmark")
                        .foregroundStyle(AppTheme.accent)
                    Text("FBタイムスタンプ")
                        .font(AppTheme.sectionFont(16))
                        .foregroundStyle(.white)
                    Spacer()
                    Text("\(data.diffHighlights.count)件")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)

                ForEach(data.diffHighlights) { highlight in
                    HStack(alignment: .top, spacing: 10) {
                        Text(highlight.timestamp)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(AppTheme.accent)
                            .frame(width: 60, alignment: .leading)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(highlight.text)
                                .font(.caption)
                                .foregroundStyle(AppTheme.textSecondary)
                                .lineLimit(2)
                            if let cat = highlight.category, !cat.isEmpty {
                                Text(cat)
                                    .font(.caption2)
                                    .foregroundStyle(AppTheme.textMuted)
                            }
                        }

                        Spacer()

                        if let priority = highlight.priority {
                            priorityBadge(priority)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 6)
                    .background(AppTheme.cardBackground)
                }
            }
        }
    }

    private func priorityBadge(_ priority: String) -> some View {
        Text(priority)
            .font(.system(size: 9, weight: .bold))
            .foregroundStyle(.white)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(
                priority == "high" ? AppTheme.accent :
                priority == "medium" ? Color(hex: 0xF5A623) :
                AppTheme.textMuted
            )
            .clipShape(Capsule())
    }

    // 文字起こしdiff比較セクション
    private var transcriptDiffSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Button {
                withAnimation { showTranscript.toggle() }
            } label: {
                HStack {
                    Image(systemName: "doc.text")
                        .foregroundStyle(AppTheme.accent)
                    Text("文字起こし比較")
                        .font(AppTheme.sectionFont(16))
                        .foregroundStyle(.white)
                    Spacer()

                    if let data = transcriptData, data.status == "ok" {
                        transcriptStatsBadges(data)
                    }

                    Image(systemName: showTranscript ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)
            }

            if showTranscript {
                if let data = transcriptData {
                    if data.status == "ok" {
                        transcriptLegend
                        transcriptSegmentsView(data.segments)
                    } else {
                        Text(data.message ?? "文字起こしデータがありません")
                            .font(.caption)
                            .foregroundStyle(AppTheme.textMuted)
                            .padding(.horizontal, 16)
                    }
                } else {
                    Text("文字起こしデータを読み込み中...")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                        .padding(.horizontal, 16)
                }
            }
        }
    }

    private func transcriptStatsBadges(_ data: TranscriptDiffResponse) -> some View {
        HStack(spacing: 6) {
            if let hl = data.highlightCount, hl > 0 {
                Text("HL \(hl)")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(AppTheme.accent)
                    .clipShape(Capsule())
            }
            if let pl = data.punchlineCount, pl > 0 {
                Text("PL \(pl)")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(.black)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(Color(hex: 0xFFD700))
                    .clipShape(Capsule())
            }
        }
    }

    // 凡例
    private var transcriptLegend: some View {
        HStack(spacing: 16) {
            legendItem(color: AppTheme.textSecondary, label: "通常")
            legendItem(color: Color(hex: 0xFF6B35), label: "カット")
            legendItem(color: AppTheme.accent, label: "FB修正")
            legendItem(color: Color(hex: 0xFFD700), label: "パンチライン")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
    }

    private func legendItem(color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            RoundedRectangle(cornerRadius: 2)
                .fill(color)
                .frame(width: 12, height: 12)
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    // 文字起こしセグメント表示（色分け）
    private func transcriptSegmentsView(_ segments: [TranscriptSegment]) -> some View {
        LazyVStack(alignment: .leading, spacing: 1) {
            ForEach(segments) { segment in
                HStack(alignment: .top, spacing: 8) {
                    // 行番号
                    Text("\(segment.lineNumber)")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(AppTheme.textMuted.opacity(0.5))
                        .frame(width: 30, alignment: .trailing)

                    // テキスト本文
                    HStack(spacing: 4) {
                        if segment.status == "unused" {
                            Text("CUT")
                                .font(.system(size: 8, weight: .bold, design: .monospaced))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 1)
                                .background(Color(hex: 0xFF6B35))
                                .clipShape(RoundedRectangle(cornerRadius: 3))
                        }
                        Text(segment.text)
                            .font(.system(size: 12))
                            .foregroundStyle(textColor(for: segment))
                            .underline(segment.status == "highlight", color: AppTheme.accent)
                    }
                    .padding(.vertical, 2)
                    .padding(.horizontal, segment.status == "unused" ? 4 : 0)
                    .background(
                        segment.status == "punchline"
                            ? Color(hex: 0xFFD700).opacity(0.15)
                            : segment.status == "unused"
                                ? Color(hex: 0xFF6B35).opacity(0.12)
                                : Color.clear
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 4))
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 2)
            }
        }
        .padding(.bottom, 16)
    }

    private func textColor(for segment: TranscriptSegment) -> Color {
        switch segment.status {
        case "punchline":
            return Color(hex: 0xFFD700)
        case "highlight":
            return AppTheme.textSecondary
        case "unused":
            return Color(hex: 0xFF6B35)
        default:
            return .white
        }
    }

    // MARK: - データ読み込み

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }

        do {
            async let ba = APIClient.shared.fetchBeforeAfter(projectId: projectId)
            async let td = APIClient.shared.fetchTranscriptDiff(projectId: projectId)

            let (baResult, tdResult) = try await (ba, td)
            beforeAfterData = baResult
            transcriptData = tdResult
        } catch {
            errorMessage = "データの取得に失敗しました: \(error.localizedDescription)"
        }
    }
}

// MARK: - 汎用 iframe プレイヤー（YouTube / Vimeo 両対応）
struct IframePlayerView: UIViewRepresentable {
    let embedURL: String

    /// Vimeo embed URLかどうか判定
    private var isVimeo: Bool { embedURL.contains("player.vimeo.com") }

    /// VimeoのvideoIDとプライバシーハッシュを抽出
    private var vimeoVideoId: String? {
        guard isVimeo else { return nil }
        // https://player.vimeo.com/video/12345?h=abc → "12345"
        guard let url = URL(string: embedURL) else { return nil }
        let parts = url.pathComponents.filter { $0 != "/" }
        if parts.first == "video", parts.count >= 2 {
            return parts[1]
        }
        return nil
    }
    private var vimeoHash: String? {
        guard isVimeo else { return nil }
        guard let components = URLComponents(string: embedURL) else { return nil }
        return components.queryItems?.first(where: { $0.name == "h" })?.value
    }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.scrollView.isScrollEnabled = false
        webView.isOpaque = false
        webView.backgroundColor = .black
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        // 既にロード済みならスキップ
        if webView.url != nil { return }

        if isVimeo, let videoId = vimeoVideoId {
            // Vimeo: Player SDK HTML方式（直接URLリクエストだと403になるため）
            let hashParam = vimeoHash.map { "?h=\($0)" } ?? ""
            let vimeoEmbedUrl = "https://player.vimeo.com/video/\(videoId)\(hashParam)"
            let html = """
            <!DOCTYPE html><html><head>
            <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
            <style>
              *{margin:0;padding:0;box-sizing:border-box}
              html,body{width:100%;height:100%;background:#000;overflow:hidden}
              #player-container{width:100%;height:100%}
              #player-container>div{width:100%!important;height:100%!important}
              iframe{width:100%;height:100%;border:none;display:block}
            </style></head><body>
            <div id="player-container"><div id="player"></div></div>
            <script src="https://player.vimeo.com/api/player.js"></script>
            <script>
              new Vimeo.Player('player',{url:'\(vimeoEmbedUrl)',responsive:true,title:false,byline:false,portrait:false,color:'1694F5'});
            </script></body></html>
            """
            webView.loadHTMLString(html, baseURL: URL(string: "https://video-director.app/"))
        } else {
            // YouTube: 従来の直接URLリクエスト方式
            if let url = URL(string: embedURL) {
                var request = URLRequest(url: url)
                request.setValue("https://video-director.app/", forHTTPHeaderField: "Referer")
                webView.load(request)
            }
        }
    }
}
