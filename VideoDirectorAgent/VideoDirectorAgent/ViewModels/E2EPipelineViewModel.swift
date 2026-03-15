import Foundation

/// E2Eパイプライン画面のViewModel
@MainActor
final class E2EPipelineViewModel: ObservableObject {
    // パイプラインの5ステップ
    enum PipelineStep: Int, CaseIterable, Identifiable {
        case feedbacks = 0
        case fbLearning = 1
        case videoLearning = 2
        case direction = 3
        case vimeoPost = 4

        var id: Int { rawValue }

        var label: String {
            switch self {
            case .feedbacks: return "FB取得"
            case .fbLearning: return "FB学習"
            case .videoLearning: return "映像学習"
            case .direction: return "ディレクション"
            case .vimeoPost: return "Vimeo投稿"
            }
        }

        var icon: String {
            switch self {
            case .feedbacks: return "bubble.left.fill"
            case .fbLearning: return "brain.head.profile"
            case .videoLearning: return "video.fill"
            case .direction: return "doc.text.fill"
            case .vimeoPost: return "paperplane.fill"
            }
        }

        /// APIレスポンスのステップキー名
        var stepKey: String {
            switch self {
            case .feedbacks: return "step1_feedbacks"
            case .fbLearning: return "step2_fb_learning"
            case .videoLearning: return "step3_video_learning"
            case .direction: return "step4_direction"
            case .vimeoPost: return "step5_vimeo"
            }
        }
    }

    // ステップの状態
    enum StepState {
        case pending    // 未実行
        case running    // 実行中
        case success    // 成功
        case error      // エラー
        case skipped    // スキップ
    }

    @Published var selectedProjectId: String = ""
    @Published var dryRun: Bool = true
    @Published var isRunning = false
    @Published var currentStep: Int = -1
    @Published var stepStates: [PipelineStep: StepState] = [:]
    @Published var result: E2EPipelineResponse?
    @Published var errorMessage: String?

    init() {
        // 全ステップを未実行で初期化
        for step in PipelineStep.allCases {
            stepStates[step] = .pending
        }
    }

    /// パイプラインを実行
    func runPipeline() async {
        guard !selectedProjectId.isEmpty else {
            errorMessage = "プロジェクトを選択してください"
            return
        }

        isRunning = true
        errorMessage = nil
        result = nil
        currentStep = 0

        // 全ステップを実行中表示
        for step in PipelineStep.allCases {
            stepStates[step] = .pending
        }
        stepStates[.feedbacks] = .running

        // 進捗シミュレーション（APIは同期的に返すため、UIで段階的に表示）
        let progressTask = Task {
            for step in PipelineStep.allCases {
                try await Task.sleep(nanoseconds: 800_000_000) // 0.8秒ごと
                if Task.isCancelled { break }
                currentStep = step.rawValue
                stepStates[step] = .running
            }
        }

        do {
            let body = E2EPipelineRequestBody(
                dryRun: dryRun,
                useLlm: true
            )
            let response = try await APIClient.shared.runE2EPipeline(
                projectId: selectedProjectId,
                body: body
            )

            progressTask.cancel()
            self.result = response

            // ステップ状態をAPIレスポンスから更新
            for step in PipelineStep.allCases {
                if let steps = response.steps,
                   let stepStatus = steps[step.stepKey] {
                    stepStates[step] = stepStatus.status == "ok" ? .success :
                        stepStatus.status == "error" ? .error :
                        stepStatus.status == "unavailable" ? .skipped : .success
                } else {
                    stepStates[step] = .success
                }
            }
            currentStep = PipelineStep.allCases.count

            if let errors = response.errors, !errors.isEmpty {
                errorMessage = errors.joined(separator: "\n")
            }
        } catch {
            progressTask.cancel()
            errorMessage = "パイプライン実行エラー: \(error.localizedDescription)"
            // 現在のステップをエラーに
            if let step = PipelineStep(rawValue: max(currentStep, 0)) {
                stepStates[step] = .error
            }
        }

        isRunning = false
    }

    /// リセット
    func reset() {
        result = nil
        errorMessage = nil
        currentStep = -1
        for step in PipelineStep.allCases {
            stepStates[step] = .pending
        }
    }
}
