import SwiftUI

// MARK: - カスタムタブバー付きルートビュー
struct RootTabView: View {
    @State private var selectedTab: Tab = .home
    @State private var showRecordingModal = false
    @State private var showKnowledgePages = false
    @StateObject private var voiceFeedbackVM = VoiceFeedbackViewModel()
    @StateObject private var projectListVM = ProjectListViewModel()
    @StateObject private var dashboardVM = DashboardViewModel()
    @StateObject private var feedbackHistoryVM = FeedbackHistoryViewModel()
    @StateObject private var knowledgePagesVM = KnowledgePagesViewModel()
    @ObservedObject private var apiClient = APIClient.shared

    enum Tab: Int, CaseIterable {
        case home, report, record, history, quality

        var label: String {
            switch self {
            case .home: return "ホーム"
            case .report: return "レポート"
            case .record: return "録音"
            case .history: return "履歴"
            case .quality: return "品質"
            }
        }

        var icon: String {
            switch self {
            case .home: return "house.fill"
            case .report: return "doc.text.fill"
            case .record: return "mic.fill"
            case .history: return "clock.fill"
            case .quality: return "chart.xyaxis.line"
            }
        }
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            VStack(spacing: 0) {
                // 接続ステータスバナー
                connectionStatusBanner

                Spacer(minLength: 0)
            }
            .zIndex(1)

            // メインコンテンツ
            Group {
                switch selectedTab {
                case .home:
                    ProjectListView(
                        viewModel: projectListVM,
                        onShowKnowledge: { showKnowledgePages = true }
                    )
                case .report:
                    NavigationStack {
                        ReportListView(viewModel: projectListVM)
                    }
                case .record:
                    // 録音タブ選択時はモーダルを表示（homeをバックに表示）
                    ProjectListView(
                        viewModel: projectListVM,
                        onShowKnowledge: { showKnowledgePages = true }
                    )
                case .history:
                    NavigationStack {
                        FeedbackHistoryView(viewModel: feedbackHistoryVM)
                    }
                case .quality:
                    NavigationStack {
                        QualityDashboardView(viewModel: dashboardVM)
                    }
                }
            }
            .padding(.bottom, 80) // タブバー分の余白

            // カスタムタブバー
            customTabBar
        }
        .ignoresSafeArea(.keyboard)
        .fullScreenCover(isPresented: $showRecordingModal) {
            VoiceFeedbackView(viewModel: voiceFeedbackVM)
        }
        .fullScreenCover(isPresented: $showKnowledgePages) {
            NavigationStack {
                KnowledgePagesView(viewModel: knowledgePagesVM)
                    .toolbar {
                        ToolbarItem(placement: .topBarLeading) {
                            Button {
                                showKnowledgePages = false
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: "chevron.left")
                                    Text("戻る")
                                }
                                .foregroundStyle(AppTheme.accent)
                            }
                        }
                    }
            }
        }
    }

    // MARK: - カスタムタブバー（中央録音ボタン大きめ）
    private var customTabBar: some View {
        HStack(spacing: 0) {
            ForEach(Tab.allCases, id: \.rawValue) { tab in
                if tab == .record {
                    // 中央の録音ボタン（大きめ）
                    Button {
                        showRecordingModal = true
                    } label: {
                        ZStack {
                            Circle()
                                .fill(Color.white.opacity(0.08))
                                .frame(width: 66, height: 66)
                                .blur(radius: 2)

                            Circle()
                                .fill(
                                    LinearGradient(
                                        colors: [Color(hex: 0xFF4D57), AppTheme.accent],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    )
                                )
                                .frame(width: 56, height: 56)
                                .shadow(color: AppTheme.accentGlow, radius: 8, x: 0, y: 2)
                                .shadow(color: .black.opacity(0.45), radius: 14, x: 0, y: 8)
                                .overlay(
                                    Circle()
                                        .strokeBorder(Color.white.opacity(0.18), lineWidth: 1)
                                )

                            Image(systemName: "mic.fill")
                                .font(.system(size: 24, weight: .bold))
                                .foregroundStyle(.white)
                                .shadow(color: .black.opacity(0.25), radius: 2, x: 0, y: 1)
                        }
                        .offset(y: -16)
                    }
                    .frame(maxWidth: .infinity)
                } else {
                    Button {
                        selectedTab = tab
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: tab.icon)
                                .font(.system(size: 18))
                            Text(tab.label)
                                .font(AppTheme.labelFont(9))
                        }
                        .foregroundStyle(selectedTab == tab ? .white : AppTheme.textMuted)
                        .frame(maxWidth: .infinity)
                    }
                }
            }
        }
        .padding(.horizontal, 8)
        .padding(.top, 8)
        .padding(.bottom, 24)
        .background(
            Rectangle()
                .fill(AppTheme.cardBackground)
                .shadow(color: .black.opacity(0.5), radius: 10, y: -2)
                .ignoresSafeArea(edges: .bottom)
        )
    }

    // MARK: - 接続ステータスバナー
    @ViewBuilder
    private var connectionStatusBanner: some View {
        switch apiClient.connectionStatus {
        case .disconnected:
            HStack(spacing: 8) {
                Image(systemName: "wifi.slash")
                    .font(.system(size: 14, weight: .semibold))
                Text("サーバーに接続できません")
                    .font(.system(size: 13, weight: .medium))
                Spacer()
                Button {
                    Task {
                        await APIClient.shared.probeAndConnect()
                    }
                } label: {
                    Text("再接続")
                        .font(.system(size: 12, weight: .bold))
                        .padding(.horizontal, 12)
                        .padding(.vertical, 4)
                        .background(Color.white.opacity(0.2))
                        .clipShape(Capsule())
                }
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color.red.opacity(0.85))
        case .connecting:
            HStack(spacing: 8) {
                ProgressView()
                    .progressViewStyle(.circular)
                    .scaleEffect(0.7)
                    .tint(.white)
                Text("接続中...")
                    .font(.system(size: 13, weight: .medium))
                Spacer()
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 16)
            .padding(.vertical, 6)
            .background(Color.orange.opacity(0.75))
        case .connected:
            EmptyView()
        }
    }
}
