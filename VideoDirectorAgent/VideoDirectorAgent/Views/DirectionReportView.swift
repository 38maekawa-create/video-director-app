import SwiftUI

// MARK: - 画面2: ディレクションレポート詳細
struct DirectionReportView: View {
    var project: VideoProject?
    @State private var selectedTab = 0
    @State private var expandedSections: Set<UUID> = []
    @State private var feedbacks: [FeedbackItem] = []
    @State private var isFeedbackLoading = false
    @State private var showVoiceFeedback = false

    private var displayProject: VideoProject {
        if let project { return project }
        // 本番: projectがnilの場合はプレースホルダーを返す
        return VideoProject(
            id: "placeholder",
            guestName: "読み込み中...",
            title: "プロジェクト未選択",
            shootDate: "",
            status: .directed
        )
    }

    private let tabTitles = ["概要", "ディレクション", "YouTube素材", "素材", "編集後", "FB・評価", "ナレッジ"]

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
            VoiceFeedbackView(projectId: displayProject.id)
        }
    }

    private var headerSection: some View {
        VStack(spacing: 0) {
            ZStack(alignment: .bottomLeading) {
                ZStack {
                    LinearGradient(
                        colors: [displayProject.status.color.opacity(0.3), AppTheme.cardBackground],
                        startPoint: .topTrailing,
                        endPoint: .bottomLeading
                    )
                    Image(systemName: displayProject.thumbnailSymbol)
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
                Text(displayProject.guestName)
                    .font(AppTheme.heroFont(30))
                    .foregroundStyle(.white)

                Text(displayProject.title)
                    .font(AppTheme.titleFont(20))
                    .foregroundStyle(AppTheme.textSecondary)
                    .tracking(1)

                HStack(spacing: 16) {
                    if let age = displayProject.guestAge {
                        Label("\(age)歳", systemImage: "person.fill")
                    }
                    if let occupation = displayProject.guestOccupation {
                        Label(occupation, systemImage: "briefcase.fill")
                    }
                    Label(displayProject.shootDate, systemImage: "calendar")
                }
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)

                HStack {
                    Button {
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "play.circle.fill")
                            Text("Vimeoレビューを開く")
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
                                .strokeBorder(AppTheme.textMuted.opacity(0.3), lineWidth: 1)
                        )
                    }

                    if let score = displayProject.qualityScore {
                        Spacer()
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
                YouTubeAssetsView(projectId: displayProject.id)
            case 3:
                sourceVideoSection
            case 4:
                editedVideoSection
            case 5:
                feedbackListSection
            case 6:
                knowledgeDetailSection
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
                    "ゲスト: \(displayProject.guestName)",
                    displayProject.guestAge.map { "年齢: \($0)歳" } ?? "年齢: 未設定",
                    displayProject.guestOccupation.map { "職業: \($0)" } ?? "職業: 未設定",
                    "撮影日: \(displayProject.shootDate)",
                    "状態: \(displayProject.status.label)",
                    "品質スコア: \(displayProject.qualityScore.map(String.init) ?? "未算出")"
                ]
            )
            overviewCard(
                title: "進行サマリー",
                icon: "chart.bar.xaxis",
                items: [
                    "未レビュー: \(displayProject.unreviewedCount)件",
                    "未送信FB: \(displayProject.hasUnsentFeedback ? "あり" : "なし")"
                ]
            )
            pdcaCard
        }
    }

    private var directionReportSection: some View {
        Group {
            if let urlString = displayProject.directionReportURL,
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

    private var sourceVideoSection: some View {
        VStack(spacing: 12) {
            overviewCard(
                title: "撮影素材",
                icon: "video.badge.waveform",
                items: [
                    "ゲスト: \(displayProject.guestName)",
                    "撮影日: \(displayProject.shootDate)"
                ]
            )
            if let url = displayProject.sourceVideoURL,
               !url.isEmpty,
               let destination = URL(string: url) {
                Link(destination: destination) {
                    HStack {
                        Image(systemName: "play.rectangle.fill")
                        Text("素材動画を開く（Vimeo）")
                    }
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(Color(hex: 0x1AB7EA))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            } else {
                overviewCard(
                    title: "素材動画",
                    icon: "exclamationmark.triangle",
                    items: ["素材動画URLが未登録です"]
                )
            }
        }
    }

    private var editedVideoSection: some View {
        VStack(spacing: 12) {
            if let url = displayProject.editedVideoURL,
               !url.isEmpty,
               let destination = URL(string: url) {
                overviewCard(
                    title: "編集後動画",
                    icon: "sparkles.rectangle.stack",
                    items: ["編集完了。レビュー可能な状態です。"]
                )
                Link(destination: destination) {
                    HStack {
                        Image(systemName: "play.rectangle.fill")
                        Text("編集後動画を開く")
                    }
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(AppTheme.statusComplete)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
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
        .task(id: displayProject.id) {
            await loadFeedbacks()
        }
    }

    private var knowledgeDetailSection: some View {
        VStack(spacing: 12) {
            if let knowledge = displayProject.knowledge, !knowledge.isEmpty {
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
                pdcaStep("C", "編集", completed: displayProject.editedVideoURL != nil)
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
            feedbacks = try await APIClient.shared.fetchFeedbacks(projectId: displayProject.id)
        } catch {
            feedbacks = []
        }
    }
}
