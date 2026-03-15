import SwiftUI

/// 音声品質評価画面
struct AudioEvaluationView: View {
    @ObservedObject var viewModel: AudioEvaluationViewModel
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
                        Text("音声品質を評価中...")
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
                if viewModel.result != nil {
                    mainScoreCard
                    axisScoresCard
                    issuesCard
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 40)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("音声品質評価")
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
                Image(systemName: "waveform")
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
            Task { await viewModel.runEvaluation() }
        } label: {
            HStack(spacing: 10) {
                if viewModel.isRunning {
                    ProgressView()
                        .tint(.white)
                } else {
                    Image(systemName: "waveform.badge.magnifyingglass")
                }
                Text(viewModel.isRunning ? "評価中..." : "音声品質評価を実行")
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

    // MARK: - メインスコアカード
    private var mainScoreCard: some View {
        VStack(spacing: 12) {
            Text("音声品質スコア")
                .font(AppTheme.labelFont(13))
                .foregroundStyle(AppTheme.textMuted)
                .tracking(2)

            Text("\(viewModel.overallScore)")
                .font(AppTheme.heroFont(72))
                .foregroundStyle(viewModel.result?.gradeColor ?? AppTheme.textMuted)

            // グレードバッジ
            Text(viewModel.grade)
                .font(.system(size: 20, weight: .heavy, design: .rounded))
                .foregroundStyle(.white)
                .padding(.horizontal, 16)
                .padding(.vertical, 6)
                .background(viewModel.result?.gradeColor ?? AppTheme.textMuted)
                .clipShape(Capsule())

            // 分析方式
            if let method = viewModel.result?.analysisMethod {
                HStack(spacing: 4) {
                    Image(systemName: viewModel.result?.isEstimated == true
                          ? "text.magnifyingglass" : "waveform.path")
                        .font(.caption2)
                    Text(method)
                        .font(.caption2)
                }
                .foregroundStyle(AppTheme.textMuted)
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(Capsule())
            }
        }
        .padding(.vertical, 28)
        .frame(maxWidth: .infinity)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - 軸別スコアカード
    private var axisScoresCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "chart.bar.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("軸別スコア")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            if viewModel.axisScores.isEmpty {
                Text("軸別スコアデータなし")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            } else {
                ForEach(viewModel.axisScores) { axis in
                    HStack(spacing: 12) {
                        // 軸ラベル
                        Text(axis.displayLabel)
                            .font(.caption)
                            .foregroundStyle(AppTheme.textSecondary)
                            .frame(width: 80, alignment: .leading)

                        // プログレスバー
                        GeometryReader { geo in
                            ZStack(alignment: .leading) {
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(AppTheme.cardBackgroundLight)
                                    .frame(height: 20)
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(axis.scoreColor)
                                    .frame(
                                        width: geo.size.width * CGFloat(axis.score) / 100.0,
                                        height: 20
                                    )
                            }
                        }
                        .frame(height: 20)

                        // スコア
                        Text("\(Int(axis.score))")
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundStyle(axis.scoreColor)
                            .frame(width: 30, alignment: .trailing)
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 問題リストカード
    private var issuesCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(Color(hex: 0xF5A623))
                Text("検出された問題")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(viewModel.issues.count)件")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }

            if viewModel.issues.isEmpty {
                Text("問題は検出されませんでした")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
            } else {
                ForEach(viewModel.issues) { issue in
                    HStack(alignment: .top, spacing: 10) {
                        Circle()
                            .fill(issue.severityColor)
                            .frame(width: 8, height: 8)
                            .padding(.top, 6)

                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(issue.axis)
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
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
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
