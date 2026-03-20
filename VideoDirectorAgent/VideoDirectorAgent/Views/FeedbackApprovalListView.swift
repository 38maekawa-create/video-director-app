import SwiftUI

/// 承認待ちFB一覧画面
/// タスク指示書の設計に基づき、各FBカードにゲスト名・FBカテゴリ・元FB要約・変換結果プレビューを表示
/// セグメントで「承認待ち」「全件」を切り替え可能
struct FeedbackApprovalListView: View {
    @ObservedObject var viewModel: FeedbackApprovalViewModel

    enum Segment: String, CaseIterable {
        case pending = "承認待ち"
        case all = "全件"
    }
    @State private var selectedSegment: Segment = .pending
    @State private var allFeedbacks: [FeedbackItem] = []
    @State private var isLoadingAll = false

    private var displayedFeedbacks: [FeedbackItem] {
        selectedSegment == .pending ? viewModel.pendingFeedbacks : allFeedbacks
    }

    var body: some View {
        ZStack {
            AppTheme.background
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // ヘッダー
                headerSection

                // セグメント
                segmentPicker

                if (selectedSegment == .pending && viewModel.isLoading && viewModel.pendingFeedbacks.isEmpty)
                    || (selectedSegment == .all && isLoadingAll && allFeedbacks.isEmpty) {
                    Spacer()
                    ProgressView()
                        .tint(AppTheme.accent)
                        .scaleEffect(1.5)
                    Spacer()
                } else if displayedFeedbacks.isEmpty {
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
                Task {
                    await viewModel.fetchPending()
                    if selectedSegment == .all {
                        await fetchAll()
                    }
                }
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

    // MARK: - セグメント
    private var segmentPicker: some View {
        Picker("", selection: $selectedSegment) {
            ForEach(Segment.allCases, id: \.self) { seg in
                Text(seg.rawValue)
            }
        }
        .pickerStyle(.segmented)
        .padding(.horizontal, 20)
        .padding(.bottom, 8)
        .onChange(of: selectedSegment) { newValue in
            if newValue == .all && allFeedbacks.isEmpty {
                Task { await fetchAll() }
            }
        }
    }

    // MARK: - 空状態
    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: selectedSegment == .pending ? "checkmark.seal.fill" : "doc.text.magnifyingglass")
                .font(.system(size: 48))
                .foregroundStyle(selectedSegment == .pending ? AppTheme.statusComplete : AppTheme.textMuted)

            Text(selectedSegment == .pending ? "承認待ちのFBはありません" : "FBがありません")
                .font(.headline)
                .foregroundStyle(.white)

            Text(selectedSegment == .pending
                 ? "音声FBを録音・変換すると、ここに表示されます"
                 : "")
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
                ForEach(displayedFeedbacks) { feedback in
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

                // 承認ステータスバッジ
                HStack(spacing: 4) {
                    Image(systemName: feedback.approvalStatus.icon)
                        .font(.caption2)
                    Text(feedback.approvalStatus.label)
                        .font(.caption2)
                        .fontWeight(.bold)
                }
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

            // 変換結果プレビュー（修正テキストがあればそちらを表示）
            let displayText = feedback.modifiedText ?? feedback.convertedText
            if let text = displayText, !text.isEmpty {
                HStack(spacing: 6) {
                    Image(systemName: feedback.modifiedText != nil ? "pencil.circle.fill" : "arrow.right.circle.fill")
                        .font(.caption2)
                        .foregroundStyle(feedback.modifiedText != nil ? Color(hex: 0x4A90D9) : AppTheme.statusComplete)
                    Text(text)
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

    // MARK: - 全件取得
    private func fetchAll() async {
        isLoadingAll = true
        do {
            allFeedbacks = try await APIClient.shared.fetchAllFeedbacks(limit: 100)
        } catch {
            // エラー時は空のまま
        }
        isLoadingAll = false
    }
}
