import SwiftUI

// MARK: - 画面2: ディレクションレポート詳細
struct DirectionReportView: View {
    var project: VideoProject?
    @State private var selectedTab = 0
    @State private var expandedSections: Set<UUID> = []

    // デフォルトプロジェクト（直接遷移用）
    private var displayProject: VideoProject {
        project ?? MockData.projects.first!
    }

    private let tabTitles = ["演出", "テロップ", "カメラ", "音声FB"]

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 0) {
                // ヘッダー
                headerSection

                // タブ切替
                tabSelector

                // セクション内容
                sectionContent

                Spacer(minLength: 100)
            }
        }
        .background(AppTheme.background.ignoresSafeArea())
        .overlay(alignment: .bottom) {
            // 下部固定: 音声FBボタン
            bottomActionBar
        }
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - ヘッダー
    private var headerSection: some View {
        VStack(spacing: 0) {
            // カバー画像エリア
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

                // グラデーション
                LinearGradient(
                    colors: [.clear, AppTheme.background],
                    startPoint: .center,
                    endPoint: .bottom
                )
                .frame(height: 100)
                .frame(maxHeight: .infinity, alignment: .bottom)
            }

            // ゲスト情報
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

                // Vimeoリンク
                HStack {
                    Button {
                        // モック: Vimeoレビューへ遷移
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

    // MARK: - タブセレクター
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
                        .frame(width: 80)
                    }
                }
            }
            .padding(.horizontal, 20)
        }
        .padding(.top, 20)
    }

    // MARK: - セクション内容
    private var sectionContent: some View {
        VStack(spacing: 12) {
            let filteredSections: [ReportSection] = {
                if selectedTab < MockData.reportSections.count {
                    return [MockData.reportSections[selectedTab]]
                }
                return []
            }()

            ForEach(filteredSections) { section in
                expandableSection(section)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 16)
    }

    // MARK: - 折りたたみセクション（Netflix「詳細」風）
    private func expandableSection(_ section: ReportSection) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // ヘッダー（タップで展開/折りたたみ）
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

            // コンテンツ（デフォルト展開）
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

    // MARK: - 下部固定アクションバー
    private var bottomActionBar: some View {
        HStack(spacing: 16) {
            Button {
                // モック: 音声FB追加
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
