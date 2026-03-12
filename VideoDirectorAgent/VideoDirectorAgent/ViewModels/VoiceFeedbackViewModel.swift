import Foundation
import SwiftUI
import AVFoundation
import Speech

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
    @Published var projectId: String = ""
    @Published var selectedTime: Double = 138
    @Published var flowState: VoiceFlowState = .idle
    @Published var rawTranscript: String = ""
    @Published var convertedText: String = ""
    @Published var structuredItems: [StructuredFeedback] = []
    @Published var sendDestination: SendDestination = .vimeo
    @Published var sentMessage: String?
    @Published var recordingDuration: TimeInterval = 0

    let markers = MockData.timelineMarkers

    private var recordingTimer: Timer?
    private var audioRecorder: AVAudioRecorder?
    private var audioFileURL: URL?

    var canConvert: Bool {
        flowState == .readyToConvert && !rawTranscript.isEmpty
    }

    var canSend: Bool {
        flowState == .readyToSend && !convertedText.isEmpty
    }

    var formattedDuration: String {
        let minutes = Int(recordingDuration) / 60
        let seconds = Int(recordingDuration) % 60
        return String(format: "%02d:%02d", minutes, seconds)
    }

    func toggleRecording() {
        sentMessage = nil

        if flowState == .recording {
            stopRecordingAndTranscribe()
            return
        }

        startRecording()
    }

    private func startRecording() {
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playAndRecord, mode: .default)
            try session.setActive(true)
        } catch {
            sentMessage = "録音の初期化に失敗しました"
            return
        }

        let fileName = "feedback_\(Date().timeIntervalSince1970).m4a"
        audioFileURL = FileManager.default.temporaryDirectory.appendingPathComponent(fileName)

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 44_100,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue
        ]

        do {
            guard let audioFileURL else { return }
            audioRecorder = try AVAudioRecorder(url: audioFileURL, settings: settings)
            audioRecorder?.record()
            flowState = .recording
            rawTranscript = ""
            convertedText = ""
            structuredItems = []
            recordingDuration = 0

            recordingTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    self?.recordingDuration += 0.1
                }
            }
        } catch {
            sentMessage = "録音開始に失敗しました"
        }
    }

    private func stopRecordingAndTranscribe() {
        recordingTimer?.invalidate()
        recordingTimer = nil
        audioRecorder?.stop()
        flowState = .transcribing

        guard let audioFileURL else {
            flowState = .idle
            return
        }

        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            Task { @MainActor in
                guard let self else { return }
                guard status == .authorized else {
                    self.rawTranscript = "（音声認識の権限がありません。設定から許可してください）"
                    self.flowState = .readyToConvert
                    return
                }

                let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "ja-JP"))
                let request = SFSpeechURLRecognitionRequest(url: audioFileURL)
                request.shouldReportPartialResults = false

                recognizer?.recognitionTask(with: request) { result, error in
                    Task { @MainActor in
                        if let result, result.isFinal {
                            self.rawTranscript = result.bestTranscription.formattedString
                            self.flowState = .readyToConvert
                        } else if let error {
                            self.rawTranscript = "（文字起こしエラー: \(error.localizedDescription)）"
                            self.flowState = .readyToConvert
                        }
                    }
                }
            }
        }
    }

    func convertFeedback() {
        guard canConvert else { return }
        sentMessage = nil
        flowState = .transcribing

        Task {
            do {
                let response = try await APIClient.shared.convertFeedback(rawText: rawTranscript, projectId: projectId)
                convertedText = response.convertedText
                structuredItems = response.structuredItems.map { item in
                    StructuredFeedback(
                        id: UUID(),
                        timestamp: item.timestamp ?? String(format: "%02d:%02d", Int(selectedTime) / 60, Int(selectedTime) % 60),
                        element: item.element,
                        priority: feedbackPriority(from: item.priority),
                        note: item.note
                    )
                }
                flowState = .readyToSend
            } catch {
                applyMockConversion()
                sentMessage = "変換APIに接続できなかったため簡易変換を表示しています"
            }
        }
    }

    func sendFeedback() {
        guard canSend else { return }
        Task {
            do {
                let timestamp = String(format: "%02d:%02d", Int(selectedTime) / 60, Int(selectedTime) % 60)
                try await APIClient.shared.createFeedback(
                    projectId: projectId,
                    content: convertedText.isEmpty ? rawTranscript : convertedText,
                    createdBy: "naoto",
                    timestamp: timestamp,
                    feedbackType: "voice"
                )
                flowState = .sent
                sentMessage = "フィードバックを保存しました"
            } catch {
                sentMessage = "送信エラー: \(error.localizedDescription)"
            }
        }
    }

    func resetFlow() {
        recordingTimer?.invalidate()
        recordingTimer = nil
        audioRecorder?.stop()
        audioRecorder = nil
        audioFileURL = nil
        flowState = .idle
        rawTranscript = ""
        convertedText = ""
        structuredItems = []
        sentMessage = nil
        recordingDuration = 0
    }

    private func feedbackPriority(from value: String) -> FeedbackPriority {
        switch value.lowercased() {
        case "high", "高":
            return .high
        case "low", "低":
            return .low
        default:
            return .medium
        }
    }

    private func applyMockConversion() {
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
}
