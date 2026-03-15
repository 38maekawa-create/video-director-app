import SwiftUI

/// Vimeo動画タイムライン上のフィードバックマーカーUI
/// - 再生時間に対応する位置にFBポイントをマーカー表示
/// - マーカータップでFB詳細ポップアップ
/// - 再生位置に応じて該当FBをハイライト
struct VimeoTimelineView: View {
    /// タイムライン上に表示するフィードバック一覧
    let feedbacks: [VimeoFeedbackItem]
    /// 動画の総再生時間（秒）
    let duration: TimeInterval
    /// 現在の再生位置（秒）
    let currentTime: TimeInterval
    /// マーカータップ時のシーク（秒）コールバック
    let onSeek: (TimeInterval) -> Void

    /// 詳細ポップアップ表示対象
    @State private var selectedFeedback: VimeoFeedbackItem?
    @State private var showDetail = false

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // タイムラインバー
            timelineBar
                .frame(height: 44)

            // アクティブなFBの簡易表示
            if let active = activeFeedback {
                activeFeedbackBanner(item: active)
            }
        }
        .sheet(item: $selectedFeedback) { item in
            FeedbackDetailSheet(item: item, onSeek: { seconds in
                onSeek(seconds)
            })
            .presentationDetents([.medium])
        }
    }

    // MARK: - タイムラインバー

    private var timelineBar: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                // 背景トラック
                Capsule()
                    .fill(Color.white.opacity(0.12))
                    .frame(height: 6)
                    .frame(maxWidth: .infinity)
                    .offset(y: 19)

                // 再生済みトラック
                if duration > 0 {
                    Capsule()
                        .fill(AppTheme.accent)
                        .frame(
                            width: geo.size.width * CGFloat(currentTime / duration),
                            height: 6
                        )
                        .offset(y: 19)
                }

                // フィードバックマーカー
                ForEach(feedbacks) { fb in
                    markerDot(fb: fb, totalWidth: geo.size.width)
                }
            }
        }
    }

    // MARK: - マーカードット

    @ViewBuilder
    private func markerDot(fb: VimeoFeedbackItem, totalWidth: CGFloat) -> some View {
        let xPos = duration > 0 ? totalWidth * CGFloat(fb.timestampMark / duration) : 0
        let isActive = isActiveFeedback(fb)

        Button {
            selectedFeedback = fb
        } label: {
            ZStack {
                Circle()
                    .fill(fb.priority.color)
                    .frame(width: isActive ? 18 : 12, height: isActive ? 18 : 12)
                    .shadow(color: fb.priority.color.opacity(0.7), radius: isActive ? 6 : 2)

                if isActive {
                    Circle()
                        .stroke(Color.white, lineWidth: 2)
                        .frame(width: 18, height: 18)
                }
            }
            .animation(.spring(response: 0.3), value: isActive)
        }
        .position(x: xPos, y: 22)
    }

    // MARK: - アクティブFBバナー

    private func activeFeedbackBanner(item: VimeoFeedbackItem) -> some View {
        HStack(spacing: 8) {
            // 優先度インジケーター
            RoundedRectangle(cornerRadius: 2)
                .fill(item.priority.color)
                .frame(width: 4, height: 36)

            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(item.timestampString)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.accent)
                    Text(item.element)
                        .font(.caption2)
                        .foregroundStyle(.white.opacity(0.55))
                    Spacer()
                    Text(item.priority.rawValue)
                        .font(.caption2)
                        .foregroundStyle(item.priority.color)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(item.priority.color.opacity(0.15))
                        .clipShape(Capsule())
                }
                Text(item.note)
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.85))
                    .lineLimit(2)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .transition(.opacity.combined(with: .move(edge: .bottom)))
        .animation(.easeInOut(duration: 0.25), value: item.id)
    }

    // MARK: - ヘルパー

    /// 現在再生位置から ±5秒 以内のFBをアクティブとみなす
    private func isActiveFeedback(_ fb: VimeoFeedbackItem) -> Bool {
        abs(fb.timestampMark - currentTime) <= 5
    }

    /// 現在位置に最も近いアクティブFB（複数の場合は最近傍）
    private var activeFeedback: VimeoFeedbackItem? {
        feedbacks
            .filter { isActiveFeedback($0) }
            .min(by: { abs($0.timestampMark - currentTime) < abs($1.timestampMark - currentTime) })
    }
}

