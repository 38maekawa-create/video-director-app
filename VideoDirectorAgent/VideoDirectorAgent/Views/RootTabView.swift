import SwiftUI

// MARK: - カスタムタブバー付きルートビュー
struct RootTabView: View {
    @State private var selectedTab: Tab = .home
    @State private var showRecordingModal = false
    @StateObject private var voiceFeedbackVM = VoiceFeedbackViewModel()

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
            // メインコンテンツ
            Group {
                switch selectedTab {
                case .home:
                    NavigationStack {
                        ProjectListView(viewModel: ProjectListViewModel())
                    }
                case .report:
                    NavigationStack {
                        DirectionReportView()
                    }
                case .record:
                    // 録音タブ選択時はモーダルを表示
                    NavigationStack {
                        ProjectListView(viewModel: ProjectListViewModel())
                    }
                case .history:
                    NavigationStack {
                        FeedbackHistoryView()
                    }
                case .quality:
                    NavigationStack {
                        QualityDashboardView(viewModel: DashboardViewModel())
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
                                .fill(AppTheme.accent)
                                .frame(width: 56, height: 56)
                                .shadow(color: AppTheme.accentGlow, radius: 8, x: 0, y: 2)

                            Image(systemName: "mic.fill")
                                .font(.system(size: 24, weight: .bold))
                                .foregroundStyle(.white)
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
}
