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
        .background(AppTheme.cardBackground)
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
    /// Vimeo URL（project.editedVideoURL）
    var editedVideoURL: String? = nil
    @StateObject private var viewModel = VimeoReviewViewModel()
    @State private var reviewComment: String = ""
    @State private var reviewComments: [ReviewComment] = []
    @State private var isCommentExpanded: Bool = false
    @State private var editingComment: VimeoCommentItem? = nil
    @State private var editingText: String = ""

    /// Vimeo URLからvideo_idを抽出するヘルパー
    private var vimeoVideoId: String? {
        VimeoURLParser.extractVideoId(from: editedVideoURL)
    }

    /// 限定公開動画のプライバシーハッシュ
    private var vimeoPrivacyHash: String? {
        VimeoURLParser.extractPrivacyHash(from: editedVideoURL)
    }

    var body: some View {
        VStack(spacing: 8) {
            // Vimeoレビューページへの導線（外部リンク）
            if let urlString = editedVideoURL, let url = URL(string: urlString) {
                Link(destination: url) {
                    HStack(spacing: 8) {
                        Image(systemName: "play.circle.fill")
                            .font(.system(size: 18))
                        Text("Vimeoレビューページを開く")
                            .font(.subheadline)
                            .fontWeight(.bold)
                        Spacer()
                        Image(systemName: "arrow.up.right.square")
                            .font(.caption)
                    }
                    .foregroundStyle(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(Color(hex: 0x1AB7EA))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }

            // Vimeo動画埋め込み再生（16:9アスペクト比で画面幅に合わせる）
            if let videoId = vimeoVideoId {
                VimeoPlayerView(
                    videoId: videoId,
                    privacyHash: vimeoPrivacyHash,
                    currentTime: $viewModel.currentTime,
                    isPlaying: $viewModel.isPlaying
                )
                .frame(height: (UIScreen.main.bounds.width - 32) * 9.0 / 16.0)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                // 動画未登録時のプレースホルダー
                VStack(spacing: 12) {
                    Image(systemName: "play.slash.fill")
                        .font(.system(size: 40))
                        .foregroundStyle(AppTheme.textMuted)
                    Text("編集後動画がまだアップロードされていません")
                        .font(AppTheme.bodyFont(14))
                        .foregroundStyle(AppTheme.textMuted)
                    Text("Vimeoにアップロード後、ここで再生・レビューできます")
                        .font(AppTheme.bodyFont(12))
                        .foregroundStyle(AppTheme.textMuted.opacity(0.7))
                }
                .frame(maxWidth: .infinity)
                .frame(height: (UIScreen.main.bounds.width - 32) * 9.0 / 16.0)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            // レビューコメント入力エリア（折りたたみ可能）
            VStack(alignment: .leading, spacing: 8) {
                Button {
                    withAnimation(.easeInOut(duration: 0.25)) {
                        isCommentExpanded.toggle()
                        // 折りたたみ時にキーボードを閉じる
                        if !isCommentExpanded {
                            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                        }
                    }
                } label: {
                    HStack {
                        Image(systemName: "bubble.left.and.bubble.right")
                            .foregroundStyle(AppTheme.accent)
                        Text("レビューコメント")
                            .font(AppTheme.sectionFont(16))
                            .foregroundStyle(.white)
                        if !reviewComment.isEmpty {
                            Circle()
                                .fill(AppTheme.accent)
                                .frame(width: 8, height: 8)
                        }
                        Spacer()
                        Image(systemName: isCommentExpanded ? "chevron.up" : "chevron.down")
                            .font(.caption)
                            .foregroundStyle(AppTheme.textMuted)
                    }
                }
                .buttonStyle(.plain)

                if isCommentExpanded {
                    TextEditor(text: $reviewComment)
                        .font(AppTheme.bodyFont(14))
                        .foregroundStyle(.white)
                        .scrollContentBackground(.hidden)
                        .frame(minHeight: 80, maxHeight: 120)
                        .padding(10)
                        .background(AppTheme.cardBackgroundLight)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .strokeBorder(AppTheme.textMuted.opacity(0.3), lineWidth: 1)
                        )

                    HStack {
                        if viewModel.currentTime > 0 {
                            Text("タイムコード: \(formatTimestamp(viewModel.currentTime))")
                                .font(AppTheme.bodyFont(12))
                                .foregroundStyle(AppTheme.accent)
                        }
                        Spacer()
                        Button {
                            submitComment()
                            // 送信後に折りたたむ
                            withAnimation(.easeInOut(duration: 0.25)) {
                                isCommentExpanded = false
                            }
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "paperplane.fill")
                                Text("送信")
                            }
                            .font(AppTheme.labelFont(14))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 10)
                            .background(reviewComment.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? AppTheme.textMuted : AppTheme.accent)
                            .clipShape(Capsule())
                        }
                        .disabled(reviewComment.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
            }
            .padding(14)
            .background(AppTheme.cardBackground)
            .clipShape(RoundedRectangle(cornerRadius: 12))

            // Vimeo API接続ステータス
            if let status = viewModel.statusMessage {
                HStack(spacing: 8) {
                    Image(systemName: viewModel.apiConnected == true ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                        .foregroundStyle(viewModel.apiConnected == true ? .green : .orange)
                    Text(status)
                        .font(AppTheme.bodyFont(12))
                        .foregroundStyle(viewModel.apiConnected == true ? AppTheme.textMuted : .orange)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            // ローカル送信コメント一覧
            if !reviewComments.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "text.bubble")
                            .foregroundStyle(AppTheme.accent)
                        Text("送信済みコメント")
                            .font(AppTheme.sectionFont(16))
                            .foregroundStyle(.white)
                        Spacer()
                        Text("\(reviewComments.count)件")
                            .font(AppTheme.bodyFont(12))
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    .padding(.horizontal, 14)
                    .padding(.top, 14)

                    ForEach(reviewComments) { comment in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                if let ts = comment.timestamp {
                                    Text(ts)
                                        .font(AppTheme.labelFont(12))
                                        .foregroundStyle(AppTheme.accent)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(AppTheme.accent.opacity(0.15))
                                        .clipShape(Capsule())
                                }
                                Spacer()
                                Text(comment.createdAt)
                                    .font(.caption2)
                                    .foregroundStyle(AppTheme.textMuted)
                            }
                            Text(comment.content)
                                .font(AppTheme.bodyFont(14))
                                .foregroundStyle(AppTheme.textSecondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(12)
                        .background(AppTheme.cardBackgroundLight)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .padding(.horizontal, 14)
                    }
                    .padding(.bottom, 14)
                }
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            // Vimeo APIから取得したコメント一覧
            if !viewModel.vimeoComments.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "bubble.left.and.text.bubble.right")
                            .foregroundStyle(AppTheme.accent)
                        Text("Vimeoレビューコメント")
                            .font(AppTheme.sectionFont(16))
                            .foregroundStyle(.white)
                        Spacer()
                        Text("\(viewModel.vimeoComments.count)件")
                            .font(AppTheme.bodyFont(12))
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    .padding(.horizontal, 14)
                    .padding(.top, 14)

                    ForEach(viewModel.vimeoComments) { comment in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                if let tc = comment.timecode {
                                    Text(tc)
                                        .font(AppTheme.labelFont(12))
                                        .foregroundStyle(AppTheme.accent)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(AppTheme.accent.opacity(0.15))
                                        .clipShape(Capsule())
                                }
                                Text(comment.user)
                                    .font(AppTheme.labelFont(12))
                                    .foregroundStyle(AppTheme.textSecondary)
                                Spacer()
                                if !comment.createdTime.isEmpty {
                                    Text(formatVimeoDate(comment.createdTime))
                                        .font(.caption2)
                                        .foregroundStyle(AppTheme.textMuted)
                                }
                            }
                            HStack(alignment: .top) {
                                Text(comment.text)
                                    .font(AppTheme.bodyFont(14))
                                    .foregroundStyle(AppTheme.textSecondary)
                                    .fixedSize(horizontal: false, vertical: true)
                                Spacer()
                                Button {
                                    editingText = comment.text
                                    editingComment = comment
                                } label: {
                                    Image(systemName: "pencil")
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.accent)
                                        .padding(6)
                                        .background(AppTheme.accent.opacity(0.15))
                                        .clipShape(Circle())
                                }
                            }
                        }
                        .padding(12)
                        .background(AppTheme.cardBackgroundLight)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .padding(.horizontal, 14)
                    }
                    .padding(.bottom, 14)
                }
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .sheet(item: $editingComment) { comment in
                    NavigationStack {
                        VStack(spacing: 16) {
                            if let tc = comment.timecode {
                                HStack {
                                    Image(systemName: "clock")
                                        .foregroundStyle(AppTheme.accent)
                                    Text(tc)
                                        .font(AppTheme.labelFont(14))
                                        .foregroundStyle(AppTheme.accent)
                                    Spacer()
                                }
                                .padding(.horizontal)
                            }
                            TextEditor(text: $editingText)
                                .font(AppTheme.bodyFont(14))
                                .scrollContentBackground(.hidden)
                                .padding(12)
                                .background(Color(.systemGray6))
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                                .frame(minHeight: 150)
                                .padding(.horizontal)
                            Spacer()
                        }
                        .padding(.top)
                        .navigationTitle("コメント編集")
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar {
                            ToolbarItem(placement: .cancellationAction) {
                                Button("キャンセル") {
                                    editingComment = nil
                                }
                            }
                            ToolbarItem(placement: .confirmationAction) {
                                Button("保存") {
                                    let newText = editingText
                                    let commentToEdit = comment
                                    editingComment = nil
                                    Task {
                                        await viewModel.editComment(
                                            comment: commentToEdit,
                                            newText: newText,
                                            projectId: projectId
                                        )
                                    }
                                }
                                .disabled(editingText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                            }
                        }
                    }
                    .presentationDetents([.medium, .large])
                }
            }

            if viewModel.isLoading {
                ProgressView()
                    .tint(AppTheme.accent)
                    .padding(.vertical, 40)
            }
        }
        .task {
            // editedVideoURLからvideo_idを設定
            if let videoId = vimeoVideoId {
                viewModel.vimeoVideoId = videoId
            }
            await viewModel.loadVimeoComments(projectId: projectId)
        }
    }

    /// コメント送信
    private func submitComment() {
        let trimmed = reviewComment.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        let timestamp: String? = viewModel.currentTime > 0 ? formatTimestamp(viewModel.currentTime) : nil
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy/MM/dd HH:mm"
        let now = formatter.string(from: Date())

        let comment = ReviewComment(
            id: UUID(),
            content: trimmed,
            timestamp: timestamp,
            createdAt: now
        )
        reviewComments.insert(comment, at: 0)
        reviewComment = ""
    }

    /// 秒数をMM:SS形式に変換
    private func formatTimestamp(_ seconds: TimeInterval) -> String {
        let m = Int(seconds) / 60
        let s = Int(seconds) % 60
        return String(format: "%02d:%02d", m, s)
    }

    /// Vimeo APIの日時文字列（ISO8601）を表示用に変換
    private func formatVimeoDate(_ isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: isoString) {
            let display = DateFormatter()
            display.dateFormat = "yyyy/MM/dd HH:mm"
            return display.string(from: date)
        }
        // フォールバック: fractionalSecondsなし
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: isoString) {
            let display = DateFormatter()
            display.dateFormat = "yyyy/MM/dd HH:mm"
            return display.string(from: date)
        }
        return isoString
    }
}

