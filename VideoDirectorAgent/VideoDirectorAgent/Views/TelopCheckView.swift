import SwiftUI

/// テロップチェック画面
struct TelopCheckView: View {
    @ObservedObject var viewModel: TelopCheckViewModel
    let projects: [VideoProject]

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 20) {
                // プロジェクト選択
                projectSelector

                // 実行ボタン
                executeButton

                // ローディング
                if viewModel.isRunning {
                    VStack(spacing: 12) {
                        ProgressView()
                            .tint(AppTheme.accent)
                        Text("テロップチェック実行中...")
                            .font(.caption)
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 24)
                }

                // エラーメッセージ
                if let error = viewModel.errorMessage {
                    errorBanner(error)
                }

                // 結果表示
                if let result = viewModel.result {
                    summaryCard(result)
                    issuesList
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 40)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("テロップチェック")
                    .font(AppTheme.heroFont(17))
                    .foregroundStyle(.white)
                    .tracking(1)
            }
        }
    }

    // MARK: - プロジェクト選択
    private var projectSelector: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "textformat.alt")
                    .foregroundStyle(AppTheme.accent)
                Text("プロジェクト選択")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(projects) { project in
                        Button {
                            viewModel.selectedProjectId = project.id
                            Task { await viewModel.fetchCachedResult() }
                        } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(project.guestName)
                                    .font(.caption)
                                    .fontWeight(.bold)
                                    .foregroundStyle(
                                        viewModel.selectedProjectId == project.id ? .white : AppTheme.textSecondary
                                    )
                                Text(project.shootDate)
                                    .font(.caption2)
                                    .foregroundStyle(AppTheme.textMuted)
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                            .background(
                                viewModel.selectedProjectId == project.id
                                    ? AppTheme.accent.opacity(0.3)
                                    : AppTheme.cardBackgroundLight
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .strokeBorder(
                                        viewModel.selectedProjectId == project.id
                                            ? AppTheme.accent : Color.clear,
                                        lineWidth: 1
                                    )
                            )
                        }
                    }
                }
                .padding(.horizontal, 2)
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 実行ボタン
    private var executeButton: some View {
        Button {
            Task { await viewModel.runCheck() }
        } label: {
            HStack(spacing: 10) {
                if viewModel.isRunning {
                    ProgressView()
                        .tint(.white)
                } else {
                    Image(systemName: "checkmark.shield.fill")
                }
                Text(viewModel.isRunning ? "チェック中..." : "テロップチェック実行")
                    .fontWeight(.bold)
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(
                viewModel.selectedProjectId.isEmpty || viewModel.isRunning
                    ? AppTheme.textMuted.opacity(0.3)
                    : AppTheme.accent
            )
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .disabled(viewModel.selectedProjectId.isEmpty || viewModel.isRunning)
    }

    // MARK: - サマリーカード
    private func summaryCard(_ result: TelopCheckResponse) -> some View {
        VStack(spacing: 16) {
            // 総合スコア
            if let score = viewModel.overallScore {
                VStack(spacing: 8) {
                    Text("テロップ品質スコア")
                        .font(AppTheme.labelFont(13))
                        .foregroundStyle(AppTheme.textMuted)
                        .tracking(2)
                    Text("\(Int(score))")
                        .font(AppTheme.heroFont(56))
                        .foregroundStyle(scoreColor(Int(score)))
                }
            }

            // エラー・警告カウント
            HStack(spacing: 20) {
                countBadge(
                    icon: "xmark.circle.fill",
                    label: "エラー",
                    count: viewModel.errorCount,
                    color: AppTheme.accent
                )
                countBadge(
                    icon: "exclamationmark.triangle.fill",
                    label: "警告",
                    count: viewModel.warningCount,
                    color: Color(hex: 0xF5A623)
                )
                if let frameCheck = result.frameCheck {
                    countBadge(
                        icon: "text.viewfinder",
                        label: "テロップ",
                        count: frameCheck.totalTelopsFound,
                        color: Color(hex: 0x4A90D9)
                    )
                }
            }

            // チェック日時
            if let checkedAt = result.checkedAt {
                Text("チェック日時: \(checkedAt)")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func countBadge(icon: String, label: String, count: Int, color: Color) -> some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundStyle(color)
            Text("\(count)")
                .font(.system(size: 22, weight: .heavy, design: .rounded))
                .foregroundStyle(.white)
            Text(label)
                .font(.caption2)
                .foregroundStyle(AppTheme.textMuted)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - 問題リスト
    private var issuesList: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "list.bullet.clipboard.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("検出された問題")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(viewModel.allIssues.count)件")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }

            if viewModel.allIssues.isEmpty {
                Text("問題は検出されませんでした")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
            } else {
                ForEach(viewModel.allIssues) { issue in
                    issueRow(issue)
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func issueRow(_ issue: TelopIssue) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: issue.severityIcon)
                .foregroundStyle(issue.severityColor)
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(issue.type.uppercased())
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundStyle(issue.severityColor)
                    Text(issue.severity.uppercased())
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(issue.severityColor.opacity(0.3))
                        .clipShape(Capsule())
                }

                Text(issue.description)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textSecondary)

                if let location = issue.location, !location.isEmpty {
                    Text("場所: \(location)")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                }

                if let suggestion = issue.suggestion, !suggestion.isEmpty {
                    Text("提案: \(suggestion)")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.statusComplete)
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func scoreColor(_ score: Int) -> Color {
        if score >= 85 { return AppTheme.statusComplete }
        if score >= 70 { return Color(hex: 0xF5A623) }
        return AppTheme.accent
    }

    private func errorBanner(_ message: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(AppTheme.accent)
            Text(message)
                .font(.caption)
                .foregroundStyle(AppTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(hex: 0x2A1717))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
