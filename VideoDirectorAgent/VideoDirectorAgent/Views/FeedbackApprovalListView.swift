import SwiftUI

/// 承認待ちFB一覧画面
/// タスク指示書の設計に基づき、各FBカードにゲスト名・FBカテゴリ・元FB要約・変換結果プレビューを表示
struct FeedbackApprovalListView: View {
    @ObservedObject var viewModel: FeedbackApprovalViewModel

    var body: some View {
        ZStack {
            AppTheme.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // ヘッダー
                headerSection

                if viewModel.isLoading && viewModel.pendingFeedbacks.isEmpty {
                    Spacer()
                    ProgressView()
                        .tint(AppTheme.accent)
                        .scaleEffect(1.5)
                    Spacer()
                } else if viewModel.pendingFeedbacks.isEmpty {
                    Spacer()
                    emptyState
                    Spacer()
                } else {
                    feedbackList
                }
            }
        }
        .task {
            await viewModel.fetchPending()
        }
    }

    // MARK: - ヘッダー
    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("FB承認")
                    .font(AppTheme.heroFont(24))
                    .foregroundStyle(.white)
                Text("\(viewModel.pendingCount)件の承認待ち")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }
            Spacer()

            // リロードボタン
            Button {
                Task { await viewModel.fetchPending() }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(AppTheme.accent)
                    .frame(width: 36, height: 36)
                    .background(AppTheme.cardBackground)
                    .clipShape(Circle())
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    // MARK: - 空状態
    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 48))
                .foregroundStyle(AppTheme.statusComplete)

            Text("承認待ちのFBはありません")
                .font(.headline)
                .foregroundStyle(.white)

            Text("音声FBを録音・変換すると、ここに表示されます")
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)
                .multilineTextAlignment(.center)
        }
        .padding(40)
    }

    // MARK: - FB一覧
    private var feedbackList: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(viewModel.pendingFeedbacks) { feedback in
                    NavigationLink {
                        FeedbackApprovalDetailView(
                            feedback: feedback,
                            viewModel: viewModel
                        )
                    } label: {
                        feedbackCard(feedback)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
        }
    }

    // MARK: - FBカード
    private func feedbackCard(_ feedback: FeedbackItem) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // 上段: ゲスト名 + ステータスバッジ
            HStack {
                if let guest = feedback.guestName, !guest.isEmpty {
                    Text(guest)
                        .font(AppTheme.labelFont(14))
                        .foregroundStyle(.white)
                }

                if let title = feedback.projectTitle, !title.isEmpty {
                    Text(title)
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                        .lineLimit(1)
                }

                Spacer()

                // 承認待ちバッジ
                Text(feedback.approvalStatus.label)
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(feedback.approvalStatus.color)
                    .clipShape(Capsule())
            }

            // 元のFBテキスト（要約）
            if let raw = feedback.rawVoiceText, !raw.isEmpty {
                HStack(spacing: 6) {
                    Image(systemName: "mic.fill")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.accent)
                    Text(raw)
                        .font(.caption)
                        .foregroundStyle(AppTheme.textSecondary)
                        .lineLimit(2)
                }
            }

            // 変換結果プレビュー
            if let converted = feedback.convertedText, !converted.isEmpty {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.right.circle.fill")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.statusComplete)
                    Text(converted)
                        .font(.caption)
                        .foregroundStyle(.white)
                        .lineLimit(2)
                }
            }

            // 下段: 日時 + タイムスタンプ
            HStack {
                if let ts = feedback.timestamp, !ts.isEmpty {
                    Label(ts, systemImage: "timer")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                }
                Spacer()
                Text(feedback.createdAt)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