/// レビューコメントモデル
struct ReviewComment: Identifiable {
    let id: UUID
    let content: String
    let timestamp: String?
    let createdAt: String
}

/// Vimeo URLからvideo_idとプライバシーハッシュを抽出するユーティリティ
enum VimeoURLParser {
    /// URLからvideo_idを抽出
    /// https://vimeo.com/1145126331 → "1145126331"
    /// https://vimeo.com/1173896594/4718c886cc → "1173896594"
    /// https://player.vimeo.com/video/1145126331 → "1145126331"
    /// https://player.vimeo.com/video/1173896594?h=4718c886cc → "1173896594"
    static func extractVideoId(from urlString: String?) -> String? {
        guard let urlString = urlString,
              !urlString.isEmpty,
              let url = URL(string: urlString),
              let host = url.host else { return nil }

        // vimeo.com/12345 形式
        if host.contains("vimeo.com") {
            let pathComponents = url.pathComponents.filter { $0 != "/" }
            // player.vimeo.com/video/12345 形式
            if pathComponents.first == "video", pathComponents.count >= 2 {
                let videoId = pathComponents[1]
                if videoId.allSatisfy(\.isNumber) { return videoId }
            }
            // vimeo.com/12345 or vimeo.com/12345/hash 形式
            // 最初の数字のみのセグメントがvideo ID
            for component in pathComponents {
                if component.allSatisfy(\.isNumber) {
                    return component
                }
            }
        }
        return nil
    }

