import SwiftUI

// MARK: - 画面2: ディレクションレポート詳細
struct DirectionReportView: View {
    var project: VideoProject?
    @State private var selectedTab = 0
    @State private var expandedSections: Set<UUID> = []

    private var displayProject: VideoProject {
        project ?? MockData.projects.first!
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
                expandableSection(MockData.reportSections[0])
            case 2:
                YouTubeAssetsView(projectId: displayProject.id)
            case 3:
                expandableSection(MockData.reportSections[2])
            case 4:
                editedSection
            case 5:
                feedbackSection
            case 6:
                knowledgeSection
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
                    "撮影日: \(displayProject.shootDate)",
                    "状態: \(displayProject.status.label)"
                ]
            )
            overviewCard(
                title: "進行サマリー",
                icon: "chart.bar.xaxis",
                items: [
                    "未レビュー: \(displayProject.unreviewedCount)件",
                    "未送信FB: \(displayProject.hasUnsentFeedback ? "あり" : "なし")",
                    "品質スコア: \(displayProject.qualityScore.map(String.init) ?? "未算出")"
                ]
            )
        }
    }

    private var editedSection: some View {
        overviewCard(
            title: "編集後レビュー",
            icon: "sparkles.rectangle.stack",
            items: [
                "編集後タブは Phase 2 で詳細連携予定",
                "本フェーズでは YouTube素材の閲覧・編集を優先",
                "Vimeoレビュー導線はヘッダーから遷移"
            ]
        )
    }

    private var feedbackSection: some View {
        VStack(spacing: 12) {
            expandableSection(MockData.reportSections[3])
            overviewCard(
                title: "評価メモ",
                icon: "checkmark.seal",
                items: [
                    "音声FBの要点を YouTube素材に反映可能",
                    "次フェーズでリアルタイム同期と評価連携を追加"
                ]
            )
        }
    }

    private var knowledgeSection: some View {
        overviewCard(
            title: "ナレッジ連携",
            icon: "books.vertical",
            items: [
                "本案件のディレクション知見は AI開発5 の素材知見と接続予定",
                "ネイティブアプリ Phase 1 では閲覧の土台のみ構築",
                "Phase 2 以降で関連ナレッジページ埋め込みへ拡張"
            ]
        )
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

    private var bottomActionBar: some View {
        HStack(spacing: 16) {
            Button {
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
}