// MARK: - フィードバック詳細シート

private struct FeedbackDetailSheet: View {
    let item: VimeoFeedbackItem
    let onSeek: (TimeInterval) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // ヘッダー
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.timestampString)
                        .font(.title2)
                        .bold()
                        .foregroundStyle(AppTheme.accent)
                    Text(item.element)
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(0.65))
                }
                Spacer()
                // 優先度バッジ
                Text(item.priority.rawValue)
                    .font(.subheadline)
                    .bold()
                    .foregroundStyle(item.priority.color)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(item.priority.color.opacity(0.18))
                    .clipShape(Capsule())
            }

            Divider().background(.white.opacity(0.1))

            // FBノート
            Text(item.note)
                .font(.body)
                .foregroundStyle(.white)
                .fixedSize(horizontal: false, vertical: true)

            Spacer()

            // シークボタン
            Button {
                onSeek(item.timestampMark)
                dismiss()
            } label: {
                Label("このタイムコードへジャンプ", systemImage: "arrow.right.circle.fill")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(AppTheme.accent)
        }
        .padding(20)
        .background(AppTheme.background.ignoresSafeArea())
        .preferredColorScheme(.dark)
    }
}

// MARK: - レビュータブ統合ビュー
/// DirectionReportViewの「レビュー」タブで表示する統合ビュー
/// VimeoプレイヤーとタイムラインFBを組み合わせて表示
struct VimeoReviewTabView: View {
    let projectId: String
    @StateObject private var viewModel = VimeoReviewViewModel()

    var body: some View {
        VStack(spacing: 16) {
            // Vimeoプレイヤー
            VimeoPlayerView(
                videoId: viewModel.vimeoVideoId,
                currentTime: $viewModel.currentTime,
                isPlaying: $viewModel.isPlaying
            )
            .frame(height: 220)
            .clipShape(RoundedRectangle(cornerRadius: 12))

            // タイムライン
            if !viewModel.feedbacks.isEmpty {
                VimeoTimelineView(
                    feedbacks: viewModel.feedbacks,
                    duration: viewModel.duration,
                    currentTime: viewModel.currentTime,
                    onSeek: { time in viewModel.seek(to: time) }
                )
                .frame(height: 60)
            }

            // FB一覧
            VStack(spacing: 8) {
                ForEach(viewModel.feedbacks) { fb in
                    Button {
                        viewModel.seek(to: fb.timestampMark)
                    } label: {
                        HStack(spacing: 12) {
                            Text(fb.timestampString)
                                .font(AppTheme.labelFont(14))
                                .foregroundStyle(AppTheme.accent)
                                .frame(width: 50, alignment: .leading)

                            Circle()
                                .fill(fb.priority.color)
                                .frame(width: 8, height: 8)

                            VStack(alignment: .leading, spacing: 2) {
                                Text(fb.element)
                                    .font(AppTheme.labelFont(13))
                                    .foregroundStyle(AppTheme.textSecondary)
                                Text(fb.note)
                                    .font(AppTheme.bodyFont(12))
                                    .foregroundStyle(AppTheme.textMuted)
                                    .lineLimit(2)
                            }
                            Spacer()
                        }
                        .padding(12)
                        .background(AppTheme.cardBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    .buttonStyle(.plain)
                }
            }

            if viewModel.feedbacks.isEmpty && !viewModel.isLoading {
                Text("タイムコード付きフィードバックがありません")
                    .font(AppTheme.bodyFont(14))
                    .foregroundStyle(AppTheme.textMuted)
                    .padding(.vertical, 40)
            }

            if viewModel.isLoading {
                ProgressView()
                    .tint(AppTheme.accent)
                    .padding(.vertical, 40)
            }
        }
        .padding(.horizontal, 16)
        .task {
            await viewModel.loadFeedbacks(projectId: projectId)
        }
    }
}