    /// URLから限定公開動画のプライバシーハッシュを抽出
    /// https://vimeo.com/1173896594/4718c886cc → "4718c886cc"
    /// https://player.vimeo.com/video/1173896594?h=4718c886cc → "4718c886cc"
    /// https://vimeo.com/1145126331 → nil（公開動画）
    static func extractPrivacyHash(from urlString: String?) -> String? {
        guard let urlString = urlString,
              !urlString.isEmpty,
              let url = URL(string: urlString),
              let host = url.host,
              host.contains("vimeo.com") else { return nil }

        // クエリパラメータ ?h=xxx 形式
        if let components = URLComponents(string: urlString),
           let hParam = components.queryItems?.first(where: { $0.name == "h" })?.value,
           !hParam.isEmpty {
            return hParam
        }

        // パスセグメント vimeo.com/12345/hash 形式
        let pathComponents = url.pathComponents.filter { $0 != "/" }
        // video ID の後のセグメントがハッシュ（英数字で数字のみではないもの）
        var foundVideoId = false
        for component in pathComponents {
            if foundVideoId {
                // video ID の直後のセグメント = ハッシュ
                if !component.isEmpty && !component.allSatisfy(\.isNumber) {
                    return component
                }
            }
            if component.allSatisfy(\.isNumber) {
                foundVideoId = true
            }
        }

        return nil
    }
}
