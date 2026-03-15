import SwiftUI

struct VoiceFeedbackView: View {
    @ObservedObject var viewModel: VoiceFeedbackViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                timelineCard
                recordCard
                transcriptCard
                convertedCard
                sendCard
            }
            .padding()
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationTitle("音声フィードバック")
    }

    private var timelineCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("タイムライン")
                .font(.headline)
            Slider(value: $viewModel.selectedTime, in: 0...360, step: 1)
                .tint(AppTheme.accent)
            Text("現在位置: \(format(viewModel.selectedTime))")
                .font(.caption)
                .foregroundStyle(.secondary)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack {
                    ForEach(viewModel.markers) { marker in
                        Text("\(format(marker.time)) \(marker.label)")
                            .font(.caption)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 6)
                            .background(AppTheme.accent.opacity(0.2))
                            .clipShape(Capsule())
                    }
                }
            }
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var recordCard: some View {
        VStack(spacing: 12) {
            Text(flowText)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Button(action: viewModel.toggleRecording) {
                Circle()
                    .fill(viewModel.flowState == .recording ? .red : AppTheme.accent)
                    .frame(width: 94, height: 94)
                    .overlay(
                        Image(systemName: viewModel.flowState == .recording ? "stop.fill" : "mic.fill")
                            .font(.system(size: 36, weight: .semibold))
                            .foregroundStyle(.white)
                    )
            }
            .buttonStyle(.plain)
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var transcriptCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("文字起こしプレビュー")
                .font(.headline)
            Text(viewModel.rawTranscript.isEmpty ? "録音停止後に文字起こしが表示されます" : viewModel.rawTranscript)
                .foregroundStyle(.white.opacity(0.9))
                .frame(maxWidth: .infinity, alignment: .leading)

            Button("変換する", action: viewModel.convertFeedback)
                .buttonStyle(.borderedProminent)
                .tint(AppTheme.accent)
                .disabled(!viewModel.canConvert)
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var convertedCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("変換後フィードバック")
                .font(.headline)

            Text(viewModel.convertedText.isEmpty ? "変換前" : viewModel.convertedText)
                .frame(maxWidth: .infinity, alignment: .leading)
                .foregroundStyle(.white.opacity(0.9))

            ForEach(viewModel.structuredItems) { item in
                HStack {
                    Text("\(item.timestamp) | \(item.element)")
                        .font(.caption)
                    Spacer()
                    Text(item.priority.rawValue)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(item.priority.color.opacity(0.25))
                        .clipShape(Capsule())
                }
                Text(item.note)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var sendCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("送信先", selection: $viewModel.sendDestination) {
                ForEach(SendDestination.allCases, id: \.self) { destination in
                    Text(destination.rawValue)
                }
            }
            .pickerStyle(.segmented)

            HStack {
                Button("この内容で送信", action: viewModel.sendFeedback)
                    .buttonStyle(.borderedProminent)
                    .tint(.green)
                    .disabled(!viewModel.canSend)

                Button("編集する") {}
                    .buttonStyle(.bordered)
            }

            if let sentMessage = viewModel.sentMessage {
                Text(sentMessage)
                    .font(.footnote)
                    .foregroundStyle(.green)
            }
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var flowText: String {
        switch viewModel.flowState {
        case .idle: return "録音開始でフィードバック入力"
        case .recording: return "録音中... もう一度タップで停止"
        case .transcribing: return "文字起こし中..."
        case .readyToConvert: return "文字起こし完了。変換して送信へ"
        case .readyToSend: return "変換完了。送信できます"
        case .sent: return "送信完了"
        }
    }

    private func format(_ seconds: TimeInterval) -> String {
        let minutes = Int(seconds) / 60
        let remain = Int(seconds) % 60
        let minuteText = minutes < 10 ? "0\(minutes)" : "\(minutes)"
        let secondText = remain < 10 ? "0\(remain)" : "\(remain)"
        return "\(minuteText):\(secondText)"
    }
}
