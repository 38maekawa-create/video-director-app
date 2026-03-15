import SwiftUI

struct FeedbackHistoryView: View {
    var body: some View {
        List {
            ForEach(MockData.historyItems) { item in
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(item.projectTitle)
                            .font(.headline)
                        Spacer()
                        Text(item.timestamp)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Text("音声: \(item.rawVoiceText)")
                        .font(.subheadline)
                    Text("変換: \(item.convertedText)")
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.8))

                    HStack {
                        Text("対応状況: \(item.editorStatus)")
                            .font(.caption)
                        Spacer()
                        Text(item.learningEffect)
                            .font(.caption)
                            .foregroundStyle(.green)
                    }
                }
                .padding(.vertical, 8)
                .listRowBackground(AppTheme.card)
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
        .navigationTitle("フィードバック履歴")
    }
}
