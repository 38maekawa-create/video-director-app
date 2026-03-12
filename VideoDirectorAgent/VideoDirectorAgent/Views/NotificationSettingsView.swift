import SwiftUI

struct NotificationSettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var telegramEnabled = true
    @State private var lineEnabled = false
    @State private var notifyReportReady = true
    @State private var notifyQualityAlert = true
    @State private var notifyFeedbackReceived = true
    @State private var chatID = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("通知チャネル") {
                    Toggle("Telegram通知", isOn: $telegramEnabled)
                    Toggle("LINE通知", isOn: $lineEnabled)
                }

                Section("通知対象") {
                    Toggle("レポート完成", isOn: $notifyReportReady)
                    Toggle("品質警告", isOn: $notifyQualityAlert)
                    Toggle("FB受信", isOn: $notifyFeedbackReceived)
                }

                Section("送信先") {
                    TextField("チャットID", text: $chatID)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
            }
            .scrollContentBackground(.hidden)
            .background(AppTheme.background)
            .navigationTitle("通知設定")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("閉じる") {
                        dismiss()
                    }
                }
            }
        }
    }
}
