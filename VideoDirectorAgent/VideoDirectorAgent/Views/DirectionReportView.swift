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
    @State private var editingFeedback: FeedbackItem? = nil
    @State private var editingText: String = ""
    @State private var showVoiceFeedback = false
    @State private var showKnowledgePage = false
    @State private var showBeforeAfterSummary = false

    private let tabTitles = ["概要", "ディレクション", "YouTube素材", "素材", "FB・評価", "ナレッジ", "レビュー"]
    private var displaySubjectName: String {
        project.primarySubjectName?.isEmpty == false ? project.primarySubjectName! : project.guestName
    }
    private var isPersonalLongformRoute: Bool {
        project.routeProfile == "teko_personal_longform"
    }

    var body: some View {
        Group {
            if showBeforeAfterSummary {
                BeforeAfterSummaryView(
                    projectId: project.id,
                    projectTitle: project.title,
                    onClose: {
                        showBeforeAfterSummary = false
                    }
                )
            } else {
                reportContent
            }
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .fullScreenCover(isPresented: $showVoiceFeedback) {
            VoiceFeedbackView(projectId: project.id)
        }
        .sheet(isPresented: $showKnowledgePage) {
            if let urlString = project.knowledgePageUrl,
               let url = URL(string: urlString) {
                KnowledgePageWebView(url: url, projectId: project.id)
            }
        }
    }

    private var reportContent: some View {
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
                Text(displaySubjectName)
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
                    if !isPersonalLongformRoute {
                        Button {
                            showBeforeAfterSummary = true
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
                        .accessibilityIdentifier("direction-before-after-button")
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
                if isPersonalLongformRoute {
                    PersonalLongformPanelView(
                        projectId: project.id,
                        icon: "list.bullet.rectangle.portrait.fill",
                        loader: APIClient.shared.fetchPersonalLongformWorkflow
                    )
                } else {
                    directionReportSection
                }
            case 2:
                YouTubeAssetsView(projectId: project.id)
            case 3:
                if isPersonalLongformRoute {
                    PersonalLongformPanelView(
                        projectId: project.id,
                        icon: "video.badge.waveform.fill",
                        loader: APIClient.shared.fetchPersonalLongformMaterialRoles
                    )
                } else {
                    sourceVideoSection
                }
            case 4:
                feedbackListSection
            case 5:
                if isPersonalLongformRoute {
                    PersonalLongformPanelView(
                        projectId: project.id,
                        icon: "books.vertical.fill",
                        loader: APIClient.shared.fetchPersonalLongformSourceBundle
                    )
                } else {
                    knowledgeDetailSection
                }
            case 6:
                if isPersonalLongformRoute {
                    PersonalLongformPanelView(
                        projectId: project.id,
                        icon: "checklist.checked",
                        loader: APIClient.shared.fetchPersonalLongformHumanChecks
                    )
                } else {
                    VimeoReviewTabView(projectId: project.id, editedVideoURL: project.editedVideoURL)
                }
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
                    "\(isPersonalLongformRoute ? "対象" : "ゲスト"): \(displaySubjectName)",
                    "ルート: \(project.categoryDisplayName)",
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
                    VimeoEmbedPlayerView(
                        videoId: videoId,
                        privacyHash: VimeoURLParser.extractPrivacyHash(from: url)
                    )
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
                        // 編集ボタン
                        HStack {
                            Spacer()
                            Button {
                                editingText = fb.convertedText ?? fb.content
                                editingFeedback = fb
                            } label: {
                                Label("編集", systemImage: "pencil")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.accent)
                            }
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
        .sheet(item: $editingFeedback) { fb in
            FeedbackEditSheet(
                feedbackId: fb.id,
                initialText: editingText,
                onSave: { newText in
                    Task {
                        try? await APIClient.shared.updateConvertedText(
                            feedbackId: fb.id, newText: newText
                        )
                        await loadFeedbacks()
                    }
                }
            )
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

private struct PersonalLongformPanelView: View {
    let projectId: String
    let icon: String
    let loader: (String) async throws -> PersonalLongformPanelResponse

    @State private var response: PersonalLongformPanelResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if isLoading && response == nil {
                ProgressView()
                    .tint(AppTheme.accent)
                    .frame(maxWidth: .infinity, minHeight: 120)
            } else if let response {
                header(response)
                ForEach(response.items) { item in
                    itemCard(item)
                }
            } else {
                fallbackCard
            }
        }
        .task(id: projectId) {
            await load()
        }
    }

    private func header(_ response: PersonalLongformPanelResponse) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .foregroundStyle(Color(hex: 0x46D369))
                Text(response.title)
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)
                Spacer()
                Text("属人ch")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundStyle(.black)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color(hex: 0x46D369))
                    .clipShape(Capsule())
            }
            Text(response.summary)
                .font(.subheadline)
                .foregroundStyle(AppTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func itemCard(_ item: PersonalLongformPanelItem) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 10) {
                Circle()
                    .fill(statusColor(item.status))
                    .frame(width: 8, height: 8)
                    .padding(.top, 6)
                VStack(alignment: .leading, spacing: 5) {
                    Text(item.title)
                        .font(.headline)
                        .foregroundStyle(.white)
                    if let subtitle = item.subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(Color(hex: 0x46D369))
                    }
                    if let detail = item.detail, !detail.isEmpty {
                        Text(detail)
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                Spacer()
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var fallbackCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(Color(hex: 0xF5A623))
                Text("読み込み待ち")
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)
            }
            Text(errorMessage ?? "属人chルート情報を取得しています")
                .font(.subheadline)
                .foregroundStyle(AppTheme.textSecondary)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            response = try await loader(projectId)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func statusColor(_ status: String?) -> Color {
        switch status {
        case "ready", "draft_ready":
            return Color(hex: 0x46D369)
        case "needs_review", "needs_sync_review", "must_check":
            return Color(hex: 0xF5A623)
        case "blocked_until_approved", "internal_only":
            return AppTheme.accent
        default:
            return AppTheme.textMuted
        }
    }
}

