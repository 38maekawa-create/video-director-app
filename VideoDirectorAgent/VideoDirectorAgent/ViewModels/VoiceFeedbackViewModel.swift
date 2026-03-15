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
    @Published var vimeoVideoId: String = ""
    @Published var vimeoPostResult: VimeoPostReviewResponse?
    @Published var isPostingToVimeo: Bool = false

    let markers: [TimelineMarker] = []

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
                flowState = .readyToConvert
                sentMessage = "変換APIに接続できません: \(error.localizedDescription)"
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
                    createdBy: APIClient.shared.actorName,
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

    /// Vimeoレビューコメントとして投稿する（dry-runモード対応）
    /// STT結果 + タイムスタンプを構造化してAPIエンドポイントに送信
    func sendToVimeoReview(dryRun: Bool = true) {
        guard !vimeoVideoId.isEmpty else {
            sentMessage = "Vimeo動画IDが未設定です"
            return
        }
        guard !convertedText.isEmpty || !rawTranscript.isEmpty else {
            sentMessage = "送信するコメントがありません"
            return
        }

        isPostingToVimeo = true
        sentMessage = nil

        Task {
            do {
                // structuredItemsがある場合はそれぞれをコメントとして投稿
                // ない場合はconvertedText全体を1つのコメントとして投稿
                let comments: [VimeoCommentPayload]

                if !structuredItems.isEmpty {
                    comments = structuredItems.map { item in
                        VimeoCommentPayload(
                            timecode: item.timestamp,
                            text: item.note.isEmpty ? item.element : "\(item.element): \(item.note)",
                            priority: item.priority.rawValue == "高" ? "high" : (item.priority.rawValue == "低" ? "low" : "medium"),
                            feedbackId: nil
                        )
                    }
                } else {
                    let timecode = String(
                        format: "%02d:%02d",
                        Int(selectedTime) / 60,
                        Int(selectedTime) % 60
                    )
                    let text = convertedText.isEmpty ? rawTranscript : convertedText
                    comments = [
                        VimeoCommentPayload(
                            timecode: timecode,
                            text: text,
                            priority: "medium",
                            feedbackId: nil
                        )
                    ]
                }

                let response = try await APIClient.shared.postVimeoReviewComments(
                    vimeoVideoId: vimeoVideoId,
                    comments: comments,
                    dryRun: dryRun
                )

                vimeoPostResult = response
                isPostingToVimeo = false

                if response.mode == "dry_run" {
                    sentMessage = "Vimeo投稿プレビュー: \(response.commentCount ?? comments.count)件のコメント"
                } else {
                    let posted = response.summary?.posted ?? 0
                    let failed = response.summary?.failed ?? 0
                    if failed == 0 {
                        sentMessage = "Vimeoに\(posted)件のコメントを投稿しました"
                        flowState = .sent
                    } else {
                        sentMessage = "Vimeo投稿: \(posted)件成功 / \(failed)件失敗"
                    }
                }
            } catch {
                isPostingToVimeo = false
                sentMessage = "Vimeo投稿エラー: \(error.localizedDescription)"
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
        vimeoPostResult = nil
        isPostingToVimeo = false
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

}
