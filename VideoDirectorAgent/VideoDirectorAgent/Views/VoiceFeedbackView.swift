import SwiftUI

// MARK: - 画面3: 音声フィードバック（全画面モーダル）
struct VoiceFeedbackView: View {
    @ObservedObject var viewModel: VoiceFeedbackViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            // 背景
            AppTheme.background
                .ignoresSafeArea()

            // 録音中は背景を暗く（フォーカスモード）
            if viewModel.flowState == .recording {
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                    .animation(.easeInOut, value: viewModel.flowState)
            }

            VStack(spacing: 0) {
                // ヘッダー
                modalHeader

                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: 20) {
                        // タイムスタンプ入力
                        if viewModel.flowState == .idle || viewModel.flowState == .recording {
                            timestampSection
                        }

                        // 録音ボタン
                        recordingSection

                        // 文字起こし結果
                        if !viewModel.rawTranscript.isEmpty {
                            transcriptSection
                        }

                        // Before/After 変換結果
                        if !viewModel.convertedText.isEmpty {
                            beforeAfterSection
                        }

                        // 送信
                        if viewModel.flowState == .readyToSend || viewModel.flowState == .sent {
                            sendSection
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 40)
                }
            }
        }
    }

    // MARK: - モーダルヘッダー
    private var modalHeader: some View {
        HStack {
            Button {
                viewModel.resetFlow()
                dismiss()
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 36, height: 36)
                    .background(AppTheme.cardBackground)
                    .clipShape(Circle())
            }

            Spacer()

            Text("音声フィードバック")
                .font(.headline)
                .foregroundStyle(.white)

            Spacer()

            // バランス用の透明ビュー
            Color.clear.frame(width: 36, height: 36)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    // MARK: - タイムスタンプ入力
    private var timestampSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("タイムスタンプ")
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(.white)

            // スライダー
            VStack(spacing: 8) {
                Slider(value: $viewModel.selectedTime, in: 0...600, step: 1)
                    .tint(AppTheme.accent)

                HStack {
                    Text(formatTime(viewModel.selectedTime))
                        .font(.system(size: 20, weight: .heavy, design: .monospaced))
                        .foregroundStyle(AppTheme.accent)
                    Spacer()
                    Text("/ 10:00")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
            }

            // マーカー
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(viewModel.markers) { marker in
                        Button {
                            viewModel.selectedTime = marker.time
                        } label: {
                            HStack(spacing: 4) {
                                Text(formatTime(marker.time))
                                    .font(.caption2)
                                    .fontWeight(.bold)
                                Text(marker.label)
                                    .font(.caption2)
                            }
                            .foregroundStyle(.white)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(AppTheme.accent.opacity(0.3))
                            .clipShape(Capsule())
                            .overlay(
                                Capsule()
                                    .strokeBorder(AppTheme.accent.opacity(0.5), lineWidth: 1)
                            )
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 録音ボタン
    private var recordingSection: some View {
        VStack(spacing: 16) {
            // ステータステキスト
            Text(flowStatusText)
                .font(.subheadline)
                .foregroundStyle(AppTheme.textSecondary)

            ZStack {
                // 録音中パルスアニメーション
                if viewModel.flowState == .recording {
                    Circle()
                        .fill(AppTheme.accent.opacity(0.2))
                        .frame(width: 140, height: 140)
                        .scaleEffect(pulseScale)
                        .animation(
                            .easeInOut(duration: 1.0).repeatForever(autoreverses: true),
                            value: viewModel.flowState
                        )

                    Circle()
                        .fill(AppTheme.accent.opacity(0.1))
                        .frame(width: 170, height: 170)
                        .scaleEffect(pulseScale)
                        .animation(
                            .easeInOut(duration: 1.2).repeatForever(autoreverses: true),
                            value: viewModel.flowState
                        )
                }

                // メインボタン
                Button(action: viewModel.toggleRecording) {
                    Circle()
                        .fill(viewModel.flowState == .recording ? AppTheme.accent : AppTheme.cardBackground)
                        .frame(width: 110, height: 110)
                        .overlay(
                            Group {
                                if viewModel.flowState == .recording {
                                    // 停止アイコン
                                    RoundedRectangle(cornerRadius: 6)
                                        .fill(.white)
                                        .frame(width: 32, height: 32)
                                } else {
                                    Image(systemName: "mic.fill")
                                        .font(.system(size: 40, weight: .bold))
                                        .foregroundStyle(AppTheme.accent)
                                }
                            }
                        )
                        .overlay(
                            Circle()
                                .strokeBorder(
                                    viewModel.flowState == .recording
                                        ? AppTheme.accent
                                        : AppTheme.textMuted.opacity(0.3),
                                    lineWidth: 3
                                )
                        )
                }
                .buttonStyle(.plain)
                .disabled(viewModel.flowState == .transcribing)
            }

            // 録音時間
            if viewModel.flowState == .recording {
                Text(viewModel.formattedDuration)
                    .font(.system(size: 32, weight: .heavy, design: .monospaced))
                    .foregroundStyle(AppTheme.accent)

                // 波形アニメーション（モック）
                waveformView
            }

            if viewModel.flowState == .transcribing {
                ProgressView()
                    .tint(AppTheme.accent)
                    .scaleEffect(1.5)
                    .padding(.top, 8)
            }
        }
        .padding(.vertical, 24)
    }

    // MARK: - 波形アニメーション（モック）
    private var waveformView: some View {
        HStack(spacing: 3) {
            ForEach(0..<20, id: \.self) { i in
                RoundedRectangle(cornerRadius: 2)
                    .fill(AppTheme.accent)
                    .frame(width: 4, height: waveHeight(for: i))
                    .animation(
                        .easeInOut(duration: 0.3 + Double(i % 5) * 0.1)
                            .repeatForever(autoreverses: true),
                        value: viewModel.flowState
                    )
            }
        }
        .frame(height: 40)
    }

    private func waveHeight(for index: Int) -> CGFloat {
        let heights: [CGFloat] = [12, 20, 28, 16, 36, 24, 32, 14, 26, 38,
                                   18, 30, 22, 34, 10, 28, 20, 36, 14, 24]
        return viewModel.flowState == .recording
            ? heights[index % heights.count]
            : 8
    }

    // MARK: - 文字起こし結果
    private var transcriptSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "text.bubble.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("文字起こし結果")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            Text(viewModel.rawTranscript)
                .font(.body)
                .foregroundStyle(AppTheme.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)

            if viewModel.canConvert {
                Button(action: viewModel.convertFeedback) {
                    HStack {
                        Image(systemName: "arrow.triangle.2.circlepath")
                        Text("プロの指示に変換する")
                    }
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(AppTheme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Before/After 変換表示
    private var beforeAfterSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Before → After")
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(AppTheme.accent)

            // Before（元の音声）
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(AppTheme.accent)
                    Text("あなたの声")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(AppTheme.accent)
                }

                Text(viewModel.rawTranscript)
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.textSecondary)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.accent.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            // 矢印
            Image(systemName: "arrow.down")
                .font(.title3)
                .foregroundStyle(AppTheme.accent)
                .frame(maxWidth: .infinity)

            // After（プロの指示）
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(AppTheme.statusComplete)
                    Text("プロの指示")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(AppTheme.statusComplete)
                }

                Text(viewModel.convertedText)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.statusComplete.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 8))

                // 構造化フィードバック
                ForEach(viewModel.structuredItems) { item in
                    HStack(spacing: 8) {
                        Text(item.timestamp)
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundStyle(AppTheme.accent)
                            .frame(width: 60, alignment: .leading)

                        Text(item.element)
                            .font(.caption)
                            .foregroundStyle(.white)

                        Spacer()

                        Text(item.priority.rawValue)
                            .font(.caption2)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(item.priority.color)
                            .clipShape(Capsule())
                    }
                    .padding(10)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 送信セクション
    private var sendSection: some View {
        VStack(spacing: 16) {
            Picker("送信先", selection: $viewModel.sendDestination) {
                ForEach(SendDestination.allCases, id: \.self) { dest in
                    Text(dest.rawValue)
                }
            }
            .pickerStyle(.segmented)
            .tint(AppTheme.accent)

            HStack(spacing: 12) {
                Button(action: viewModel.sendFeedback) {
                    HStack {
                        Image(systemName: "paperplane.fill")
                        Text("この指示を送信")
                    }
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(viewModel.canSend ? AppTheme.statusComplete : AppTheme.textMuted)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
                .disabled(!viewModel.canSend)

                Button {
                    viewModel.resetFlow()
                } label: {
                    HStack {
                        Image(systemName: "arrow.counterclockwise")
                        Text("やり直し")
                    }
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
                    .padding(.vertical, 14)
                    .padding(.horizontal, 20)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }

            if let msg = viewModel.sentMessage {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(AppTheme.statusComplete)
                    Text(msg)
                        .font(.subheadline)
                        .foregroundStyle(AppTheme.statusComplete)
                }
                .padding(12)
                .frame(maxWidth: .infinity)
                .background(AppTheme.statusComplete.opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - ヘルパー
    private var flowStatusText: String {
        switch viewModel.flowState {
        case .idle: return "タップして録音開始"
        case .recording: return "録音中... もう一度タップで停止"
        case .transcribing: return "文字起こし中..."
        case .readyToConvert: return "変換ボタンを押してください"
        case .readyToSend: return "変換完了。送信できます"
        case .sent: return "送信完了"
        }
    }

    private var pulseScale: CGFloat {
        viewModel.flowState == .recording ? 1.15 : 1.0
    }

    private func formatTime(_ seconds: TimeInterval) -> String {
        let m = Int(seconds) / 60
        let s = Int(seconds) % 60
        return String(format: "%02d:%02d", m, s)
    }
}