// MARK: - FB編集シート
private struct FeedbackEditSheet: View {
    let feedbackId: String
    let initialText: String
    let onSave: (String) -> Void

    @State private var text: String = ""
    @State private var isSaving = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                TextEditor(text: $text)
                    .font(.body)
                    .padding(12)
                    .scrollContentBackground(.hidden)
                    .background(AppTheme.cardBackground)
            }
            .background(AppTheme.background)
            .navigationTitle("フィードバック編集")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("キャンセル") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        isSaving = true
                        onSave(text)
                        dismiss()
                    }
                    .disabled(text.isEmpty || isSaving)
                }
            }
        }
        .onAppear {
            text = initialText
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

private struct InlinePreviewItem: Identifiable {
    let id: String
    let label: String
    let embedURL: String
    let externalURL: String
}

private struct BeforeAfterSummaryView: View {
    let projectId: String
    let projectTitle: String
    let onClose: () -> Void

    @State private var isLoading = true
    @State private var response: BeforeAfterResponse?
    @State private var transcriptData: TranscriptDiffResponse?
    @State private var fbTrackerData: FBTrackerResponse?
    @State private var errorMessage: String?
    @State private var isSupplementalLoading = false
    @State private var activeInlinePlayerKey: String?
    @State private var selectedInlinePlayerKey: String?
    @State private var selectedComparisonMode = 0
    @State private var selectedComparisonPairId: String = "source-edited"
    @State private var selectedSourceIndex = 0
    @State private var showTranscriptDetails = false
    @State private var selectedTranscriptVersion: String?
    @State private var isTranscriptReloading = false
    @State private var showFBTrackerDetails = true
    @State private var updatingFBTrackerItemId: String?

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(alignment: .leading, spacing: 18) {
                header

                if isLoading {
                    loading
                } else if let errorMessage {
                    error(errorMessage)
                } else if let response {
                    summary(response)
                }

                Spacer(minLength: 40)
            }
            .padding(.bottom, 24)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .task {
            await loadSummary()
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Button(action: onClose) {
                    HStack(spacing: 4) {
                        Image(systemName: "chevron.left")
                        Text("戻る")
                    }
                    .font(AppTheme.labelFont(13))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(AppTheme.cardBackground)
                    .clipShape(Capsule())
                }
                .accessibilityIdentifier("before-after-summary-close")

                Spacer()
            }

            HStack(spacing: 8) {
                Image(systemName: "rectangle.on.rectangle.angled")
                    .foregroundStyle(AppTheme.accent)
                Text("ビフォーアフター")
                    .font(AppTheme.heroFont(24))
                    .foregroundStyle(.white)
            }

        }
        .padding(.horizontal, 16)
        .padding(.top, 18)
    }

    private var loading: some View {
        VStack(spacing: 12) {
            ProgressView()
                .tint(AppTheme.accent)
            Text("概要を読み込み中...")
                .font(AppTheme.bodyFont(13))
                .foregroundStyle(AppTheme.textMuted)
        }
        .frame(maxWidth: .infinity, minHeight: 220)
    }

    private func error(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("読み込みに失敗しました", systemImage: "exclamationmark.triangle")
                .font(AppTheme.sectionFont(16))
                .foregroundStyle(AppTheme.accent)
            Text(message)
                .font(AppTheme.bodyFont(13))
                .foregroundStyle(AppTheme.textSecondary)
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal, 16)
    }

    private func summary(_ response: BeforeAfterResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            legacyBeforeAfterMainSection(response)
            diffHighlightsFullSection(response)
            transcriptDetailsSection(response)
            fbTrackerDetailsSection
        }
        .padding(.horizontal, 16)
        .accessibilityIdentifier("before-after-summary-screen")
    }

    private func restoreStatusBanner(_ response: BeforeAfterResponse) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "sparkles")
                    .foregroundStyle(AppTheme.accent)
                Text("Build74 文字色復旧")
                    .font(AppTheme.sectionFont(16))
                    .foregroundStyle(.white)
                Spacer()
            }

            Text("旧画面と同じ順番で、比較モード・上下2段比較・FBタイムスタンプ・文字起こし比較・FB指示トラッカーを表示します。")
                .font(AppTheme.bodyFont(12))
                .foregroundStyle(AppTheme.textMuted)

            HStack(spacing: 8) {
                previewPill("素材", "\(response.sourceVideos.count)")
                previewPill("FB", "\(response.diffHighlights.count)")
                previewPill("文字", "\(transcriptData?.segments.count ?? 0)")
                previewPill("指示", "\(fbTrackerData?.items.count ?? 0)")
            }

            if isSupplementalLoading {
                HStack(spacing: 6) {
                    ProgressView()
                        .scaleEffect(0.7)
                        .tint(AppTheme.accent)
                    Text("詳細データ読込中")
                        .font(AppTheme.labelFont(11))
                        .foregroundStyle(AppTheme.textMuted)
                }
                .accessibilityIdentifier("before-after-supplemental-loading")
            }
        }
        .padding(12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .accessibilityIdentifier("before-after-build74-transcript-colors")
    }

    private func legacyBeforeAfterMainSection(_ response: BeforeAfterResponse) -> some View {
        let items = inlinePreviewItems(response)

        return VStack(alignment: .leading, spacing: 10) {
            Text(projectTitle)
                .font(AppTheme.heroFont(22))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, alignment: .leading)

            legacyComparisonModePicker(items)
            sourceMaterialPicker(response)
            legacyTwoUpComparison(items)
            safeExternalLinks(response)
        }
        .padding(.vertical, 4)
        .accessibilityIdentifier("before-after-legacy-main-layout")
    }

    private func previewRecoveryBanner(_ response: BeforeAfterResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "sparkles")
                    .foregroundStyle(AppTheme.accent)
                Text("Build74 文字色復旧")
                    .font(AppTheme.sectionFont(16))
                    .foregroundStyle(.white)
                Spacer()
            }

            HStack(spacing: 8) {
                previewPill("素材", "\(min(response.sourceVideos.count, 3))/\(response.sourceVideos.count)")
                previewPill("FB", "\(min(response.diffHighlights.count, 5))/\(response.diffHighlights.count)")
                previewPill("文字", "\(min(transcriptData?.segments.count ?? 0, 5))/\(transcriptData?.segments.count ?? 0)")
                previewPill("指示", "\(min(fbTrackerData?.items.count ?? 0, 5))/\(fbTrackerData?.items.count ?? 0)")
            }

            if isSupplementalLoading {
                HStack(spacing: 6) {
                    ProgressView()
                        .scaleEffect(0.7)
                        .tint(AppTheme.accent)
                    Text("詳細データ読込中")
                        .font(AppTheme.labelFont(11))
                        .foregroundStyle(AppTheme.textMuted)
                }
                .accessibilityIdentifier("before-after-supplemental-loading")
            }

            VStack(alignment: .leading, spacing: 8) {
                compactPreviewLine(
                    icon: "play.rectangle",
                    label: "素材",
                    value: response.sourceVideos.first?.title ?? response.sourceVideos.first?.youtubeUrl ?? "未連携"
                )
                compactPreviewLine(
                    icon: "film",
                    label: "編集後",
                    value: editedVideoPreviewText(response)
                )
                compactPreviewLine(
                    icon: "text.quote",
                    label: "文字",
                    value: transcriptPreviewText
                )
                compactPreviewLine(
                    icon: "checklist",
                    label: "指示",
                    value: fbInstructionPreviewText
                )
            }

            safeInlinePreview(response)
            safeExternalLinks(response)

            Text("概要を先に開き、比較スロット・FB指示チェック・文字起こし比較を後から埋めます。再生はタップした1本だけに絞ります。")
                .font(AppTheme.bodyFont(12))
                .foregroundStyle(AppTheme.textMuted)
        }
        .padding(12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .accessibilityIdentifier("before-after-build74-transcript-colors")
    }

    private func safeInlinePreview(_ response: BeforeAfterResponse) -> some View {
        let items = inlinePreviewItems(response)
        let selectedItem = selectedInlineItem(from: items)

        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "rectangle.inset.filled.and.person.filled")
                    .foregroundStyle(AppTheme.accent)
                Text("アプリ内プレビュー")
                    .font(AppTheme.sectionFont(14))
                    .foregroundStyle(.white)
                Spacer()
            }

            legacyComparisonModePicker(items)
            legacyTwoUpComparison(items)
            inlineSelectionStatus(selectedItem)
            comparisonPairControls(items)
            comparisonPairStatus(items)

            if items.isEmpty {
                HStack(spacing: 8) {
                    Image(systemName: "video.slash")
                        .foregroundStyle(AppTheme.textMuted)
                    Text("素材/編集後/FB後動画が未登録のため、ここでは再生できません。")
                        .font(AppTheme.bodyFont(12))
                        .foregroundStyle(AppTheme.textMuted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            } else if let selectedItem {
                HStack(spacing: 8) {
                    ForEach(items) { item in
                        inlinePreviewOption(item, isSelected: item.id == selectedItem.id)
                    }
                }

                SafeIframePlayerView(
                    embedURL: selectedItem.embedURL,
                    isActive: Binding(
                        get: { activeInlinePlayerKey == selectedItem.id },
                        set: { isActive in
                            activeInlinePlayerKey = isActive ? selectedItem.id : nil
                        }
                    )
                )
                .id(selectedItem.id)
                .frame(height: 180)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .accessibilityIdentifier("before-after-inline-selected-player")
            }
        }
        .padding(10)
        .background(AppTheme.cardBackground.opacity(0.65))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .accessibilityIdentifier("before-after-inline-preview-section")
    }

    private func inlineSelectionStatus(_ item: InlinePreviewItem?) -> some View {
        HStack(spacing: 8) {
            HStack(spacing: 5) {
                Image(systemName: "scope")
                Text("選択中: \(item?.label ?? "未登録")")
            }
            .font(AppTheme.labelFont(11))
            .foregroundStyle(AppTheme.textSecondary)
            .accessibilityIdentifier("before-after-inline-selected-label")

            Spacer()

            if let item,
               let url = URL(string: item.externalURL) {
                Link(destination: url) {
                    HStack(spacing: 4) {
                        Image(systemName: "safari")
                        Text("外で開く")
                    }
                    .font(AppTheme.labelFont(11))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 6)
                    .background(AppTheme.accent.opacity(0.35))
                    .clipShape(Capsule())
                }
                .accessibilityIdentifier("before-after-inline-open-selected")
            } else {
                HStack(spacing: 4) {
                    Image(systemName: "safari")
                    Text("外で開く")
                }
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)
                .padding(.horizontal, 9)
                .padding(.vertical, 6)
                .background(AppTheme.cardBackground)
                .clipShape(Capsule())
                .accessibilityIdentifier("before-after-inline-open-selected")
            }
        }
        .padding(.horizontal, 2)
    }

    private func inlinePreviewOption(_ item: InlinePreviewItem, isSelected: Bool) -> some View {
        Button {
            selectedInlinePlayerKey = item.id
            activeInlinePlayerKey = nil
        } label: {
            HStack(spacing: 5) {
                Image(systemName: isSelected ? "play.circle.fill" : "circle")
                Text(item.label)
            }
            .font(AppTheme.labelFont(11))
            .foregroundStyle(isSelected ? .white : AppTheme.textMuted)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(isSelected ? AppTheme.accent.opacity(0.35) : AppTheme.cardBackground)
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("before-after-inline-option-\(item.id)")
    }

    private func legacyComparisonModePicker(_ items: [InlinePreviewItem]) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text("比較モード")
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)

            Picker("比較モード", selection: $selectedComparisonMode) {
                Text("素材 vs 編集後").tag(0)
                Text("編集後 vs FB後").tag(1)
            }
            .pickerStyle(.segmented)
            .accessibilityIdentifier("before-after-comparison-mode-picker")
        }
        .onChange(of: selectedComparisonMode) { _, mode in
            selectedComparisonPairId = mode == 0 ? "source-edited" : "edited-fb"
            activeInlinePlayerKey = nil
        }
    }

    private func sourceMaterialPicker(_ response: BeforeAfterResponse) -> some View {
        Group {
            if selectedComparisonMode == 0, response.sourceVideos.count > 1 {
                HStack(spacing: 8) {
                    Text("素材選択")
                        .font(AppTheme.labelFont(11))
                        .foregroundStyle(AppTheme.textMuted)

                    Picker("素材", selection: $selectedSourceIndex) {
                        ForEach(0..<response.sourceVideos.count, id: \.self) { index in
                            Text("素材\(index + 1)").tag(index)
                        }
                    }
                    .pickerStyle(.menu)
                    .tint(AppTheme.accent)

                    Spacer()
                }
                .padding(.horizontal, 2)
                .accessibilityIdentifier("before-after-source-picker")
            }
        }
        .onChange(of: selectedSourceIndex) { _, _ in
            selectedInlinePlayerKey = "source"
            activeInlinePlayerKey = nil
        }
    }

    private func legacyTwoUpComparison(_ items: [InlinePreviewItem]) -> some View {
        let pair = legacyComparisonPair(items)

        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "rectangle.split.2x1")
                    .foregroundStyle(AppTheme.accent)
                Text("上下2段比較")
                    .font(AppTheme.sectionFont(14))
                    .foregroundStyle(.white)
                Spacer()
                Text(pair.label)
                    .font(AppTheme.labelFont(10))
                    .foregroundStyle(AppTheme.textMuted)
            }

            legacyComparisonSlot(position: "上段", item: pair.before)
            legacyComparisonSlot(position: "下段", item: pair.after)
        }
        .padding(10)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .accessibilityIdentifier("before-after-two-up-comparison")
    }

    private func legacyComparisonSlot(position: String, item: InlinePreviewItem?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Circle()
                    .fill(position == "上段" ? Color(hex: 0x4A90D9) : AppTheme.accent)
                    .frame(width: 8, height: 8)
                Text("\(position): \(item?.label ?? "未登録")")
                    .font(AppTheme.labelFont(12))
                    .foregroundStyle(item == nil ? AppTheme.textMuted : AppTheme.textSecondary)
                Spacer()
            }

            if let item {
                SafeIframePlayerView(
                    embedURL: item.embedURL,
                    isActive: Binding(
                        get: { activeInlinePlayerKey == "slot-\(item.id)" },
                        set: { isActive in
                            selectedInlinePlayerKey = item.id
                            activeInlinePlayerKey = isActive ? "slot-\(item.id)" : nil
                        }
                    )
                )
                .id("slot-\(item.id)")
                .aspectRatio(16.0 / 9.0, contentMode: .fit)
                .frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .accessibilityIdentifier("before-after-legacy-16x9-player")
            } else {
                HStack(spacing: 8) {
                    Image(systemName: "video.slash")
                        .foregroundStyle(AppTheme.textMuted)
                    Text("この比較対象は未登録です")
                        .font(AppTheme.bodyFont(12))
                        .foregroundStyle(AppTheme.textMuted)
                }
                .aspectRatio(16.0 / 9.0, contentMode: .fit)
                .frame(maxWidth: .infinity, alignment: .center)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
        .accessibilityIdentifier(position == "上段" ? "before-after-two-up-top" : "before-after-two-up-bottom")
    }

    private func legacyComparisonPair(_ items: [InlinePreviewItem]) -> (label: String, before: InlinePreviewItem?, after: InlinePreviewItem?) {
        if selectedComparisonMode == 1 {
            return (
                "編集後 vs FB後",
                items.first(where: { $0.id == "edited" }),
                items.first(where: { $0.id == "fb-revised" })
            )
        }
        return (
            "素材 vs 編集後",
            items.first(where: { $0.id == "source" }),
            items.first(where: { $0.id == "edited" })
        )
    }

    private func comparisonPairControls(_ items: [InlinePreviewItem]) -> some View {
        let hasSourceEdited = hasAnyInlineItem(["source", "edited"], in: items)
        let hasEditedFB = hasAnyInlineItem(["edited", "fb-revised"], in: items)
        let sourceEditedSelected = selectedComparisonPairId == "source-edited"
        let editedFBSelected = selectedComparisonPairId == "edited-fb"

        return VStack(alignment: .leading, spacing: 6) {
            Text("比較ペア")
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)

            HStack(spacing: 8) {
                comparisonPairButton(
                    label: "素材→編集後",
                    systemImage: "arrow.right.circle",
                    isEnabled: hasSourceEdited,
                    isSelected: sourceEditedSelected,
                    accessibilityId: "before-after-compare-source-edited"
                ) {
                    selectComparisonPair(pairId: "source-edited", primary: "edited", fallback: "source", items: items)
                }

                comparisonPairButton(
                    label: "編集後→FB後",
                    systemImage: "arrow.triangle.2.circlepath.circle",
                    isEnabled: hasEditedFB,
                    isSelected: editedFBSelected,
                    accessibilityId: "before-after-compare-edited-fb"
                ) {
                    selectComparisonPair(pairId: "edited-fb", primary: "fb-revised", fallback: "edited", items: items)
                }
            }
        }
        .accessibilityIdentifier("before-after-comparison-pair-row")
    }

    private func comparisonPairStatus(_ items: [InlinePreviewItem]) -> some View {
        let isEditedFB = selectedComparisonPairId == "edited-fb"
        let pairLabel = isEditedFB ? "編集後→FB後" : "素材→編集後"
        let beforeItem = items.first(where: { $0.id == (isEditedFB ? "edited" : "source") })
        let afterItem = items.first(where: { $0.id == (isEditedFB ? "fb-revised" : "edited") })

        return VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 5) {
                Image(systemName: "rectangle.split.2x1")
                    .foregroundStyle(AppTheme.accent)
                Text("比較中: \(pairLabel)")
                    .font(AppTheme.labelFont(11))
                    .foregroundStyle(AppTheme.textSecondary)
            }
            .accessibilityIdentifier("before-after-comparison-selected-label")

            HStack(spacing: 8) {
                comparisonPairEndpoint(prefix: "左", item: beforeItem)
                comparisonPairEndpoint(prefix: "右", item: afterItem)
            }

            HStack(spacing: 8) {
                comparisonSideButton(label: "左を再生", item: beforeItem, accessibilityId: "before-after-play-left")
                comparisonSideButton(label: "右を再生", item: afterItem, accessibilityId: "before-after-play-right")
            }
        }
        .padding(10)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .accessibilityIdentifier("before-after-comparison-status")
    }

    private func comparisonPairEndpoint(prefix: String, item: InlinePreviewItem?) -> some View {
        HStack(spacing: 4) {
            Text("\(prefix):")
                .font(AppTheme.labelFont(10))
                .foregroundStyle(AppTheme.textMuted)
            Text(item?.label ?? "未登録")
                .font(AppTheme.labelFont(10))
                .foregroundStyle(item == nil ? AppTheme.textMuted : .white)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func comparisonSideButton(label: String, item: InlinePreviewItem?, accessibilityId: String) -> some View {
        Button {
            if let item {
                selectedInlinePlayerKey = item.id
                activeInlinePlayerKey = nil
            }
        } label: {
            HStack(spacing: 5) {
                Image(systemName: item == nil ? "minus.circle" : "play.circle")
                Text(label)
            }
            .font(AppTheme.labelFont(11))
            .foregroundStyle(item == nil ? AppTheme.textMuted : .white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 7)
            .background(item == nil ? AppTheme.cardBackgroundLight : AppTheme.accent.opacity(0.28))
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(accessibilityId)
    }

    private func comparisonPairButton(
        label: String,
        systemImage: String,
        isEnabled: Bool,
        isSelected: Bool,
        accessibilityId: String,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: systemImage)
                Text(label)
            }
            .font(AppTheme.labelFont(11))
            .foregroundStyle(isEnabled ? .white : AppTheme.textMuted)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(isEnabled && isSelected ? AppTheme.accent.opacity(0.48) : (isEnabled ? AppTheme.accent.opacity(0.28) : AppTheme.cardBackground))
            .clipShape(Capsule())
        }
        .buttonStyle(.plain)
        .disabled(!isEnabled)
        .accessibilityIdentifier(accessibilityId)
    }

    private func selectComparisonPair(pairId: String, primary: String, fallback: String, items: [InlinePreviewItem]) {
        selectedComparisonPairId = pairId
        selectedComparisonMode = pairId == "edited-fb" ? 1 : 0
        if let target = items.first(where: { $0.id == primary }) ?? items.first(where: { $0.id == fallback }) {
            selectedInlinePlayerKey = target.id
            activeInlinePlayerKey = nil
        }
    }

    private func hasAnyInlineItem(_ ids: [String], in items: [InlinePreviewItem]) -> Bool {
        items.contains { ids.contains($0.id) }
    }

    private func inlinePreviewItems(_ response: BeforeAfterResponse) -> [InlinePreviewItem] {
        var items: [InlinePreviewItem] = []
        if !response.sourceVideos.isEmpty {
            let safeIndex = min(max(selectedSourceIndex, 0), response.sourceVideos.count - 1)
            let source = response.sourceVideos[safeIndex]
            if !source.embedUrl.isEmpty {
                items.append(
                    InlinePreviewItem(
                        id: "source",
                        label: response.sourceVideos.count > 1 ? "素材\(safeIndex + 1)" : "素材",
                        embedURL: source.embedUrl,
                        externalURL: source.youtubeUrl
                    )
                )
            }
        }
        if let edited = response.editedVideo,
           let embedURL = edited.embedUrl,
           !embedURL.isEmpty {
            items.append(
                InlinePreviewItem(
                    id: "edited",
                    label: edited.versionLabel?.isEmpty == false ? edited.versionLabel! : "編集後",
                    embedURL: embedURL,
                    externalURL: edited.vimeoUrl
                )
            )
        }
        if let revised = response.fbRevisedVideo,
           let embedURL = revised.embedUrl,
           !embedURL.isEmpty {
            items.append(
                InlinePreviewItem(
                    id: "fb-revised",
                    label: revised.versionLabel?.isEmpty == false ? revised.versionLabel! : "FB後",
                    embedURL: embedURL,
                    externalURL: revised.vimeoUrl
                )
            )
        }
        return items
    }

    private func selectedInlineItem(from items: [InlinePreviewItem]) -> InlinePreviewItem? {
        if let selectedInlinePlayerKey,
           let selected = items.first(where: { $0.id == selectedInlinePlayerKey }) {
            return selected
        }
        return items.first
    }

    private func safeExternalLinks(_ response: BeforeAfterResponse) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("外部で開く")
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)
            HStack(spacing: 8) {
                if let source = response.sourceVideos.first,
                   let url = URL(string: source.youtubeUrl) {
                    safeExternalLink("素材", icon: "play.rectangle", url: url)
                } else {
                    disabledLinkPill("素材")
                }

                if let edited = response.editedVideo,
                   let url = URL(string: edited.vimeoUrl) {
                    safeExternalLink("編集後", icon: "film", url: url)
                } else {
                    disabledLinkPill("編集後")
                }

                if let revised = response.fbRevisedVideo,
                   let url = URL(string: revised.vimeoUrl) {
                    safeExternalLink("FB後", icon: "arrow.triangle.2.circlepath", url: url)
                }
            }
        }
        .accessibilityIdentifier("before-after-external-link-row")
    }

    private func safeExternalLink(_ label: String, icon: String, url: URL) -> some View {
        Link(destination: url) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                Text(label)
            }
            .font(AppTheme.labelFont(11))
            .foregroundStyle(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(AppTheme.accent.opacity(0.35))
            .clipShape(Capsule())
        }
        .accessibilityIdentifier("before-after-open-\(label)")
    }

    private func disabledLinkPill(_ label: String) -> some View {
        HStack(spacing: 5) {
            Image(systemName: "minus.circle")
            Text(label)
        }
        .font(AppTheme.labelFont(11))
        .foregroundStyle(AppTheme.textMuted)
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(AppTheme.cardBackground)
        .clipShape(Capsule())
    }

    private func compactPreviewLine(icon: String, label: String, value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(AppTheme.accent)
                .frame(width: 18)
            Text(label)
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)
                .frame(width: 42, alignment: .leading)
            Text(value.isEmpty ? "未連携" : value)
                .font(AppTheme.bodyFont(12))
                .foregroundStyle(AppTheme.textSecondary)
                .lineLimit(2)
        }
    }

    private func editedVideoPreviewText(_ response: BeforeAfterResponse) -> String {
        if let revised = response.fbRevisedVideo {
            return "\(revised.versionLabel ?? "FB修正版") \(revised.editorName ?? "")".trimmingCharacters(in: .whitespaces)
        }
        if let edited = response.editedVideo {
            return "\(edited.versionLabel ?? "編集後") \(edited.editorName ?? "")".trimmingCharacters(in: .whitespaces)
        }
        return "未登録"
    }

    private var transcriptPreviewText: String {
        if let first = transcriptData?.segments.first {
            return first.text
        }
        if let message = transcriptData?.message, !message.isEmpty {
            return message
        }
        return "未取得"
    }

    private var fbInstructionPreviewText: String {
        if let first = fbTrackerData?.items.first {
            return first.text
        }
        if let message = fbTrackerData?.message, !message.isEmpty {
            return message
        }
        return "Vimeoコメント0件"
    }

    private func previewPill(_ label: String, _ value: String) -> some View {
        HStack(spacing: 4) {
            Text(label)
                .font(AppTheme.labelFont(10))
                .foregroundStyle(AppTheme.textMuted)
            Text(value)
                .font(AppTheme.labelFont(11))
                .foregroundStyle(.white)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(AppTheme.cardBackground)
        .clipShape(Capsule())
    }

    private func metricRow(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
                .font(AppTheme.bodyFont(13))
                .foregroundStyle(AppTheme.textMuted)
            Spacer()
            Text(value)
                .font(AppTheme.labelFont(13))
                .foregroundStyle(.white)
        }
    }

    private func previewDivider(_ title: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider().background(AppTheme.textMuted.opacity(0.3))
            Text(title)
                .font(AppTheme.sectionFont(15))
                .foregroundStyle(.white)
        }
        .padding(.top, 4)
    }

    private func previewRow(leading: String, title: String, subtitle: String?) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text(leading)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(AppTheme.accent)
                .frame(width: 62, alignment: .leading)

            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(AppTheme.textSecondary)
                    .lineLimit(2)
                if let subtitle, !subtitle.isEmpty {
                    Text(subtitle)
                        .font(AppTheme.labelFont(10))
                        .foregroundStyle(AppTheme.textMuted)
                }
            }
        }
        .padding(.vertical, 4)
    }

    private func diffHighlightsFullSection(_ response: BeforeAfterResponse) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            if !response.diffHighlights.isEmpty {
                HStack {
                    Image(systemName: "clock.badge.exclamationmark")
                        .foregroundStyle(AppTheme.accent)
                    Text("FBタイムスタンプ")
                        .font(AppTheme.sectionFont(16))
                        .foregroundStyle(.white)
                    Spacer()
                    Text("\(response.diffHighlights.count)件")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 6)

                ForEach(response.diffHighlights) { highlight in
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
                            if let category = highlight.category, !category.isEmpty {
                                Text(category)
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
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityIdentifier("before-after-diff-highlights-section")
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

    private var fbTrackerDetailsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Button {
                withAnimation(.easeInOut(duration: 0.18)) {
                    showFBTrackerDetails.toggle()
                }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "checklist")
                        .foregroundStyle(AppTheme.accent)
                    Text("FB指示トラッカー")
                        .font(AppTheme.sectionFont(15))
                        .foregroundStyle(.white)
                    Spacer()
                    Text(fbTrackerSummaryText)
                        .font(AppTheme.labelFont(10))
                        .foregroundStyle(AppTheme.textMuted)
                    Image(systemName: showFBTrackerDetails ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("before-after-fb-tracker-toggle")

            if showFBTrackerDetails {
                if let tracker = fbTrackerData, !tracker.items.isEmpty {
                    fbTrackerProgressRow(tracker)

                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(tracker.items) { item in
                            fbTrackerCheckRow(item)
                        }
                    }
                    .accessibilityIdentifier("before-after-fb-tracker-full-list")
                } else if isSupplementalLoading {
                    HStack(spacing: 8) {
                        ProgressView()
                            .scaleEffect(0.75)
                            .tint(AppTheme.accent)
                        Text("FB指示を読み込み中")
                            .font(AppTheme.bodyFont(12))
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 8)
                } else {
                    Text(fbTrackerData?.message ?? "FB指示がまだありません")
                        .font(AppTheme.bodyFont(12))
                        .foregroundStyle(AppTheme.textMuted)
                        .padding(.vertical, 8)
                }
            }
        }
        .padding(12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .accessibilityIdentifier("before-after-fb-tracker-section")
    }

    private func fbTrackerProgressRow(_ tracker: FBTrackerResponse) -> some View {
        HStack(spacing: 8) {
            transcriptStat("\(tracker.summary.resolved)/\(tracker.summary.total) 対応済み")
            if tracker.summary.pending > 0 {
                transcriptStat("未対応 \(tracker.summary.pending)")
            }
            GeometryReader { geo in
                let ratio = tracker.summary.total > 0
                    ? CGFloat(tracker.summary.resolved) / CGFloat(tracker.summary.total)
                    : 0
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.gray.opacity(0.25))
                    RoundedRectangle(cornerRadius: 4)
                        .fill(tracker.summary.pending == 0 ? AppTheme.statusComplete : Color.orange)
                        .frame(width: geo.size.width * ratio)
                }
            }
            .frame(height: 6)
        }
        .accessibilityIdentifier("before-after-fb-tracker-progress")
    }

    private func fbTrackerCheckRow(_ item: FBTrackerItem) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Button {
                Task { await toggleFBTrackerItem(item) }
            } label: {
                if updatingFBTrackerItemId == item.id {
                    ProgressView()
                        .scaleEffect(0.72)
                        .tint(AppTheme.accent)
                        .frame(width: 24, height: 24)
                } else {
                    Image(systemName: item.status == "resolved" ? "checkmark.circle.fill" : "circle")
                        .font(.title3)
                        .foregroundStyle(item.statusColor)
                        .frame(width: 24, height: 24)
                }
            }
            .buttonStyle(.plain)
            .disabled(updatingFBTrackerItemId != nil || item.uri.isEmpty)
            .accessibilityIdentifier("before-after-fb-tracker-check-\(item.id)")

            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 6) {
                    if let timecode = item.timecode, !timecode.isEmpty {
                        Text(timecode)
                            .font(AppTheme.labelFont(10))
                            .foregroundStyle(AppTheme.accent)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(AppTheme.accent.opacity(0.14))
                            .clipShape(Capsule())
                    }
                    Text(item.versionLabel)
                        .font(AppTheme.labelFont(10))
                        .foregroundStyle(AppTheme.textMuted)
                    Spacer()
                    Text(item.statusLabel)
                        .font(AppTheme.labelFont(10))
                        .foregroundStyle(item.statusColor)
                }

                Text(item.text)
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(item.status == "resolved" ? AppTheme.textMuted : AppTheme.textSecondary)
                    .strikethrough(item.status == "resolved", color: AppTheme.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 6)
        .padding(.horizontal, 8)
        .background(AppTheme.cardBackground.opacity(0.7))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func transcriptDetailsSection(_ response: BeforeAfterResponse) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Button {
                withAnimation(.easeInOut(duration: 0.18)) {
                    showTranscriptDetails.toggle()
                }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "doc.text")
                        .foregroundStyle(AppTheme.accent)
                    Text("文字起こし比較")
                        .font(AppTheme.sectionFont(15))
                        .foregroundStyle(.white)
                    Spacer()
                    Text("全行表示")
                        .font(AppTheme.labelFont(10))
                        .foregroundStyle(AppTheme.textMuted)
                    Image(systemName: showTranscriptDetails ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("before-after-transcript-toggle")

            if showTranscriptDetails {
                transcriptVersionPicker(response)
                transcriptStatsRow

                if isTranscriptReloading || isSupplementalLoading {
                    HStack(spacing: 8) {
                        ProgressView()
                            .scaleEffect(0.75)
                            .tint(AppTheme.accent)
                        Text("文字起こし差分を読み込み中")
                            .font(AppTheme.bodyFont(12))
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, 8)
                } else if let transcriptData, transcriptData.status == "ok", !transcriptData.segments.isEmpty {
                    transcriptLegend
                    LazyVStack(alignment: .leading, spacing: 6) {
                        ForEach(transcriptData.segments) { segment in
                            transcriptSegmentRow(segment)
                        }
                    }
                    .accessibilityIdentifier("before-after-transcript-full-list")
                } else {
                    Text(transcriptData?.message ?? "文字起こしデータがありません")
                        .font(AppTheme.bodyFont(12))
                        .foregroundStyle(AppTheme.textMuted)
                        .padding(.vertical, 8)
                }
            }
        }
        .padding(12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .accessibilityIdentifier("before-after-transcript-section")
    }

    private func transcriptVersionPicker(_ response: BeforeAfterResponse) -> some View {
        let versions = response.allVersions ?? []
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                if versions.isEmpty {
                    transcriptVersionPill("現行版", isSelected: true) {}
                } else {
                    ForEach(Array(versions.enumerated()), id: \.offset) { _, version in
                        let label = version.versionLabel?.isEmpty == false ? version.versionLabel! : (version.version ?? "現行版")
                        transcriptVersionPill(label, isSelected: selectedTranscriptVersion == label) {
                            selectedTranscriptVersion = label
                            Task { await reloadTranscriptDiff(version: label) }
                        }
                    }
                }
            }
        }
        .accessibilityIdentifier("before-after-transcript-version-picker")
    }

    private func transcriptVersionPill(_ label: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(label)
                .font(AppTheme.labelFont(11))
                .foregroundStyle(isSelected ? .white : AppTheme.textMuted)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(isSelected ? AppTheme.accent.opacity(0.38) : AppTheme.cardBackground)
                .clipShape(Capsule())
        }
        .buttonStyle(.plain)
    }

    private var transcriptStatsRow: some View {
        HStack(spacing: 8) {
            if let total = transcriptData?.totalSegments {
                transcriptStat("全\(total)行")
            }
            if let used = transcriptData?.usedCount {
                transcriptStat("採用 \(used)")
            }
            if let unused = transcriptData?.unusedCount {
                transcriptStat("CUT \(unused)")
            }
            if let highlights = transcriptData?.highlightCount, highlights > 0 {
                transcriptStat("FB \(highlights)")
            }
            if let punchlines = transcriptData?.punchlineCount, punchlines > 0 {
                transcriptStat("PL \(punchlines)")
            }
            if let ratio = transcriptData?.usedRatio {
                transcriptStat("採用率 \(ratio)")
            }
        }
        .accessibilityIdentifier("before-after-transcript-stats")
    }

    private var transcriptLegend: some View {
        HStack(spacing: 10) {
            transcriptLegendItem(color: Color.green.opacity(0.8), label: "採用")
            transcriptLegendItem(color: Color(hex: 0xFF6B35), label: "カット")
            transcriptLegendItem(color: AppTheme.accent, label: "FB修正")
            transcriptLegendItem(color: Color(hex: 0xFFD700), label: "パンチライン")
        }
        .padding(.vertical, 2)
        .accessibilityIdentifier("before-after-transcript-legend")
    }

    private func transcriptLegendItem(color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            RoundedRectangle(cornerRadius: 2)
                .fill(color)
                .frame(width: 10, height: 10)
            Text(label)
                .font(AppTheme.labelFont(9))
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    private func transcriptStat(_ text: String) -> some View {
        Text(text)
            .font(AppTheme.labelFont(10))
            .foregroundStyle(AppTheme.textSecondary)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(AppTheme.cardBackground)
            .clipShape(Capsule())
    }

    private func transcriptSegmentRow(_ segment: TranscriptSegment) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text("\(segment.lineNumber)")
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(AppTheme.textMuted.opacity(0.75))
                .frame(width: 36, alignment: .trailing)

            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(segment.statusLabel)
                        .font(AppTheme.labelFont(9))
                        .foregroundStyle(segment.statusColor)
                    if let matched = segment.matchedFeedback, !matched.isEmpty {
                        Text(matched)
                            .font(AppTheme.labelFont(9))
                            .foregroundStyle(AppTheme.textMuted)
                            .lineLimit(1)
                    }
                }
                Text(segment.text)
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(transcriptTextColor(for: segment))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 5)
        .padding(.horizontal, 8)
        .background(transcriptBackgroundColor(for: segment))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func transcriptTextColor(for segment: TranscriptSegment) -> Color {
        switch segment.status {
        case "used":
            return .white
        case "unused", "highlight", "punchline":
            return segment.statusColor
        default:
            return AppTheme.textMuted
        }
    }

    private func transcriptBackgroundColor(for segment: TranscriptSegment) -> Color {
        switch segment.status {
        case "used":
            return Color.green.opacity(0.06)
        case "unused", "highlight", "punchline":
            return segment.statusColor.opacity(0.12)
        default:
            return Color.clear
        }
    }

    private var transcriptSummaryText: String {
        guard let transcriptData else { return isSupplementalLoading ? "読込中" : "未取得" }
        if transcriptData.status == "ok" {
            return "\(transcriptData.segments.count)行"
        }
        return transcriptData.message ?? transcriptData.status
    }

    private var fbTrackerSummaryText: String {
        guard let fbTrackerData else { return isSupplementalLoading ? "読込中" : "未取得" }
        return "\(fbTrackerData.summary.resolved)/\(fbTrackerData.summary.total)対応済み"
    }

    @MainActor
    private func loadSummary() async {
        isLoading = true
        isSupplementalLoading = false
        transcriptData = nil
        fbTrackerData = nil
        updatingFBTrackerItemId = nil
        do {
            response = try await APIClient.shared.fetchBeforeAfter(projectId: projectId)
            if selectedTranscriptVersion == nil {
                selectedTranscriptVersion = response?.allVersions?.first?.versionLabel
                    ?? response?.allVersions?.first?.version
            }
            isLoading = false
            await loadSupplementalData()
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }

    @MainActor
    private func loadSupplementalData() async {
        isSupplementalLoading = true
        async let transcript: TranscriptDiffResponse? = try? APIClient.shared.fetchTranscriptDiff(projectId: projectId)
        async let tracker: FBTrackerResponse? = try? APIClient.shared.fetchFBTracker(projectId: projectId)
        let transcriptResult = await transcript
        transcriptData = transcriptResult
        if selectedTranscriptVersion == nil {
            selectedTranscriptVersion = transcriptResult?.compareVersion
        }
        fbTrackerData = await tracker
        isSupplementalLoading = false
    }

    @MainActor
    private func reloadTranscriptDiff(version: String) async {
        isTranscriptReloading = true
        defer { isTranscriptReloading = false }
        transcriptData = try? await APIClient.shared.fetchTranscriptDiff(projectId: projectId, version: version)
    }

    @MainActor
    private func toggleFBTrackerItem(_ item: FBTrackerItem) async {
        guard !item.uri.isEmpty else { return }
        updatingFBTrackerItemId = item.id
        defer { updatingFBTrackerItemId = nil }

        let newStatus = item.status == "resolved" ? "pending" : "resolved"
        do {
            try await APIClient.shared.updateFBTrackingStatus(
                projectId: projectId,
                commentUri: item.uri,
                status: newStatus
            )
            fbTrackerData = try await APIClient.shared.fetchFBTracker(projectId: projectId)
        } catch {
            fbTrackerData = try? await APIClient.shared.fetchFBTracker(projectId: projectId)
        }
    }
}
