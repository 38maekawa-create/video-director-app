import SwiftUI
import WebKit

/// 素材動画サブタブ: プロジェクトに紐づくYouTube素材動画の一覧表示 + アプリ内再生 + 手動登録
struct SourceVideosSubTabView: View {
    let project: VideoProject

    @State private var videos: [SourceVideoItem] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var showAddSheet = false
    @State private var showPlayerSheet = false
    @State private var selectedVideo: SourceVideoItem?

    var body: some View {
        VStack(spacing: 12) {
            // プロジェクト情報カード
            projectInfoCard

            // 動画一覧
            if isLoading {
                loadingView
            } else if videos.isEmpty {
                emptyView
            } else {
                ForEach(videos, id: \.videoId) { video in
                    sourceVideoCard(video)
                }
            }

            // エラー表示
            if let errorMessage {
                Text(errorMessage)
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(AppTheme.accent)
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.accent.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }

            // 手動登録ボタン
            Button {
                showAddSheet = true
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "plus.circle.fill")
                    Text("素材動画を追加")
                }
                .font(AppTheme.labelFont(14))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(AppTheme.textMuted.opacity(0.3), lineWidth: 1)
                )
            }
        }
        .task {
            await loadSourceVideos()
        }
        .sheet(isPresented: $showAddSheet) {
            AddSourceVideoSheet(projectId: project.id) {
                // 登録完了後にリロード
                Task { await loadSourceVideos() }
            }
        }
        .sheet(isPresented: $showPlayerSheet) {
            if let video = selectedVideo {
                YouTubePlayerSheet(video: video)
            }
        }
    }

    // MARK: - プロジェクト情報

    private var projectInfoCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                Image(systemName: "video.badge.waveform")
                    .foregroundStyle(AppTheme.accent)
                Text("撮影素材")
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)
                Spacer()
                Text("\(videos.count)件")
                    .font(AppTheme.labelFont(12))
                    .foregroundStyle(AppTheme.textMuted)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(Capsule())
            }
            HStack(spacing: 16) {
                Label("ゲスト: \(project.guestName)", systemImage: "person.fill")
                Label("撮影日: \(project.shootDate)", systemImage: "calendar")
            }
            .font(.caption)
            .foregroundStyle(AppTheme.textMuted)
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    // MARK: - 動画カード

    private func sourceVideoCard(_ video: SourceVideoItem) -> some View {
        VStack(spacing: 0) {
            // YouTube埋め込みプレーヤー（16:9）
            // WKWebViewはintrinsicContentSizeを持たないため、明示的にframe指定
            YouTubePlayerView(videoURL: video.watchURL)
                .frame(height: (UIScreen.main.bounds.width - 32) * 9.0 / 16.0)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .onTapGesture {
                    selectedVideo = video
                    showPlayerSheet = true
                }

            // 動画情報
            VStack(alignment: .leading, spacing: 8) {
                // バッジ行
                HStack(spacing: 6) {
                    qualityBadge(video.qualityStatus ?? "pending")
                    sourceBadge(video.source ?? "")
                    Spacer()
                }

                if let title = video.title, !title.isEmpty {
                    Text(title)
                        .font(AppTheme.bodyFont(14, weight: .semibold))
                        .foregroundStyle(.white)
                        .lineLimit(2)
                }

                HStack(spacing: 12) {
                    if let url = URL(string: video.watchURL) {
                        Link(destination: url) {
                            HStack(spacing: 4) {
                                Image(systemName: "play.rectangle.fill")
                                    .font(.system(size: 12))
                                Text("YouTubeで開く")
                                    .font(AppTheme.labelFont(12))
                            }
                            .foregroundStyle(Color(hex: 0xFF0000))
                        }
                    }

                    if let duration = video.duration, !duration.isEmpty {
                        Label(duration, systemImage: "clock")
                            .font(.caption)
                            .foregroundStyle(AppTheme.textMuted)
                    }

                    if let date = video.createdAt {
                        Text(String(date.prefix(10)))
                            .font(.caption)
                            .foregroundStyle(AppTheme.textMuted)
                    }
                }
            }
            .padding(14)
        }
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    // MARK: - バッジ

    private func qualityBadge(_ status: String) -> some View {
        let (text, color): (String, Color) = {
            switch status {
            case "good_audio": return ("音質◎", AppTheme.statusComplete)
            case "poor_audio": return ("音質△", AppTheme.accent)
            default: return ("未確認", Color(hex: 0xF5A623))
            }
        }()
        return Text(text)
            .font(AppTheme.labelFont(11))
            .foregroundStyle(color)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    private func sourceBadge(_ source: String) -> some View {
        let (text, color): (String, Color) = {
            switch source {
            case "ai_dev5": return ("自動連携", Color(hex: 0x4A90D9))
            case "manual": return ("手動登録", AppTheme.textMuted)
            default: return ("", .clear)
            }
        }()
        return Group {
            if !text.isEmpty {
                Text(text)
                    .font(AppTheme.labelFont(11))
                    .foregroundStyle(color)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(color.opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            }
        }
    }

    // MARK: - 状態表示

    private var loadingView: some View {
        HStack(spacing: 12) {
            ProgressView()
                .tint(AppTheme.accent)
            Text("素材動画を読み込み中...")
                .foregroundStyle(AppTheme.textSecondary)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var emptyView: some View {
        VStack(spacing: 12) {
            Image(systemName: "film.stack")
                .font(.system(size: 36))
                .foregroundStyle(AppTheme.textMuted)
            Text("素材動画がまだ登録されていません")
                .font(AppTheme.bodyFont(15, weight: .semibold))
                .foregroundStyle(AppTheme.textSecondary)
            Text("AI開発5のナレッジ連携で自動登録、または下のボタンから手動登録できます")
                .font(AppTheme.bodyFont(13))
                .foregroundStyle(AppTheme.textMuted)
                .multilineTextAlignment(.center)
        }
        .padding(28)
        .frame(maxWidth: .infinity)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    // MARK: - データ取得

    private func loadSourceVideos() async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchSourceVideos(projectId: project.id)
            videos = response.videos
        } catch {
            // フォールバック: 既存のsourceVideoURLから表示
            if let url = project.sourceVideoURL, !url.isEmpty, isYouTubeURL(url) {
                let vid = extractVideoId(from: url)
                if !vid.isEmpty {
                    videos = [SourceVideoItem(
                        id: nil,
                        projectId: project.id,
                        youtubeUrl: url,
                        videoId: vid,
                        title: nil,
                        duration: nil,
                        qualityStatus: "pending",
                        source: "legacy",
                        knowledgeFile: nil,
                        createdAt: nil
                    )]
                }
            }
            if videos.isEmpty {
                errorMessage = "素材動画APIに接続できません"
            }
        }

        isLoading = false
    }

    private func isYouTubeURL(_ url: String) -> Bool {
        url.contains("youtube.com/watch") || url.contains("youtu.be/")
    }

    private func extractVideoId(from url: String) -> String {
        if let range = url.range(of: "v=") {
            let start = range.upperBound
            let remaining = String(url[start...])
            return String(remaining.prefix(while: { $0 != "&" && $0 != "#" }))
        }
        if url.contains("youtu.be/"), let range = url.range(of: "youtu.be/") {
            let start = range.upperBound
            let remaining = String(url[start...])
            return String(remaining.prefix(while: { $0 != "?" && $0 != "#" }))
        }
        return ""
    }
}

// MARK: - YouTube再生シート（フルスクリーン）

struct YouTubePlayerSheet: View {
    let video: SourceVideoItem
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                YouTubePlayerView(videoURL: video.watchURL)
                    .ignoresSafeArea(edges: .horizontal)

                if let title = video.title, !title.isEmpty {
                    Text(title)
                        .font(AppTheme.bodyFont(16, weight: .semibold))
                        .foregroundStyle(.white)
                        .padding(16)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                Spacer()
            }
            .background(AppTheme.background)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("閉じる") { dismiss() }
                        .foregroundStyle(AppTheme.accent)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    if let url = URL(string: video.watchURL) {
                        Link(destination: url) {
                            Image(systemName: "arrow.up.right.square")
                                .foregroundStyle(AppTheme.textSecondary)
                        }
                    }
                }
            }
        }
        .presentationDetents([.large])
    }
}

