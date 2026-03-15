import SwiftUI

// MARK: - 画面1: プロジェクト一覧（ホーム）— Netflix風
struct ProjectListView: View {
    @ObservedObject var viewModel: ProjectListViewModel
    @State private var searchText = ""

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 0) {
                // ヒーローバナー
                if let hero = viewModel.heroProject {
                    NavigationLink(value: hero) {
                        heroSection(hero)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }

                // 検索バー
                searchBar

                // カルーセルセクション群
                VStack(spacing: 24) {
                    // 最近のフィードバック
                    if !viewModel.recentFeedbackProjects.isEmpty {
                        carouselSection(
                            title: "最近のフィードバック",
                            icon: "bubble.left.fill",
                            projects: viewModel.recentFeedbackProjects
                        )
                    }

                    // 要対応
                    if !viewModel.actionRequiredProjects.isEmpty {
                        carouselSection(
                            title: "要対応",
                            icon: "exclamationmark.triangle.fill",
                            projects: viewModel.actionRequiredProjects
                        )
                    }

                    // 全プロジェクト
                    carouselSection(
                        title: "全プロジェクト",
                        icon: "film.stack.fill",
                        projects: viewModel.filteredProjects
                    )
                }
                .padding(.bottom, 32)
            }
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("VIDEO DIRECTOR")
                    .font(AppTheme.heroFont(20))
                    .foregroundStyle(AppTheme.accent)
                    .tracking(4)
            }
        }
        .refreshable {
            await viewModel.refresh()
        }
        .task {
            await viewModel.loadProjectsIfNeeded()
        }
        .onChange(of: searchText) { _, newValue in
            viewModel.searchText = newValue
        }
        .navigationDestination(for: VideoProject.self) { project in
            DirectionReportView(project: project)
        }
    }

    // MARK: - ヒーローバナー
    @ViewBuilder
    private func heroSection(_ project: VideoProject) -> some View {
        ZStack(alignment: .bottomLeading) {
            // 背景グラデーション（サムネイル代替）
            ZStack {
                LinearGradient(
                    colors: [AppTheme.accent.opacity(0.3), AppTheme.cardBackground],
                    startPoint: .topTrailing,
                    endPoint: .bottomLeading
                )

                Image(systemName: project.thumbnailSymbol)
                    .font(.system(size: 80))
                    .foregroundStyle(.white.opacity(0.1))
            }
            .frame(height: 280)

            // 下部グラデーション（テキスト読みやすさ確保）
            LinearGradient(
                colors: [.clear, AppTheme.background],
                startPoint: .top,
                endPoint: .bottom
            )
            .frame(height: 160)
            .frame(maxHeight: .infinity, alignment: .bottom)

            // テキストオーバーレイ
            VStack(alignment: .leading, spacing: 8) {
                Text("最新プロジェクト")
                    .font(AppTheme.labelFont(11))
                    .foregroundStyle(AppTheme.accent)
                    .textCase(.uppercase)
                    .tracking(2)

                Text(project.guestName)
                    .font(.system(size: 36, weight: .bold, design: .serif))
                    .tracking(3)
                    .foregroundStyle(.white)

                Text(project.title)
                    .font(AppTheme.titleFont(20))
                    .foregroundStyle(AppTheme.textSecondary)
                    .tracking(1)

                if let errorMessage = viewModel.errorMessage {
                    Text(errorMessage)
                        .font(.caption)
                        .foregroundStyle(AppTheme.textSecondary)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(AppTheme.cardBackground.opacity(0.85))
                        .clipShape(Capsule())
                }

                HStack(spacing: 12) {
                    Label(project.shootDate, systemImage: "calendar")
                    if let score = project.qualityScore {
                        Label("スコア \(score)", systemImage: "chart.bar.fill")
                    }
                }
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)

                // ステータスバッジ
                HStack(spacing: 8) {
                    statusBadge(project.status)
                    if project.unreviewedCount > 0 {
                        Text("未レビュー \(project.unreviewedCount)")
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundStyle(.black)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 5)
                            .background(AppTheme.accent)
                            .clipShape(Capsule())
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 20)
        }
    }

    // MARK: - 検索バー
    private var searchBar: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(AppTheme.textMuted)
            TextField("プロジェクト名、ゲスト名、日付で検索", text: $searchText)
                .foregroundStyle(.white)
                .autocorrectionDisabled()
        }
        .padding(12)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    // MARK: - カルーセルセクション
    @ViewBuilder
    private func carouselSection(title: String, icon: String, projects: [VideoProject]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .foregroundStyle(AppTheme.accent)
                Text(title)
                    .font(AppTheme.sectionFont(17))
                    .foregroundStyle(.white)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }
            .padding(.horizontal, 16)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(projects) { project in
                        NavigationLink(value: project) {
                            projectCard(project)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 16)
            }
        }
    }

    // MARK: - プロジェクトカード（Netflix風サムネイル）
    private func projectCard(_ project: VideoProject) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            // サムネイル
            ZStack(alignment: .bottomLeading) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(
                            LinearGradient(
                                colors: [AppTheme.cardBackground, project.status.color.opacity(0.2)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )

                    Image(systemName: project.thumbnailSymbol)
                        .font(.system(size: 32))
                        .foregroundStyle(.white.opacity(0.3))
                }
                .frame(width: 150, height: 100)

                // プログレスバー（スコア表示）
                if let score = project.qualityScore {
                    GeometryReader { geo in
                        VStack {
                            Spacer()
                            Rectangle()
                                .fill(AppTheme.accent)
                                .frame(width: geo.size.width * CGFloat(score) / 100.0, height: 3)
                        }
                    }
                    .frame(width: 150, height: 100)
                    .allowsHitTesting(false)
                }

                // 未送信バッジ
                if project.hasUnsentFeedback {
                    Circle()
                        .fill(AppTheme.accent)
                        .frame(width: 10, height: 10)
                        .offset(x: 138, y: -88)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 8))

            // タイトル＋情報
            Text(project.guestName)
                .font(.system(size: 14, weight: .bold, design: .serif))
                .tracking(1.5)
                .foregroundStyle(.white)
                .lineLimit(1)

            if let occupation = project.guestOccupation, !occupation.isEmpty {
                Text(occupation)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textSecondary)
                    .lineLimit(1)
            }

            Text(project.shootDate)
                .font(.caption2)
                .foregroundStyle(AppTheme.textMuted)
        }
        .frame(width: 150)
    }

    // MARK: - ステータスバッジ
    private func statusBadge(_ status: ProjectStatus) -> some View {
        Text(status.label)
            .font(.caption)
            .fontWeight(.medium)
            .foregroundStyle(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(status.color.opacity(0.3))
            .clipShape(Capsule())
            .overlay(
                Capsule()
                    .strokeBorder(status.color.opacity(0.5), lineWidth: 1)
            )
    }
}
