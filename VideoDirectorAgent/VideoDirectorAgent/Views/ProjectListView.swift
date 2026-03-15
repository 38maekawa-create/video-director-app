import SwiftUI

struct ProjectListView: View {
    @ObservedObject var viewModel: ProjectListViewModel

    var body: some View {
        List {
            ForEach(viewModel.projects) { project in
                ProjectCard(project: project)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .navigationTitle("プロジェクト一覧")
    }
}

private struct ProjectCard: View {
    let project: VideoProject

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(AppTheme.card)
                    .frame(width: 74, height: 74)
                Image(systemName: project.thumbnailSymbol)
                    .font(.system(size: 28))
                    .foregroundStyle(AppTheme.accent)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text(project.title)
                    .font(.headline)
                    .foregroundStyle(.white)

                HStack(spacing: 8) {
                    Text(project.status.rawValue)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(project.status.color.opacity(0.22))
                        .clipShape(Capsule())

                    if project.unreviewedCount > 0 {
                        Text("未レビュー \(project.unreviewedCount)")
                            .font(.caption)
                            .bold()
                            .foregroundStyle(.black)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(.yellow)
                            .clipShape(Capsule())
                    }
                }
            }
            Spacer()
        }
        .padding(12)
        .background(AppTheme.card.opacity(0.9))
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}
