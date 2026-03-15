import SwiftUI

struct RootTabView: View {
    var body: some View {
        TabView {
            NavigationStack {
                ProjectListView(viewModel: ProjectListViewModel())
            }
            .tabItem {
                Label("案件", systemImage: "rectangle.stack.fill")
            }

            NavigationStack {
                DirectionReportView()
            }
            .tabItem {
                Label("レポート", systemImage: "doc.text.fill")
            }

            NavigationStack {
                VoiceFeedbackView(viewModel: VoiceFeedbackViewModel())
            }
            .tabItem {
                Label("音声FB", systemImage: "mic.fill")
            }

            NavigationStack {
                FeedbackHistoryView()
            }
            .tabItem {
                Label("履歴", systemImage: "clock.arrow.trianglehead.counterclockwise.rotate.90")
            }

            NavigationStack {
                QualityDashboardView(viewModel: DashboardViewModel())
            }
            .tabItem {
                Label("品質", systemImage: "chart.xyaxis.line")
            }
        }
        .background(AppTheme.background.ignoresSafeArea())
    }
}
