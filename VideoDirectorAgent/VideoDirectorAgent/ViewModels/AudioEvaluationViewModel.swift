import Foundation

/// 音声品質評価画面のViewModel
@MainActor
final class AudioEvaluationViewModel: ObservableObject {
    @Published var selectedProjectId: String = ""
    @Published var isLoading = false
    @Published var isRunning = false
    @Published var result: AudioEvaluationResponse?
    @Published var errorMessage: String?

    /// キャッシュ済み結果を取得
    func fetchCachedResult() async {
        guard !selectedProjectId.isEmpty else { return }
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchAudioEvaluation(projectId: selectedProjectId)
            // not_evaluatedの場合はresultをnilのままにする
            if response.status != "not_evaluated" {
                self.result = response
            }
        } catch {
            print("音声品質評価結果取得エラー: \(error)")
        }

        isLoading = false
    }

    /// 音声品質評価を実行
    func runEvaluation() async {
        guard !selectedProjectId.isEmpty else {
            errorMessage = "プロジェクトを選択してください"
            return
        }

        isRunning = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.runAudioEvaluation(projectId: selectedProjectId)
            self.result = response
        } catch {
            errorMessage = "音声品質評価実行エラー: \(error.localizedDescription)"
        }

        isRunning = false
    }

    /// 総合スコア（0-100）
    var overallScore: Int {
        Int(result?.overallScore ?? 0)
    }

    /// グレード
    var grade: String {
        result?.grade ?? "-"
    }

    /// 問題リスト
    var issues: [AudioIssue] {
        result?.issues ?? []
    }

    /// 軸別スコア
    var axisScores: [AudioAxisScore] {
        result?.axisScores ?? []
    }
}
