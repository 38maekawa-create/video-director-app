import SwiftUI

/// E2Eパイプライン実行画面
struct E2EPipelineView: View {
    @ObservedObject var viewModel: E2EPipelineViewModel
    let projects: [VideoProject]

    var body: some View {
        ScrollView(.vertical, showsIndicators: false) {
            VStack(spacing: 20) {
                // プロジェクト選択
                projectSelector

                // dry_runトグル
                dryRunToggle

                // 実行ボタン
                executeButton

                // 5段階の進捗表示
                if viewModel.isRunning || viewModel.result != nil {
                    stepIndicator
                }

                // エラーメッセージ
                if let error = viewModel.errorMessage {
                    errorBanner(error)
                }

                // 結果表示
                if let result = viewModel.result {
                    resultSection(result)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 40)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("E2Eパイプライン")
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
                Image(systemName: "film.stack.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("プロジェクト選択")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            // プロジェクト一覧をスクロール可能なリストで表示
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 10) {
                    ForEach(projects) { project in
                        Button {
                            viewModel.selectedProjectId = project.id
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

    // MARK: - Dry Runトグル
    private var dryRunToggle: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Dry Run モード")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                Text("ONの場合、Vimeo投稿をシミュレートのみ")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }
            Spacer()
            Toggle("", isOn: $viewModel.dryRun)
                .tint(AppTheme.accent)
                .labelsHidden()
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 実行ボタン
    private var executeButton: some View {
        Button {
            Task { await viewModel.runPipeline() }
        } label: {
            HStack(spacing: 10) {
                if viewModel.isRunning {
                    ProgressView()
                        .tint(.white)
                } else {
                    Image(systemName: "play.fill")
                }
                Text(viewModel.isRunning ? "実行中..." : "パイプライン実行")
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

    // MARK: - 5段階ステップインジケーター
    private var stepIndicator: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "arrow.triangle.2.circlepath")
                    .foregroundStyle(AppTheme.accent)
                Text("パイプライン進捗")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            VStack(spacing: 0) {
                ForEach(E2EPipelineViewModel.PipelineStep.allCases) { step in
                    HStack(spacing: 14) {
                        // ステップアイコン
                        stepIcon(for: step)

                        // ステップラベル
                        VStack(alignment: .leading, spacing: 2) {
                            Text(step.label)
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundStyle(.white)

                            // ステップ詳細（結果があれば表示）
                            if let result = viewModel.result,
                               let steps = result.steps,
                               let stepStatus = steps[step.stepKey] {
                                if let count = stepStatus.feedbackCount {
                                    Text("FB \(count)件取得")
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.textMuted)
                                }
                                if let err = stepStatus.error {
                                    Text(err)
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.accent)
                                }
                            }
                        }

                        Spacer()

                        // ステータスバッジ
                        stepStateBadge(viewModel.stepStates[step] ?? .pending)
                    }
                    .padding(.vertical, 10)

                    // ステップ間のコネクタライン
                    if step.rawValue < E2EPipelineViewModel.PipelineStep.allCases.count - 1 {
                        HStack {
                            Rectangle()
                                .fill(stepLineColor(for: step))
                                .frame(width: 2, height: 20)
                                .padding(.leading, 15)
                            Spacer()
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // ステップアイコン
    private func stepIcon(for step: E2EPipelineViewModel.PipelineStep) -> some View {
        let state = viewModel.stepStates[step] ?? .pending
        return ZStack {
            Circle()
                .fill(stepCircleColor(state))
                .frame(width: 32, height: 32)
            if case .running = state {
                ProgressView()
                    .tint(.white)
                    .scaleEffect(0.6)
            } else {
                Image(systemName: step.icon)
                    .font(.system(size: 14))
                    .foregroundStyle(.white)
            }
        }
    }

    private func stepCircleColor(_ state: E2EPipelineViewModel.StepState) -> Color {
        switch state {
        case .pending: return AppTheme.cardBackgroundLight
        case .running: return Color(hex: 0xF5A623)
        case .success: return AppTheme.statusComplete
        case .error: return AppTheme.accent
        case .skipped: return AppTheme.textMuted
        }
    }

    private func stepLineColor(for step: E2EPipelineViewModel.PipelineStep) -> Color {
        let state = viewModel.stepStates[step] ?? .pending
        switch state {
        case .success: return AppTheme.statusComplete.opacity(0.5)
        case .error: return AppTheme.accent.opacity(0.5)
        default: return AppTheme.cardBackgroundLight
        }
    }

    private func stepStateBadge(_ state: E2EPipelineViewModel.StepState) -> some View {
        Text(stateLabel(state))
            .font(.caption2)
            .fontWeight(.bold)
            .foregroundStyle(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(stepCircleColor(state))
            .clipShape(Capsule())
    }

    private func stateLabel(_ state: E2EPipelineViewModel.StepState) -> String {
        switch state {
        case .pending: return "待機"
        case .running: return "実行中"
        case .success: return "完了"
        case .error: return "エラー"
        case .skipped: return "スキップ"
        }
    }

    // MARK: - 結果セクション
    private func resultSection(_ result: E2EPipelineResponse) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Image(systemName: "doc.text.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("ディレクション結果")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                Spacer()
                if let entries = result.directionEntries {
                    Text("\(entries.count)件")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
            }

            if let entries = result.directionEntries, !entries.isEmpty {
                ForEach(entries) { entry in
                    directionEntryCard(entry)
                }
            } else {
                Text("ディレクションエントリがありません")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func directionEntryCard(_ entry: E2EDirectionEntry) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(entry.timestamp)
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundStyle(AppTheme.accent)
                Text(entry.element)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                Spacer()
                Text(entry.priority.uppercased())
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(entry.priorityColor)
                    .clipShape(Capsule())
            }

            Text(entry.instruction)
                .font(.caption)
                .foregroundStyle(AppTheme.textSecondary)

            if let reasoning = entry.reasoning, !reasoning.isEmpty {
                Text(reasoning)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textMuted)
                    .italic()
            }
        }
        .padding(12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    // MARK: - エラーバナー
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
