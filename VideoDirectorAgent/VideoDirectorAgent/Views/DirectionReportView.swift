import SwiftUI
import WebKit

// MARK: - YouTube動画IDの抽出ユーティリティ
private func extractYouTubeVideoId(from url: String) -> String? {
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

// MARK: - YouTube埋め込みプレイヤー（エラー時フォールバック付き）
struct YouTubePlayerView: View {
    let videoURL: String

    @State private var embedError = false

    private var videoId: String? {
        extractYouTubeVideoId(from: videoURL)
    }

    var body: some View {
        if embedError, let vid = videoId {
            // フォールバック: サムネイル + 「YouTubeで開く」ボタン
            YouTubeFallbackView(videoId: vid)
        } else {
            YouTubeWebPlayerView(videoURL: videoURL, onEmbedError: {
                embedError = true
            })
        }
    }
}

// MARK: - フォールバック表示（サムネ + YouTubeで開くボタン）
struct YouTubeFallbackView: View {
    let videoId: String

    var body: some View {
        ZStack {
            // サムネイル画像（16:9）
            AsyncImage(url: URL(string: "https://img.youtube.com/vi/\(videoId)/hqdefault.jpg")) { phase in
                switch phase {
                case .success(let image):
                    image
                        .resizable()
                        .aspectRatio(16.0 / 9.0, contentMode: .fit)
                case .failure:
                    Color.black
                        .aspectRatio(16.0 / 9.0, contentMode: .fit)
                case .empty:
                    Color.black
                        .aspectRatio(16.0 / 9.0, contentMode: .fit)
                        .overlay(ProgressView().tint(.white))
                @unknown default:
                    Color.black
                        .aspectRatio(16.0 / 9.0, contentMode: .fit)
                }
            }

            // オーバーレイ: エラーメッセージ + ボタン
            VStack(spacing: 12) {
                Spacer()

                // エラーメッセージ
                Text("埋め込み再生が制限されています")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(Color.black.opacity(0.7))
                    .clipShape(RoundedRectangle(cornerRadius: 6))

                // YouTubeで開くボタン
                Link(destination: URL(string: "https://www.youtube.com/watch?v=\(videoId)")!) {
                    HStack(spacing: 8) {
                        Image(systemName: "play.rectangle.fill")
                            .font(.system(size: 16, weight: .bold))
                        Text("YouTubeで開く")
                            .font(.subheadline)
                            .fontWeight(.bold)
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(Color(red: 1.0, green: 0.0, blue: 0.0))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                Spacer()
                    .frame(height: 16)
            }
        }
    }
}

// MARK: - WKWebViewベースのYouTubeプレーヤー（IFrame Player API + エラー検出）
struct YouTubeWebPlayerView: UIViewRepresentable {
    let videoURL: String
    var onEmbedError: (() -> Void)?

    func makeCoordinator() -> Coordinator {
        Coordinator(onEmbedError: onEmbedError)
    }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        // JavaScript→Swift通信用のメッセージハンドラを登録
        config.userContentController.add(context.coordinator, name: "ytError")
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.scrollView.isScrollEnabled = false
        webView.isOpaque = false
        webView.backgroundColor = .clear
        webView.navigationDelegate = context.coordinator
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        guard let videoId = extractYouTubeVideoId(from: videoURL) else { return }
        // YouTubeは外部サイトのRefererが必須（youtube.com自身やRefererなしだとエラー153）
        // PLAYABILITY_ERROR_CODE_EMBEDDER_IDENTITY_MISSING_REFERRER 対策
        let embedURLString = "https://www.youtube.com/embed/\(videoId)?playsinline=1&rel=0"
        if let url = URL(string: embedURLString) {
            if webView.url?.absoluteString != embedURLString {
                var request = URLRequest(url: url)
                request.setValue("https://video-director.app/", forHTTPHeaderField: "Referer")
                webView.load(request)
            }
        }
    }

    // MARK: - Coordinator（WKScriptMessageHandler + WKNavigationDelegate）
    class Coordinator: NSObject, WKScriptMessageHandler, WKNavigationDelegate {
        var onEmbedError: (() -> Void)?

        init(onEmbedError: (() -> Void)?) {
            self.onEmbedError = onEmbedError
        }

        func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
            if message.name == "ytError" {
                DispatchQueue.main.async { [weak self] in
                    self?.onEmbedError?()
                }
            }
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            DispatchQueue.main.async { [weak self] in
                self?.onEmbedError?()
            }
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            DispatchQueue.main.async { [weak self] in
                self?.onEmbedError?()
            }
        }
    }
}

// MARK: - 画面2: ディレクションレポート詳細
struct DirectionReportView: View {
    let project: VideoProject
    @State private var selectedTab = 0
    @State private var expandedSections: Set<UUID> = []
    @State private var feedbacks: [FeedbackItem] = []
    @State private var isFeedbackLoading = false
    @State private var showVoiceFeedback = false
    @State private var showKnowledgePage = false
    @State private var showBeforeAfter = false

    private let tabTitles = ["概要", "ディレクション", "YouTube素材", "素材", "FB・評価", "ナレッジ", "レビュー"]

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 0) {
                headerSection
                tabSelector
                sectionContent
                Spacer(minLength: 100)
            }
        }
        .background(AppTheme.background.ignoresSafeArea())
        .overlay(alignment: .bottom) {
            bottomActionBar
        }
        .navigationBarTitleDisplayMode(.inline)
        .fullScreenCover(isPresented: $showVoiceFeedback) {
            VoiceFeedbackView(projectId: project.id)
        }
        .fullScreenCover(isPresented: $showBeforeAfter) {
            BeforeAfterView(projectId: project.id, projectTitle: project.title)
        }
        .sheet(isPresented: $showKnowledgePage) {
            if let urlString = project.knowledgePageUrl,
               let url = URL(string: urlString) {
                KnowledgePageWebView(url: url, projectId: project.id)
            }
        }
    }

    private var headerSection: some View {
        VStack(spacing: 0) {
            ZStack(alignment: .bottomLeading) {
                ZStack {
                    LinearGradient(
                        colors: [project.status.color.opacity(0.3), AppTheme.cardBackground],
                        startPoint: .topTrailing,
                        endPoint: .bottomLeading
                    )
                    Image(systemName: project.thumbnailSymbol)
                        .font(.system(size: 60))
                        .foregroundStyle(.white.opacity(0.1))
                }
                .frame(height: 180)

                LinearGradient(
                    colors: [.clear, AppTheme.background],
                    startPoint: .center,
                    endPoint: .bottom
                )
                .frame(height: 100)
                .frame(maxHeight: .infinity, alignment: .bottom)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text(project.guestName)
                    .font(AppTheme.heroFont(30))
                    .foregroundStyle(.white)

                Text(project.title)
                    .font(AppTheme.titleFont(20))
                    .foregroundStyle(AppTheme.textSecondary)
                    .tracking(1)

                HStack(spacing: 16) {
                    if let age = project.guestAge {
                        Label("\(age)歳", systemImage: "person.fill")
                    }
                    if let occupation = project.guestOccupation {
                        Label(occupation, systemImage: "briefcase.fill")
                    }
                    Label(project.shootDate, systemImage: "calendar")
                }
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)

                HStack(spacing: 12) {
                    Button {
                        showBeforeAfter = true
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "rectangle.on.rectangle.angled")
                            Text("ビフォーアフター")
                        }
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(AppTheme.cardBackground)
                        .clipShape(Capsule())
                        .overlay(
                            Capsule()
                                .strokeBorder(Color(hex: 0xF5A623).opacity(0.5), lineWidth: 1)
                        )
                    }

                    if project.knowledgePageUrl != nil {
                        Button {
                            showKnowledgePage = true
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "book.fill")
                                Text("閲覧ページ")
                            }
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundStyle(.white)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(AppTheme.cardBackground)
                            .clipShape(Capsule())
                            .overlay(
                                Capsule()
                                    .strokeBorder(AppTheme.accent.opacity(0.5), lineWidth: 1)
                            )
                        }
                    }

                    Spacer()

                    if let score = project.qualityScore {
                        VStack(spacing: 2) {
                            Text("\(score)")
                                .font(.system(size: 24, weight: .heavy))
                                .foregroundStyle(scoreColor(score))
                            Text("品質スコア")
                                .font(.caption2)
                                .foregroundStyle(AppTheme.textMuted)
                        }
                    }
                }
                .padding(.top, 4)
            }
            .padding(.horizontal, 20)
        }
    }

    private var tabSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 0) {
                ForEach(0..<tabTitles.count, id: \.self) { index in
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            selectedTab = index
                        }
                    } label: {
                        VStack(spacing: 8) {
                            Text(tabTitles[index])
                                .font(.subheadline)
                                .fontWeight(selectedTab == index ? .bold : .medium)
                                .foregroundStyle(selectedTab == index ? .white : AppTheme.textMuted)

                            Rectangle()
                                .fill(selectedTab == index ? AppTheme.accent : .clear)
                                .frame(height: 2)
                        }
                        .frame(width: 104)
                    }
                }
            }
            .padding(.horizontal, 20)
        }
        .padding(.top, 20)
    }

    private var sectionContent: some View {
        VStack(spacing: 12) {
            switch selectedTab {
            case 0:
                overviewSection
            case 1:
                directionReportSection
            case 2:
                YouTubeAssetsView(projectId: project.id)
            case 3:
                sourceVideoSection
            case 4:
                feedbackListSection
            case 5:
                knowledgeDetailSection
            case 6:
                VimeoReviewTabView(projectId: project.id, editedVideoURL: project.editedVideoURL)
            default:
                EmptyView()
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 16)
    }

    private func expandableSection(_ section: ReportSection) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    if expandedSections.contains(section.id) {
                        expandedSections.remove(section.id)
                    } else {
                        expandedSections.insert(section.id)
                    }
                }
            } label: {
                HStack {
                    Image(systemName: section.icon)
                        .foregroundStyle(AppTheme.accent)
                    Text(section.title)
                        .font(.headline)
                        .foregroundStyle(.white)
                    Spacer()
                    Image(systemName: expandedSections.contains(section.id) ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
                .padding(16)
            }

            if !expandedSections.contains(section.id) {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(section.items, id: \.self) { item in
                        HStack(alignment: .top, spacing: 10) {
                            Circle()
                                .fill(AppTheme.accent)
                                .frame(width: 6, height: 6)
                                .padding(.top, 6)
                            Text(item)
                                .font(.subheadline)
                                .foregroundStyle(AppTheme.textSecondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 16)
            }
        }
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var overviewSection: some View {
        VStack(spacing: 12) {
            overviewCard(
                title: "プロジェクト概要",
                icon: "doc.text.magnifyingglass",
                items: [
                    "ゲスト: \(project.guestName)",
                    project.guestAge.map { "年齢: \($0)歳" } ?? "年齢: 未設定",
                    project.guestOccupation.map { "職業: \($0)" } ?? "職業: 未設定",
                    "撮影日: \(project.shootDate)",
                    "状態: \(project.status.label)",
                    "品質スコア: \(project.qualityScore.map(String.init) ?? "未算出")"
                ]
            )
            overviewCard(
                title: "進行サマリー",
                icon: "chart.bar.xaxis",
                items: [
                    "未レビュー: \(project.unreviewedCount)件",
                    "未送信FB: \(project.hasUnsentFeedback ? "あり" : "なし")"
                ]
            )

            // 手修正ツール導線
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: "wrench.and.screwdriver.fill")
                        .foregroundStyle(AppTheme.accent)
                    Text("手修正ツール")
                        .font(AppTheme.sectionFont(18))
                        .foregroundStyle(.white)
                }

                NavigationLink {
                    TitleDescriptionEditView(
                        projectId: project.id,
                        projectTitle: project.title
                    )
                } label: {
                    editToolRow(icon: "character.cursor.ibeam", title: "タイトル・概要欄を編集")
                }

                NavigationLink {
                    ThumbnailEditView(
                        projectId: project.id,
                        projectTitle: project.title
                    )
                } label: {
                    editToolRow(icon: "photo.artframe", title: "サムネ指示書を編集")
                }

                NavigationLink {
                    DirectionEditView(
                        projectId: project.id,
                        projectTitle: project.title
                    )
                } label: {
                    editToolRow(icon: "pencil.and.outline", title: "ディレクションを編集")
                }
            }
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(AppTheme.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 12))

            pdcaCard
        }
    }

    private func editToolRow(icon: String, title: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(AppTheme.accent)
                .frame(width: 24)
            Text(title)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundStyle(.white)
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)
        }
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var directionReportSection: some View {
        VStack(spacing: 12) {
            // 手修正ボタン
            NavigationLink {
                DirectionEditView(
                    projectId: project.id,
                    projectTitle: project.title
                )
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "pencil.and.outline")
                        .font(.system(size: 14, weight: .bold))
                    Text("ディレクションを編集")
                        .font(.subheadline)
                        .fontWeight(.bold)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(AppTheme.accent.opacity(0.5), lineWidth: 1)
                )
            }

            if let urlString = project.directionReportURL,
               let url = URL(string: urlString) {
                WebViewRepresentable(url: url)
                    .frame(minHeight: 600)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                overviewCard(
                    title: "ディレクションレポート",
                    icon: "doc.richtext",
                    items: ["レポートURLが未設定です"]
                )
            }
        }
    }

    /// YouTube URLかどうかを判定
    private func isYouTubeURL(_ url: String) -> Bool {
        url.contains("youtube.com/watch") || url.contains("youtu.be/")
    }

    private var sourceVideoSection: some View {
        SourceVideosSubTabView(project: project)
    }

    private var editedVideoSection: some View {
        VStack(spacing: 12) {
            if let url = project.editedVideoURL,
               !url.isEmpty {
                overviewCard(
                    title: "編集後動画",
                    icon: "sparkles.rectangle.stack",
                    items: ["編集完了。レビュー可能な状態です。"]
                )

                // Vimeo埋め込み再生（16:9アスペクト比）
                // WKWebViewはintrinsicContentSizeを持たないため、画面幅から直接計算
                if let videoId = VimeoURLParser.extractVideoId(from: url) {
                    VimeoEmbedPlayerView(videoId: videoId)
                        .frame(height: (UIScreen.main.bounds.width - 32) * 9.0 / 16.0)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                // 外部リンクボタン（Vimeoで直接開く）
                if let destination = URL(string: url) {
                    Link(destination: destination) {
                        HStack {
                            Image(systemName: "arrow.up.right.square")
                            Text("Vimeoで開く")
                        }
                        .font(.subheadline)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                        .background(Color(hex: 0x1AB7EA))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                }
            } else {
                overviewCard(
                    title: "編集後動画",
                    icon: "sparkles.rectangle.stack",
                    items: [
                        "編集後動画はまだアップロードされていません",
                        "パグさんが編集完了後にここに表示されます"
                    ]
                )
            }
        }
    }

    private var feedbackListSection: some View {
        VStack(spacing: 12) {
            if isFeedbackLoading {
                ProgressView()
                    .tint(AppTheme.accent)
                    .frame(maxWidth: .infinity, minHeight: 100)
            } else if feedbacks.isEmpty {
                overviewCard(
                    title: "フィードバック",
                    icon: "bubble.left.and.bubble.right",
                    items: ["まだフィードバックがありません"]
                )
            } else {
                ForEach(feedbacks) { fb in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(fb.createdBy)
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundStyle(AppTheme.accent)
                            Spacer()
                            Text(fb.createdAt)
                                .font(.caption2)
                                .foregroundStyle(AppTheme.textMuted)
                        }
                        Text(fb.content)
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.textSecondary)
                        if let timestamp = fb.timestamp {
                            HStack(spacing: 4) {
                                Image(systemName: "clock")
                                Text(timestamp)
                            }
                            .font(.caption2)
                            .foregroundStyle(AppTheme.textMuted)
                        }
                    }
                    .padding(16)
                    .background(AppTheme.cardBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
        }
        .task(id: project.id) {
            await loadFeedbacks()
        }
    }

    private var knowledgeDetailSection: some View {
        VStack(spacing: 12) {
            if let knowledge = project.knowledge, !knowledge.isEmpty {
                overviewCard(
                    title: "ナレッジハイライト",
                    icon: "lightbulb.fill",
                    items: knowledge.components(separatedBy: "\n").filter { !$0.isEmpty }
                )
            } else {
                overviewCard(
                    title: "ナレッジ連携",
                    icon: "books.vertical",
                    items: [
                        "この案件のナレッジはまだ生成されていません",
                        "動画分析完了後に自動生成されます"
                    ]
                )
            }
        }
    }

    private func overviewCard(title: String, icon: String, items: [String]) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: icon)
                    .foregroundStyle(AppTheme.accent)
                Text(title)
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)
            }

            ForEach(items, id: \.self) { item in
                HStack(alignment: .top, spacing: 10) {
                    Circle()
                        .fill(AppTheme.accent)
                        .frame(width: 6, height: 6)
                        .padding(.top, 6)
                    Text(item)
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var pdcaCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: "arrow.triangle.2.circlepath")
                    .foregroundStyle(AppTheme.accent)
                Text("品質改善サイクル")
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)
            }

            HStack(spacing: 12) {
                pdcaStep("D", "ディレクション", completed: true)
                pdcaStep("C", "編集", completed: project.editedVideoURL != nil)
                pdcaStep("A", "評価", completed: !feedbacks.isEmpty)
                pdcaStep("R", "ルール更新", completed: false)
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func pdcaStep(_ short: String, _ title: String, completed: Bool) -> some View {
        VStack(spacing: 8) {
            ZStack {
                Circle()
                    .fill(completed ? AppTheme.statusComplete.opacity(0.18) : AppTheme.cardBackgroundLight)
                    .frame(width: 44, height: 44)
                Circle()
                    .strokeBorder(completed ? AppTheme.statusComplete : AppTheme.textMuted.opacity(0.35), lineWidth: 1.5)
                    .frame(width: 44, height: 44)
                Text(short)
                    .font(.headline)
                    .foregroundStyle(completed ? AppTheme.statusComplete : AppTheme.textMuted)
            }
            Text(title)
                .font(.caption2)
                .foregroundStyle(.white)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
    }

    private var bottomActionBar: some View {
        HStack(spacing: 16) {
            Button {
                showVoiceFeedback = true
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "mic.fill")
                        .font(.system(size: 16, weight: .bold))
                    Text("音声フィードバックを追加")
                        .font(.subheadline)
                        .fontWeight(.bold)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(AppTheme.accent)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            Rectangle()
                .fill(AppTheme.cardBackground)
                .shadow(color: .black.opacity(0.5), radius: 10, y: -2)
                .ignoresSafeArea(edges: .bottom)
        )
    }

    private func scoreColor(_ score: Int) -> Color {
        if score >= 85 { return AppTheme.statusComplete }
        if score >= 70 { return Color(hex: 0xF5A623) }
        return AppTheme.accent
    }

    private func loadFeedbacks() async {
        isFeedbackLoading = true
        defer { isFeedbackLoading = false }
        do {
            feedbacks = try await APIClient.shared.fetchFeedbacks(projectId: project.id)
        } catch {
            feedbacks = []
        }
    }
}

// MARK: - ナレッジ閲覧ページ（WKWebViewフルスクリーン表示 + 音声FBフローティングボタン）
struct KnowledgePageWebView: View {
    let url: URL
    var projectId: String = ""
    @Environment(\.dismiss) private var dismiss
    @StateObject private var voiceVM = VoiceFeedbackViewModel()
    @State private var showRecordingPanel = false
    @State private var showSuccessToast = false

    var body: some View {
        NavigationView {
            ZStack(alignment: .bottomTrailing) {
                WebViewRepresentable(url: url)
                    .ignoresSafeArea(edges: .bottom)

                // 録音パネル（録音中〜送信完了まで表示）
                if showRecordingPanel {
                    knowledgeRecordingPanel
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                // フローティングマイクボタン（録音パネル非表示時のみ）
                if !showRecordingPanel {
                    floatingMicButton
                        .padding(.trailing, 20)
                        .padding(.bottom, 30)
                        .transition(.scale.combined(with: .opacity))
                }

                // 送信完了トースト
                if showSuccessToast {
                    successToast
                        .transition(.move(edge: .top).combined(with: .opacity))
                }
            }
            .animation(.easeInOut(duration: 0.3), value: showRecordingPanel)
            .animation(.easeInOut(duration: 0.3), value: showSuccessToast)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        voiceVM.resetFlow()
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
                        Image(systemName: "book.fill")
                            .foregroundStyle(AppTheme.accent)
                        Text("動画ナレッジ")
                            .font(.headline)
                            .foregroundStyle(.white)
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Link(destination: url) {
                        HStack(spacing: 4) {
                            Image(systemName: "safari")
                            Text("Safari")
                        }
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.accent)
                    }
                }
            }
            .toolbarBackground(AppTheme.cardBackground, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .onAppear {
            voiceVM.projectId = projectId
        }
    }

    // MARK: - フローティングマイクボタン（FABスタイル）
    private var floatingMicButton: some View {
        Button {
            showRecordingPanel = true
            voiceVM.toggleRecording()
        } label: {
            ZStack {
                Circle()
                    .fill(Color(hex: 0xE50914))
                    .frame(width: 60, height: 60)
                    .shadow(color: .black.opacity(0.4), radius: 8, x: 0, y: 4)

                Image(systemName: "mic.fill")
                    .font(.system(size: 24, weight: .bold))
                    .foregroundStyle(.white)
            }
        }
        .buttonStyle(.plain)
    }

    // MARK: - 録音パネル（WebView下部にオーバーレイ表示）
    private var knowledgeRecordingPanel: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 16) {
                // ドラッグハンドル
                RoundedRectangle(cornerRadius: 2)
                    .fill(AppTheme.textMuted.opacity(0.4))
                    .frame(width: 40, height: 4)
                    .padding(.top, 8)

                // ステータステキスト
                Text(panelStatusText)
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.textSecondary)

                // 録音ボタン + 時間表示
                HStack(spacing: 20) {
                    // 録音/停止ボタン
                    Button(action: {
                        if voiceVM.flowState == .idle {
                            voiceVM.toggleRecording()
                        } else if voiceVM.flowState == .recording {
                            voiceVM.toggleRecording()
                        }
                    }) {
                        ZStack {
                            // パルスアニメーション（録音中）
                            if voiceVM.flowState == .recording {
                                Circle()
                                    .fill(Color(hex: 0xE50914).opacity(0.3))
                                    .frame(width: 80, height: 80)
                                    .scaleEffect(knowledgePulseScale)
                                    .animation(
                                        .easeInOut(duration: 1.0).repeatForever(autoreverses: true),
                                        value: voiceVM.flowState
                                    )
                            }

                            Circle()
                                .fill(voiceVM.flowState == .recording
                                      ? Color(hex: 0xB71C1C)
                                      : Color(hex: 0xE50914))
                                .frame(width: 60, height: 60)
                                .overlay(
                                    Group {
                                        if voiceVM.flowState == .recording {
                                            RoundedRectangle(cornerRadius: 4)
                                                .fill(.white)
                                                .frame(width: 22, height: 22)
                                        } else {
                                            Image(systemName: "mic.fill")
                                                .font(.system(size: 24, weight: .bold))
                                                .foregroundStyle(.white)
                                        }
                                    }
                                )
                                .shadow(color: Color(hex: 0xE50914).opacity(0.4), radius: 6, x: 0, y: 3)
                        }
                    }
                    .buttonStyle(.plain)
                    .disabled(voiceVM.flowState == .transcribing)

                    // 録音時間（録音中のみ）
                    if voiceVM.flowState == .recording {
                        Text(voiceVM.formattedDuration)
                            .font(.system(size: 28, weight: .heavy, design: .monospaced))
                            .foregroundStyle(Color(hex: 0xE50914))
                    }

                    // 変換中スピナー
                    if voiceVM.flowState == .transcribing {
                        ProgressView()
                            .tint(AppTheme.accent)
                            .scaleEffect(1.2)
                    }
                }

                // 文字起こし結果（コンパクト表示）
                if !voiceVM.rawTranscript.isEmpty && voiceVM.flowState != .recording {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(voiceVM.rawTranscript)
                            .font(.caption)
                            .foregroundStyle(AppTheme.textSecondary)
                            .lineLimit(3)
                            .frame(maxWidth: .infinity, alignment: .leading)

                        // 変換ボタン
                        if voiceVM.canConvert {
                            Button(action: voiceVM.convertFeedback) {
                                HStack(spacing: 4) {
                                    Image(systemName: "arrow.triangle.2.circlepath")
                                    Text("プロの指示に変換")
                                }
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 10)
                                .background(AppTheme.accent)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                        }
                    }
                    .padding(.horizontal, 4)
                }

                // 変換結果（コンパクト表示）
                if !voiceVM.convertedText.isEmpty {
                    Text(voiceVM.convertedText)
                        .font(.caption)
                        .foregroundStyle(.white)
                        .lineLimit(3)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(8)
                        .background(AppTheme.statusComplete.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .padding(.horizontal, 4)
                }

                // アクションボタン群
                HStack(spacing: 12) {
                    // 閉じるボタン
                    Button {
                        voiceVM.resetFlow()
                        showRecordingPanel = false
                    } label: {
                        Text("閉じる")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundStyle(.white)
                            .padding(.vertical, 10)
                            .padding(.horizontal, 20)
                            .background(AppTheme.cardBackgroundLight)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }

                    // 送信ボタン（送信可能時のみ）
                    if voiceVM.canSend {
                        Button {
                            voiceVM.sendFeedback()
                            // 送信成功を監視
                            Task {
                                // flowState が .sent になるのを待つ
                                for _ in 0..<50 {
                                    try? await Task.sleep(nanoseconds: 200_000_000)
                                    if voiceVM.flowState == .sent {
                                        showRecordingPanel = false
                                        showSuccessToast = true
                                        // 2秒後にトースト非表示
                                        try? await Task.sleep(nanoseconds: 2_000_000_000)
                                        showSuccessToast = false
                                        voiceVM.resetFlow()
                                        break
                                    }
                                }
                            }
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: "paperplane.fill")
                                Text("送信")
                            }
                            .font(.subheadline)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(AppTheme.statusComplete)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                    }
                }

                // 送信メッセージ表示
                if let msg = voiceVM.sentMessage {
                    Text(msg)
                        .font(.caption)
                        .foregroundStyle(voiceVM.flowState == .sent ? AppTheme.statusComplete : AppTheme.accent)
                        .padding(.bottom, 4)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 20)
            .background(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(AppTheme.cardBackground)
                    .shadow(color: .black.opacity(0.5), radius: 15, y: -5)
                    .ignoresSafeArea(edges: .bottom)
            )
        }
    }

    // MARK: - 送信完了トースト
    private var successToast: some View {
        VStack {
            HStack(spacing: 8) {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(AppTheme.statusComplete)
                    .font(.system(size: 20))
                Text("フィードバックを送信しました")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
            .background(
                Capsule()
                    .fill(AppTheme.cardBackground)
                    .shadow(color: .black.opacity(0.3), radius: 8, y: 2)
            )
            .padding(.top, 60)

            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - ヘルパー
    private var panelStatusText: String {
        switch voiceVM.flowState {
        case .idle: return "タップして録音開始"
        case .recording: return "録音中... タップで停止"
        case .transcribing: return "文字起こし中..."
        case .readyToConvert: return "変換ボタンを押してください"
        case .readyToSend: return "送信できます"
        case .sent: return "送信完了"
        }
    }

    private var knowledgePulseScale: CGFloat {
        voiceVM.flowState == .recording ? 1.2 : 1.0
    }
}
