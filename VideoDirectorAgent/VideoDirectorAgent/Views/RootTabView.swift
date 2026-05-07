import SwiftUI

// MARK: - カスタムタブバー付きルートビュー
struct RootTabView: View {
    (\.scenePhase) private var scenePhase
    @State private var selectedTab: Tab = .home
    @State private var showRecordingModal = false
    @State private var showKnowledgePages = false
    @StateObject private var voiceFeedbackVM = VoiceFeedbackViewModel()
    @StateObject private var projectListVM = ProjectListViewModel()
    @StateObject private var dashboardVM = DashboardViewModel()
    @StateObject private var feedbackApprovalVM = FeedbackApprovalViewModel()
    @StateObject private var knowledgePagesVM = KnowledgePagesViewModel()
    @ObservedObject private var apiClient = APIClient.shared

    /// バナー表示用のデバウンスされた接続ステータス
    /// 通常の再接続中は何も出さず、継続的な切断だけを表示する
    @State private var displayedStatus: APIClient.ConnectionStatus = .connected("未確認")
    /// バナー表示デバウンス用タスク
    @State private var bannerDebounceTask: Task<Void, Never>?

    enum Tab: Int, CaseIterable {
        case home, report, record, approval, quality

        var label: String {
            switch self {
            case .home: return "ホーム"
            case .report: return "レポート"
            case .record: return "録音"
            case .approval: return "FB承認"
            case .quality: return "品質"
            }
        }

        var icon: String {
            switch self {
            case .home: return "house.fill"
            case .report: return "doc.text.fill"
            case .record: return "mic.fill"
            case .approval: return "checkmark.shield.fill"
            case .quality: return "chart.xyaxis.line"
            }
        }
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            VStack(spacing: 0) {
                // 接続ステータスバナー（デバウンス済みステータスに基づき表示）
                connectionStatusBanner

                Spacer(minLength: 0)
            }
            .animation(.easeInOut(duration: 0.5), value: displayedStatus)
            .zIndex(1)

            // メインコンテンツ
            tabContent
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
        .task {
            // アプリ起動時に承認待ちFB件数とプロジェクト一覧を取得
            await feedbackApprovalVM.fetchPending()
            await projectListVM.refreshIfStale(maxAge: 0)
        }
        .onChange(of: selectedTab) { _, newTab in
            if newTab == .home || newTab == .report {
                Task {
                    await projectListVM.refreshIfStale(maxAge: 30)
                }
            }
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                Task {
                    await projectListVM.refreshIfStale(maxAge: 30)
                    await feedbackApprovalVM.fetchPending()
                }
            }
        }
        .onChange(of: apiClient.connectionStatus) { _, newStatus in
            // バナー表示のデバウンス: disconnectedへの遷移は12秒遅延
            // connectedへの復帰は即座に反映（バナーをすぐ消す）
            // モバイル通信での一時的なprobe失敗でバナーが出たり消えたりするのを根本的に防止
            bannerDebounceTask?.cancel()
            switch newStatus {
            case .connected:
                // connected復帰は即座にバナーを消す
                displayedStatus = newStatus
            case .disconnected:
                // 12秒間disconnectedが持続した場合のみバナー表示
                // 12秒以内にconnectedに戻ればバナーは出ない
                bannerDebounceTask = Task {
                    try? await Task.sleep(nanoseconds: 12_000_000_000)
                    guard !Task.isCancelled else { return }
                    // 最終チェック: この時点でまだdisconnectedかどうか
                    if case .disconnected = apiClient.connectionStatus {
                        displayedStatus = newStatus
                    }
                }
            case .connecting:
                // 起動・復帰・サイレント再接続中は業務上の異常ではないので帯を出さない
                displayedStatus = .connected("再接続確認中")
            }
        }
    }

    // MARK: - タブ別メインコンテンツ
    @ViewBuilder
    private var tabContent: some View {
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
        case .approval:
            NavigationStack {
                FeedbackApprovalListView(viewModel: feedbackApprovalVM)
            }
        case .quality:
            NavigationStack {
                QualityDashboardView(viewModel: dashboardVM)
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
                        ZStack(alignment: .topTrailing) {
                            VStack(spacing: 4) {
                                Image(systemName: tab.icon)
                                    .font(.system(size: 18))
                                Text(tab.label)
                                    .font(AppTheme.labelFont(9))
                            }
                            .foregroundStyle(selectedTab == tab ? .white : AppTheme.textMuted)
                            .frame(maxWidth: .infinity)

                            // FB承認タブに未承認件数バッジを表示
                            if tab == .approval && feedbackApprovalVM.pendingCount > 0 {
                                Text("\(feedbackApprovalVM.pendingCount)")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundStyle(.white)
                                    .frame(minWidth: 16, minHeight: 16)
                                    .background(AppTheme.accent)
                                    .clipShape(Circle())
                                    .offset(x: -8, y: -2)
                            }
                        }
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
        // 初回接続が完了するまではバナーを一切表示しない
        // アプリ起動直後の「接続中...」表示を抑制
        if !apiClient.hasEverConnected {
            EmptyView()
        } else {
            // displayedStatus（デバウンス済み）に基づいて表示
            // connectionStatusの急速な変化によるチラつきを完全に防止
            switch displayedStatus {
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
                .transition(.move(edge: .top).combined(with: .opacity))
            case .connecting:
                EmptyView()
            case .connected:
                EmptyView()
            }
        }
    }
}
