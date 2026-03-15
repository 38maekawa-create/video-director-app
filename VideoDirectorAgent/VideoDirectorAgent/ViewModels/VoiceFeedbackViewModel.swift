import Foundation

enum VoiceFlowState {
    case idle
    case recording
    case transcribing
    case readyToConvert
    case readyToSend
    case sent
}

@MainActor
final class VoiceFeedbackViewModel: ObservableObject {
    @Published var selectedTime: Double = 138
    @Published var flowState: VoiceFlowState = .idle
    @Published var rawTranscript: String = ""
    @Published var convertedText: String = ""
    @Published var structuredItems: [StructuredFeedback] = []
    @Published var sendDestination: SendDestination = .vimeo
    @Published var sentMessage: String?

    let markers = MockData.timelineMarkers

    var canConvert: Bool {
        flowState == .readyToConvert && !rawTranscript.isEmpty
    }

    var canSend: Bool {
        flowState == .readyToSend && !convertedText.isEmpty
    }

    func toggleRecording() {
        sentMessage = nil

        if flowState == .recording {
            stopRecordingAndTranscribe()
            return
        }

        flowState = .recording
        rawTranscript = ""
        convertedText = ""
        structuredItems = []
    }

    private func stopRecordingAndTranscribe() {
        flowState = .transcribing

        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            self.rawTranscript = "2分18秒あたり、テロップ多くて要点が埋もれる。あとBGMが少し強い。"
            self.flowState = .readyToConvert
        }
    }

    func convertFeedback() {
        guard canConvert else { return }

        structuredItems = [
            .init(
                id: UUID(),
                timestamp: "02:18",
                element: "テロップ",
                priority: .high,
                note: "1カット1メッセージに整理し、文字量を約50%削減"
            ),
            .init(
                id: UUID(),
                timestamp: "02:18-02:40",
                element: "BGM",
                priority: .medium,
                note: "ナレーション帯域を避けるEQ調整 + 全体-2dB"
            )
        ]

        convertedText = "02:18付近はテロップ情報量を削減し、要点を1メッセージずつ提示してください。合わせて02:18-02:40のBGMレベルを2dB下げ、ナレーションの明瞭度を優先してください。"
        flowState = .readyToSend
    }

    func sendFeedback() {
        guard canSend else { return }

        flowState = .sent
        sentMessage = "\(sendDestination.rawValue)へ送信しました"
    }
}
