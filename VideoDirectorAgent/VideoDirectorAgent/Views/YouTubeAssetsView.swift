import SwiftUI

/// YouTube素材画面: サムネイル指示書（Z型4ゾーン）・タイトル案・概要欄を表示
struct YouTubeAssetsView: View {
    let projectID: String
    @StateObject private var viewModel = YouTubeAssetsViewModel()

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                if viewModel.isLoading {
                    ProgressView("読み込み中...")
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity, minHeight: 200)
                } else if let assets = viewModel.assets {
                    // サムネイル指示書（Z型4ゾーン）
                    ThumbnailZoneCard(zones: assets.thumbnailZones)

                    // タイトル案リスト（タップでコピー）
                    TitleCandidatesCard(candidates: assets.titleCandidates)

                    // 概要欄テキスト（コピーボタン付き）
                    DescriptionCard(text: assets.description)
                } else if let error = viewModel.errorMessage {
                    Text("エラー: \(error)")
                        .foregroundStyle(.red)
                        .padding()
                }
            }
            .padding()
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationTitle("YouTube素材")
        .task {
            await viewModel.fetchAssets(projectID: projectID)
        }
    }
}

// MARK: - サムネイル指示書（Z型4ゾーン）カード

private struct ThumbnailZoneCard: View {
    let zones: ThumbnailZones

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("サムネイル指示書（Z型4ゾーン）", systemImage: "photo.on.rectangle")
                .font(.headline)
                .foregroundStyle(.white)

            // Z字順: 左上→右上→左下→右下
            VStack(spacing: 8) {
                HStack(spacing: 8) {
                    ZoneCell(label: "左上", content: zones.topLeft,    color: AppTheme.accent)
                    ZoneCell(label: "右上", content: zones.topRight,   color: .purple)
                }
                HStack(spacing: 8) {
                    ZoneCell(label: "左下", content: zones.bottomLeft, color: .teal)
                    ZoneCell(label: "右下", content: zones.bottomRight, color: .orange)
                }
            }
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

private struct ZoneCell: View {
    let label: String
    let content: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(.caption2)
                .bold()
                .foregroundStyle(color)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(color.opacity(0.18))
                .clipShape(Capsule())

            Text(content)
                .font(.caption)
                .foregroundStyle(.white.opacity(0.88))
                .frame(maxWidth: .infinity, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(10)
        .background(color.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .frame(maxWidth: .infinity)
    }
}

// MARK: - タイトル案カード

private struct TitleCandidatesCard: View {
    let candidates: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("タイトル案（タップでコピー）", systemImage: "text.cursor")
                .font(.headline)
                .foregroundStyle(.white)

            ForEach(Array(candidates.enumerated()), id: \.offset) { index, title in
                TitleCandidateRow(index: index + 1, title: title)
            }
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

private struct TitleCandidateRow: View {
    let index: Int
    let title: String
    @State private var copied = false

    var body: some View {
        HStack(spacing: 10) {
            // 番号バッジ
            Text("\(index)")
                .font(.caption)
                .bold()
                .foregroundStyle(AppTheme.accent)
                .frame(width: 22, height: 22)
                .background(AppTheme.accent.opacity(0.15))
                .clipShape(Circle())

            Text(title)
                .font(.subheadline)
                .foregroundStyle(.white.opacity(0.90))
                .frame(maxWidth: .infinity, alignment: .leading)
                .lineLimit(3)

            // コピーボタン
            Button {
                copyToClipboard(title)
            } label: {
                Image(systemName: copied ? "checkmark.circle.fill" : "doc.on.doc")
                    .foregroundStyle(copied ? .green : AppTheme.accent)
                    .font(.system(size: 16))
            }
        }
        .padding(.vertical, 6)
        .contentShape(Rectangle())
        .onTapGesture {
            copyToClipboard(title)
        }
    }

    private func copyToClipboard(_ text: String) {
        UIPasteboard.general.string = text
        copied = true
        Task {
            try? await Task.sleep(for: .seconds(1.5))
            copied = false
        }
    }
}

// MARK: - 概要欄カード

private struct DescriptionCard: View {
    let text: String
    @State private var copied = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("概要欄テキスト", systemImage: "doc.text")
                    .font(.headline)
                    .foregroundStyle(.white)

                Spacer()

                // コピーボタン
                Button {
                    UIPasteboard.general.string = text
                    copied = true
                    Task {
                        try? await Task.sleep(for: .seconds(1.5))
                        copied = false
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: copied ? "checkmark" : "doc.on.doc")
                        Text(copied ? "コピー済" : "コピー")
                            .font(.caption)
                    }
                    .foregroundStyle(copied ? .green : AppTheme.accent)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background((copied ? Color.green : AppTheme.accent).opacity(0.15))
                    .clipShape(Capsule())
                }
            }

            Text(text)
                .font(.caption)
                .foregroundStyle(.white.opacity(0.85))
                .frame(maxWidth: .infinity, alignment: .leading)
                .lineLimit(nil)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}