// MARK: - 素材動画手動登録シート

struct AddSourceVideoSheet: View {
    let projectId: String
    var onAdded: () -> Void

    @Environment(\.dismiss) var dismiss
    @State private var urlText = ""
    @State private var titleText = ""
    @State private var qualityStatus = "pending"
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @State private var successMessage: String?

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 20) {
                Text("YouTube URLを入力して素材動画を登録します")
                    .font(AppTheme.bodyFont(14))
                    .foregroundStyle(AppTheme.textSecondary)

                VStack(alignment: .leading, spacing: 8) {
                    Text("YouTube URL")
                        .font(AppTheme.labelFont(12))
                        .foregroundStyle(AppTheme.textMuted)
                    TextField("https://www.youtube.com/watch?v=...", text: $urlText)
                        .textFieldStyle(.plain)
                        .font(AppTheme.bodyFont(14))
                        .foregroundStyle(.white)
                        .padding(12)
                        .background(AppTheme.cardBackgroundLight)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("タイトル（任意）")
                        .font(AppTheme.labelFont(12))
                        .foregroundStyle(AppTheme.textMuted)
                    TextField("動画タイトル", text: $titleText)
                        .textFieldStyle(.plain)
                        .font(AppTheme.bodyFont(14))
                        .foregroundStyle(.white)
                        .padding(12)
                        .background(AppTheme.cardBackgroundLight)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                }

                VStack(alignment: .leading, spacing: 8) {
                    Text("音質ステータス")
                        .font(AppTheme.labelFont(12))
                        .foregroundStyle(AppTheme.textMuted)
                    Picker("音質", selection: $qualityStatus) {
                        Text("未確認").tag("pending")
                        Text("良好").tag("good_audio")
                        Text("不良").tag("poor_audio")
                    }
                    .pickerStyle(.segmented)
                }

                if let errorMessage {
                    Text(errorMessage)
                        .font(AppTheme.bodyFont(13))
                        .foregroundStyle(AppTheme.accent)
                }

                if let successMessage {
                    Text(successMessage)
                        .font(AppTheme.bodyFont(13))
                        .foregroundStyle(AppTheme.statusComplete)
                }

                Spacer()

                Button {
                    Task { await submit() }
                } label: {
                    HStack {
                        if isSubmitting {
                            ProgressView().tint(.white)
                        }
                        Text("登録する")
                    }
                    .font(AppTheme.labelFont(15))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(urlText.isEmpty ? AppTheme.textMuted : AppTheme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
                .disabled(urlText.isEmpty || isSubmitting)
            }
            .padding(20)
            .background(AppTheme.background)
            .navigationTitle("素材動画を追加")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("キャンセル") { dismiss() }
                        .foregroundStyle(AppTheme.accent)
                }
            }
        }
    }

    private func submit() async {
        guard !urlText.isEmpty else { return }
        isSubmitting = true
        errorMessage = nil
        successMessage = nil

        do {
            _ = try await APIClient.shared.addSourceVideo(
                projectId: projectId,
                youtubeURL: urlText.trimmingCharacters(in: .whitespacesAndNewlines),
                title: titleText.isEmpty ? nil : titleText.trimmingCharacters(in: .whitespacesAndNewlines),
                qualityStatus: qualityStatus
            )
            successMessage = "登録しました！"
            onAdded()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                dismiss()
            }
        } catch {
            errorMessage = "登録に失敗しました: \(error.localizedDescription)"
        }

        isSubmitting = false
    }
}
