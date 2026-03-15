import Foundation

/// テロップチェック画面のViewModel
@MainActor
final class TelopCheckViewModel: ObservableObject {
    @Published var selectedProjectId: String = ""
    @Published var isLoading = false
    @Published var isRunning = false
    @Published var result: TelopCheckResponse?
    @Published var errorMessage: String?

    /// キャッシュ済み結果を取得
    func fetchCachedResult() async {
        guard !selectedProjectId.isEmpty else { return }
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchTelopCheck(projectId: selectedProjectId)
            // not_checkedの場合はresultをnilのままにする
            if response.status != "not_checked" {
                self.result = response
            }
        } catch {
            // キャッシュがない場合は無視（まだ実行されていない）
            print("テロップチェック結果取得エラー: \(error)")
        }

        isLoading = false
    }

    /// テロップチェックを実行
    func runCheck() async {
        guard !selectedProjectId.isEmpty else {
            errorMessage = "プロジェクトを選択してください"
            return
        }

        isRunning = true
        errorMessage = nil

        do {
            let body = TelopCheckRequestBody()
            let response = try await APIClient.shared.runTelopCheck(
                projectId: selectedProjectId,
                body: body
            )
            self.result = response
        } catch {
            errorMessage = "テロップチェック実行エラー: \(error.localizedDescription)"
        }

        isRunning = false
    }

    /// 結果に含まれる全問題をseverity順で返す
    var allIssues: [TelopIssue] {
        guard let frameCheck = result?.frameCheck else { return [] }
        return frameCheck.allIssues.sorted { issue1, issue2 in
            severityOrder(issue1.severity) < severityOrder(issue2.severity)
        }
    }

    /// severity のソート順（error=0, warning=1, info=2）
    private func severityOrder(_ severity: String) -> Int {
        switch severity.lowercased() {
        case "error": return 0
        case "warning": return 1
        default: return 2
        }
    }

    /// エラー件数
    var errorCount: Int {
        result?.frameCheck?.errorCount ?? 0
    }

    /// 警告件数
    var warningCount: Int {
        result?.frameCheck?.warningCount ?? 0
    }

    /// 総合スコア
    var overallScore: Double? {
        result?.frameCheck?.overallScore
    }
}
