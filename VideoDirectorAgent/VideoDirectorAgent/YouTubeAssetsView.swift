import SwiftUI
import UIKit

struct YouTubeAssetsView: View {
    let projectId: String

    @State private var assets: YouTubeAssets?
    @State private var selectedTitleIndex = 0
    @State private var editedTitle = ""
    @State private var descriptionText = ""
    @State private var isLoading = true
    @State private var isSavingTitle = false
    @State private var isSavingDescription = false
    @State private var bannerMessage: String?
    @State private var showUpdateBanner = false
    @State private var lastKnownEditedBy: String?
    @State private var pollingTimer: Timer?

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if showUpdateBanner {
                updateBanner
            }

            if let bannerMessage {
                banner(text: bannerMessage)
            }

            if isLoading {
                loadingCard
            } else if let assets {
                thumbnailSection(assets)
                titleSection(assets)
                descriptionSection(assets)
            } else {
                emptyCard
            }
        }
        .task {
            await loadAssets()
        }
        .onAppear {
            startPolling()
        }
        .onDisappear {
            stopPolling()
        }
    }

    private var loadingCard: some View {
        HStack(spacing: 12) {
            ProgressView()
                .tint(AppTheme.accent)
            Text("YouTube素材を読み込み中")
                .foregroundStyle(AppTheme.textSecondary)
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var emptyCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("YouTube素材がまだ同期されていません")
                .font(AppTheme.sectionFont(18))
                .foregroundStyle(.white)
            Text("Pythonパイプラインの API 同期後に、サムネ指示書・タイトル案・概要欄がここに表示されます。")
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textSecondary)
            Button("再読み込み") {
                Task { await loadAssets() }
            }
            .font(AppTheme.labelFont(13))
            .foregroundStyle(.white)
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(AppTheme.accent)
            .clipShape(Capsule())
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func thumbnailSection(_ assets: YouTubeAssets) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionTitle("サムネイル指示書", icon: "rectangle.on.rectangle")

            if let design = assets.thumbnailDesign {
                metadataPill(title: "全体コンセプト", value: design.overallConcept)
                metadataPill(title: "フォント", value: design.fontSuggestion)
                metadataPill(title: "背景", value: design.backgroundSuggestion)

                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                    ForEach(Array(design.zones.enumerated()), id: \.element.id) { index, zone in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(zonePositionLabel(for: index))
                                .font(AppTheme.labelFont(10))
                                .foregroundStyle(AppTheme.textMuted)

                            Text(zone.role)
                                .font(AppTheme.labelFont(12))
                                .foregroundStyle(.white)
                            Text(zone.content)
                                .font(AppTheme.bodyFont(14, weight: .semibold))
                                .foregroundStyle(.white)
                                .fixedSize(horizontal: false, vertical: true)
                            Text(zone.notes)
                                .font(AppTheme.bodyFont(12))
                                .foregroundStyle(AppTheme.textSecondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, minHeight: 132, alignment: .topLeading)
                        .background(zoneColor(zone.colorSuggestion))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }
            } else {
                Text("サムネイル指示書は未生成です。")
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
        .padding(18)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func titleSection(_ assets: YouTubeAssets) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionTitle("タイトル案", icon: "text.quote")

            if let proposals = assets.titleProposals {
                ForEach(Array(proposals.candidates.enumerated()), id: \.offset) { index, candidate in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: selectedTitleIndex == index ? "largecircle.fill.circle" : "circle")
                                .foregroundStyle(selectedTitleIndex == index ? AppTheme.accent : AppTheme.textMuted)
                            VStack(alignment: .leading, spacing: 8) {
                                HStack(spacing: 8) {
                                    if proposals.recommendedIndex == index {
                                        Text("推奨")
                                            .font(AppTheme.labelFont(11))
                                            .foregroundStyle(.black)
                                            .padding(.horizontal, 8)
                                            .padding(.vertical, 4)
                                            .background(Color(hex: 0xD4AF37))
                                            .clipShape(Capsule())
                                    }
                                    Text(candidate.appealType)
                                        .font(AppTheme.labelFont(11))
                                        .foregroundStyle(AppTheme.textMuted)
                                }

                                Text(candidate.title)
                                    .font(AppTheme.bodyFont(15, weight: .bold))
                                    .foregroundStyle(.white)
                                    .fixedSize(horizontal: false, vertical: true)

                                Text("対象: \(candidate.targetSegment)")
                                    .font(AppTheme.bodyFont(12))
                                    .foregroundStyle(AppTheme.textSecondary)

                                Text(candidate.rationale)
                                    .font(AppTheme.bodyFont(12))
                                    .foregroundStyle(AppTheme.textMuted)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture {
                            selectedTitleIndex = index
                            if editedTitle.isEmpty {
                                editedTitle = candidate.title
                            }
                        }

                        if selectedTitleIndex == index {
                            TextField("選択タイトルを微修正", text: $editedTitle)
                                .textFieldStyle(.plain)
                                .font(AppTheme.bodyFont(14))
                                .foregroundStyle(.white)
                                .padding(12)
                                .background(AppTheme.cardBackgroundLight)
                                .clipShape(RoundedRectangle(cornerRadius: 10))

                            Button {
                                Task { await saveSelectedTitle() }
                            } label: {
                                HStack {
                                    if isSavingTitle {
                                        ProgressView().tint(.white)
                                    }
                                    Text("このタイトルで確定")
                                }
                                .font(AppTheme.labelFont(13))
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                                .background(AppTheme.accent)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                            .disabled(isSavingTitle)
                        }
                    }
                    .padding(14)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            } else {
                Text("タイトル案は未生成です。")
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
        .padding(18)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func descriptionSection(_ assets: YouTubeAssets) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionTitle("概要欄", icon: "doc.text")

            TextEditor(text: $descriptionText)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 220)
                .font(.system(.body, design: .monospaced))
                .foregroundStyle(.white)
                .padding(8)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 12))

            HStack(spacing: 10) {
                Button("コピー") {
                    UIPasteboard.general.string = descriptionText
                    bannerMessage = "概要欄をクリップボードにコピーしました"
                }
                .buttonStyle(SecondaryActionButtonStyle())

                Button("リセット") {
                    descriptionText = assets.descriptionOriginal ?? ""
                    bannerMessage = "AI生成版に戻しました"
                }
                .buttonStyle(SecondaryActionButtonStyle())

                Button {
                    Task { await saveDescription() }
                } label: {
                    HStack {
                        if isSavingDescription {
                            ProgressView().tint(.white)
                        }
                        Text("確定保存")
                    }
                }
                .buttonStyle(PrimaryActionButtonStyle())
                .disabled(isSavingDescription)
            }

            if let lastEditedBy = assets.lastEditedBy ?? assets.descriptionFinalizedBy,
               let updatedAt = assets.updatedAt ?? assets.descriptionFinalizedAt {
                Text("\(lastEditedBy)が更新: \(relativeLabel(from: updatedAt))")
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
        .padding(18)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private func loadAssets() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let loaded = try await APIClient.shared.fetchYouTubeAssets(projectId: projectId)
            applyLoadedAssets(loaded)
            bannerMessage = nil
        } catch {
            bannerMessage = "YouTube素材APIに接続できません: \(error.localizedDescription)"
        }
    }

    private func applyLoadedAssets(_ loaded: YouTubeAssets) {
        assets = loaded
        lastKnownEditedBy = loaded.lastEditedBy
        selectedTitleIndex = loaded.selectedTitleIndex ?? loaded.titleProposals?.recommendedIndex ?? 0
        if let editedTitle = loaded.editedTitle, !editedTitle.isEmpty {
            self.editedTitle = editedTitle
        } else if let candidates = loaded.titleProposals?.candidates, candidates.indices.contains(selectedTitleIndex) {
            editedTitle = candidates[selectedTitleIndex].title
        } else {
            editedTitle = ""
        }
        descriptionText = loaded.activeDescription
    }

    private func startPolling() {
        stopPolling()
        pollingTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in
            Task { @MainActor in
                await pollForUpdates()
            }
        }
    }

    private func stopPolling() {
        pollingTimer?.invalidate()
        pollingTimer = nil
    }

    private func pollForUpdates() async {
        do {
            let latest = try await APIClient.shared.fetchYouTubeAssets(projectId: projectId)
            if let editedBy = latest.lastEditedBy,
               editedBy != "naoto",
               editedBy != "なおとさん",
               editedBy != lastKnownEditedBy {
                applyLoadedAssets(latest)
                showUpdateBanner = true
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                    showUpdateBanner = false
                }
            } else {
                applyLoadedAssets(latest)
            }
        } catch {
        }
    }

    private func saveSelectedTitle() async {
        guard let assets else { return }
        isSavingTitle = true
        defer { isSavingTitle = false }

        do {
            let finalTitle = editedTitle.trimmingCharacters(in: .whitespacesAndNewlines)
            try await APIClient.shared.selectTitle(
                projectId: projectId,
                index: selectedTitleIndex,
                editedTitle: finalTitle.isEmpty ? nil : finalTitle,
                by: "naoto"
            )
            self.assets?.selectedTitleIndex = selectedTitleIndex
            self.assets?.editedTitle = finalTitle.isEmpty ? nil : finalTitle
            self.assets?.lastEditedBy = "naoto"
            bannerMessage = "タイトル案を保存しました"
        } catch {
            bannerMessage = "タイトル保存に失敗しました"
            // API失敗時もローカル表示は更新
            self.assets?.selectedTitleIndex = selectedTitleIndex
            self.assets?.editedTitle = editedTitle
        }
    }

    private func saveDescription() async {
        isSavingDescription = true
        defer { isSavingDescription = false }

        do {
            try await APIClient.shared.updateDescription(projectId: projectId, edited: descriptionText, by: "naoto")
            self.assets?.descriptionEdited = descriptionText
            self.assets?.lastEditedBy = "naoto"
            bannerMessage = "概要欄を保存しました"
        } catch {
            bannerMessage = "概要欄保存に失敗しました: \(error.localizedDescription)"
        }
    }

    private var updateBanner: some View {
        HStack {
            Image(systemName: "arrow.triangle.2.circlepath")
            Text("パグさんが更新しました")
        }
        .font(.caption)
        .fontWeight(.bold)
        .foregroundStyle(.white)
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color(hex: 0x4A90D9))
        .clipShape(Capsule())
        .transition(.move(edge: .top).combined(with: .opacity))
        .animation(.easeInOut, value: showUpdateBanner)
    }

    private func banner(text: String) -> some View {
        Text(text)
            .font(AppTheme.bodyFont(12, weight: .semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(AppTheme.accent.opacity(0.85))
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func sectionTitle(_ title: String, icon: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(AppTheme.accent)
            Text(title)
                .font(AppTheme.sectionFont(18))
                .foregroundStyle(.white)
        }
    }

    private func metadataPill(title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)
            Text(value)
                .font(AppTheme.bodyFont(13, weight: .semibold))
                .foregroundStyle(AppTheme.textSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func zoneColor(_ suggestion: String) -> Color {
        let normalized = suggestion.lowercased()
        if normalized.contains("赤") || normalized.contains("red") {
            return Color(hex: 0x6B1010)
        }
        if normalized.contains("黄") || normalized.contains("gold") {
            return Color(hex: 0x6B5410)
        }
        if normalized.contains("青") || normalized.contains("navy") {
            return Color(hex: 0x102C5C)
        }
        return AppTheme.cardBackgroundLight
    }

    private func zonePositionLabel(for index: Int) -> String {
        switch index {
        case 0: return "左上"
        case 1: return "右上"
        case 2: return "対角"
        case 3: return "右下"
        default: return "ゾーン"
        }
    }

    private func relativeLabel(from isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: isoString) else { return isoString }
        let interval = Int(Date().timeIntervalSince(date))
        if interval < 60 { return "\(max(interval, 0))秒前" }
        if interval < 3600 { return "\(interval / 60)分前" }
        if interval < 86400 { return "\(interval / 3600)時間前" }
        return "\(interval / 86400)日前"
    }
}

private struct PrimaryActionButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(AppTheme.labelFont(13))
            .foregroundStyle(.white)
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity)
            .background(AppTheme.accent.opacity(configuration.isPressed ? 0.85 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct SecondaryActionButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(AppTheme.labelFont(13))
            .foregroundStyle(.white)
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity)
            .background(AppTheme.cardBackgroundLight.opacity(configuration.isPressed ? 0.8 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(AppTheme.textMuted.opacity(0.25), lineWidth: 1)
            )
    }
}
