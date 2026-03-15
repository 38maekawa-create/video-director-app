import SwiftUI

/// レポートタブ: 全プロジェクトを縦リストで表示し、各プロジェクトの詳細に遷移
struct ReportListView: View {
    @ObservedObject var viewModel: ProjectListViewModel
    @State private var searchText = ""

    var body: some View {
        List {
            if viewModel.isLoading {
                HStack {
                    Spacer()
                    ProgressView("読み込み中...")
                        .foregroundStyle(.white)
                    Spacer()
                }
                .listRowBackground(AppTheme.cardBackground)
            } else if let error = viewModel.errorMessage {
                Text(error)
                    .foregroundStyle(.red)
                    .font(.caption)
                    .listRowBackground(AppTheme.cardBackground)
            } else {
                ForEach(filteredProjects) { project in
                    NavigationLink {
                        DirectionReportView(project: project)
                    } label: {
                        reportRow(project)
                    }
                    .listRowBackground(AppTheme.cardBackground)
                }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(AppTheme.background.ignoresSafeArea())
        .navigationTitle("レポート一覧")
        .searchable(text: $searchText, prompt: "プロジェクト検索")
        .task {
            await viewModel.loadProjectsIfNeeded()
        }
        .refreshable {
            await viewModel.refresh()
        }
    }

    private var filteredProjects: [VideoProject] {
        if searchText.isEmpty { return viewModel.projects }
        return viewModel.projects.filter {
            $0.guestName.localizedCaseInsensitiveContains(searchText) ||
            $0.title.localizedCaseInsensitiveContains(searchText)
        }
    }

    private func reportRow(_ project: VideoProject) -> some View {
        HStack(spacing: 12) {
            // アイコン
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(project.status.color.opacity(0.15))
                    .frame(width: 44, height: 44)
                Image(systemName: project.thumbnailSymbol)
                    .font(.system(size: 18))
                    .foregroundStyle(project.status.color)
            }

            // 情報
            VStack(alignment: .leading, spacing: 4) {
                Text(project.guestName)
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(.white)

                HStack(spacing: 8) {
                    Text(project.shootDate)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)

                    if let score = project.qualityScore {
                        HStack(spacing: 2) {
                            Image(systemName: "chart.bar.fill")
                            Text("\(score)")
                        }
                        .font(.caption2)
                        .foregroundStyle(score >= 80 ? AppTheme.statusComplete : AppTheme.accent)
                    }

                    Text(project.status.label)
                        .font(.caption2)
                        .foregroundStyle(project.status.color)
                }
            }

            Spacer()

            // レポートURLの有無
            if project.directionReportURL != nil {
                Image(systemName: "doc.text.fill")
                    .font(.caption)
                    .foregroundStyle(AppTheme.statusComplete)
            }

            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)
        }
        .padding(.vertical, 4)
    }
}
