import SwiftUI

struct VideoTrackingView: View {
    @ObservedObject var viewModel: VideoTrackingViewModel

    var body: some View {
        VStack(spacing: 16) {
            if let message = viewModel.errorMessage {
                Text(message)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textSecondary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(Color(hex: 0x2A1717))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }

            ForEach(viewModel.videos) { video in
                VStack(alignment: .leading, spacing: 12) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(video.title)
                                .font(.headline)
                                .foregroundStyle(.white)
                            Text(video.channelName ?? "チャンネル未設定")
                                .font(.caption)
                                .foregroundStyle(AppTheme.textMuted)
                        }
                        Spacer()
                        Text(statusLabel(video.analysisStatus))
                            .font(.caption2)
                            .foregroundStyle(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(statusColor(video.analysisStatus))
                            .clipShape(Capsule())
                    }

                    if let analysis = video.analysisResult {
                        detailRow("総合", value: analysis.overallScore.map { String(format: "%.0f", $0) } ?? "-")
                        detailRow("構図", value: analysis.composition ?? "-")
                        detailRow("テンポ", value: analysis.tempo ?? "-")
                        detailRow("カット", value: analysis.cuttingStyle ?? "-")
                        detailRow("色彩", value: analysis.colorGrading ?? "-")

                        if let techniques = analysis.keyTechniques, !techniques.isEmpty {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("抽出テクニック")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textMuted)
                                ForEach(techniques, id: \.self) { item in
                                    Text("・\(item)")
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.textSecondary)
                                }
                            }
                        }
                    }
                }
                .padding(16)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            VStack(alignment: .leading, spacing: 12) {
                Text("学習済みインサイト")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)

                ForEach(viewModel.insights) { insight in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(insight.category)
                                .font(.caption)
                                .foregroundStyle(AppTheme.accent)
                            Spacer()
                            Text("信頼度 \(Int(insight.confidence * 100))%")
                                .font(.caption2)
                                .foregroundStyle(AppTheme.textMuted)
                        }
                        Text(insight.pattern)
                            .font(.caption)
                            .foregroundStyle(AppTheme.textSecondary)
                        Text("参照映像 \(insight.sourceCount)件")
                            .font(.caption2)
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    .padding(12)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }
            .padding(16)
            .background(AppTheme.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
    }

    private func detailRow(_ title: String, value: String) -> some View {
        HStack(alignment: .top) {
            Text(title)
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)
                .frame(width: 48, alignment: .leading)
            Text(value)
                .font(.caption)
                .foregroundStyle(AppTheme.textSecondary)
            Spacer()
        }
    }

    private func statusLabel(_ status: String) -> String {
        switch status {
        case "completed": return "分析完了"
        case "analyzing": return "分析中"
        default: return "待機中"
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "completed": return AppTheme.statusComplete
        case "analyzing": return Color(hex: 0xF5A623)
        default: return AppTheme.textMuted
        }
    }
}
