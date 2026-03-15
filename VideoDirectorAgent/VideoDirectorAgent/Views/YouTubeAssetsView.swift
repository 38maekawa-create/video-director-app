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
    @State private var copiedItemId: String?

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

    // MARK: - ローディング・空状態

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

    // MARK: - サムネイル指示書セクション（Z型4ゾーン）

    private func thumbnailSection(_ assets: YouTubeAssets) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                sectionTitle("サムネイル指示書", icon: "rectangle.on.rectangle")
                Spacer()
                // サムネ指示書全体コピーボタン
                if let design = assets.thumbnailDesign {
                    copyButton(id: "thumbnail-all") {
                        thumbnailDesignAsText(design)
                    }
                }
            }

            if let design = assets.thumbnailDesign {
                // 全体コンセプト
                VStack(alignment: .leading, spacing: 8) {
                    Text("全体コンセプト")
                        .font(AppTheme.labelFont(11))
                        .foregroundStyle(AppTheme.accent)
                    Text(design.overallConcept)
                        .font(AppTheme.bodyFont(14, weight: .semibold))
                        .foregroundStyle(.white)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 10))

                // メタデータ（フォント・背景）横並び
                HStack(spacing: 10) {
                    metadataPill(title: "フォント", value: design.fontSuggestion)
                    metadataPill(title: "背景", value: design.backgroundSuggestion)
                }

                // Z型4ゾーンレイアウト（Z字の読み順を示す矢印付き）
                VStack(spacing: 4) {
                    HStack(spacing: 4) {
                        Text("Z型レイアウト")
                            .font(AppTheme.labelFont(11))
                            .foregroundStyle(AppTheme.textMuted)
                        Image(systemName: "arrow.right")
                            .font(.system(size: 9))
                            .foregroundStyle(AppTheme.textMuted)
                        Spacer()
                    }
                    .padding(.bottom, 4)

                    // Z型: 左上→右上 / 対角 / 右下
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                        ForEach(Array(design.zones.enumerated()), id: \.element.id) { index, zone in
                            zoneCard(zone: zone, index: index)
                        }
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

    private func zoneCard(zone: ThumbnailZone, index: Int) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            // ゾーン位置ラベル + Z字順番号
            HStack(spacing: 6) {
                Text("\(index + 1)")
                    .font(.system(size: 10, weight: .heavy, design: .rounded))
                    .foregroundStyle(.black)
                    .frame(width: 18, height: 18)
                    .background(Color(hex: 0xD4AF37))
                    .clipShape(Circle())

                Text(zonePositionLabel(for: index))
                    .font(AppTheme.labelFont(10))
                    .foregroundStyle(AppTheme.textMuted)

                Spacer()
            }

            // 役割
            Text(zone.role)
                .font(AppTheme.labelFont(12))
                .foregroundStyle(AppTheme.accent)

            // コンテンツ（メインテキスト）
            Text(zone.content)
                .font(AppTheme.bodyFont(14, weight: .bold))
                .foregroundStyle(.white)
                .fixedSize(horizontal: false, vertical: true)

            // 補足ノート
            if !zone.notes.isEmpty {
                Text(zone.notes)
                    .font(AppTheme.bodyFont(11))
                    .foregroundStyle(AppTheme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            // 色指定
            HStack(spacing: 4) {
                Circle()
                    .fill(zoneColor(zone.colorSuggestion))
                    .frame(width: 10, height: 10)
                Text(zone.colorSuggestion)
                    .font(AppTheme.bodyFont(10))
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 120, alignment: .topLeading)
        .background(zoneColor(zone.colorSuggestion).opacity(0.15))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(zoneColor(zone.colorSuggestion).opacity(0.4), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - タイトル案セクション

    private func titleSection(_ assets: YouTubeAssets) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionTitle("タイトル案", icon: "text.quote")

            if let proposals = assets.titleProposals {
                ForEach(Array(proposals.candidates.enumerated()), id: \.offset) { index, candidate in
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(alignment: .top, spacing: 10) {
                            // 選択ラジオ
                            Image(systemName: selectedTitleIndex == index ? "largecircle.fill.circle" : "circle")
                                .foregroundStyle(selectedTitleIndex == index ? AppTheme.accent : AppTheme.textMuted)
                                .font(.system(size: 20))

                            VStack(alignment: .leading, spacing: 8) {
                                // バッジ行
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
                                    Spacer()
                                    // コピーボタン
                                    copyButton(id: "title-\(index)") {
                                        candidate.title
                                    }
                                }

                                // タイトルテキスト
                                Text(candidate.title)
                                    .font(AppTheme.bodyFont(15, weight: .bold))
                                    .foregroundStyle(.white)
                                    .fixedSize(horizontal: false, vertical: true)

                                // 対象セグメント
                                Text("対象: \(candidate.targetSegment)")
                                    .font(AppTheme.bodyFont(12))
                                    .foregroundStyle(AppTheme.textSecondary)

                                // 理由
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

                        // 選択時の編集・確定UI
                        if selectedTitleIndex == index {
                            TextField("選択タイトルを微修正", text: $editedTitle)
                                .textFieldStyle(.plain)
                                .font(AppTheme.bodyFont(14))
                                .foregroundStyle(.white)
                                .padding(12)
                                .background(AppTheme.cardBackgroundLight)
                                .clipShape(RoundedRectangle(cornerRadius: 10))

                            HStack(spacing: 10) {
                                // 編集後のタイトルをコピー
                                Button {
                                    let text = editedTitle.isEmpty ? candidate.title : editedTitle
                                    UIPasteboard.general.string = text
                                    showCopiedFeedback(id: "title-edited-\(index)")
                                } label: {
                                    HStack(spacing: 4) {
                                        Image(systemName: copiedItemId == "title-edited-\(index)" ? "checkmark" : "doc.on.doc")
                                            .font(.system(size: 12))
                                        Text("コピー")
                                    }
                                }
                                .buttonStyle(SecondaryActionButtonStyle())

                                Button {
                                    Task { await saveSelectedTitle() }
                                } label: {
                                    HStack {
                                        if isSavingTitle {
                                            ProgressView().tint(.white)
                                        }
                                        Text("このタイトルで確定")
                                    }
                                }
                                .buttonStyle(PrimaryActionButtonStyle())
                                .disabled(isSavingTitle)
                            }
                        }
                    }
                    .padding(14)
                    .background(
                        selectedTitleIndex == index
                            ? AppTheme.accent.opacity(0.08)
                            : AppTheme.cardBackgroundLight.opacity(1)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(
                                selectedTitleIndex == index ? AppTheme.accent.opacity(0.4) : Color.clear,
                                lineWidth: 1
                            )
                    )
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

    // MARK: - 概要欄セクション

    private func descriptionSection(_ assets: YouTubeAssets) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                sectionTitle("概要欄", icon: "doc.text")
                Spacer()
                // 概要欄全体コピーボタン
                copyButton(id: "description-all") {
                    descriptionText
                }
            }

            TextEditor(text: $descriptionText)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 220)
                .font(.system(.body, design: .monospaced))
                .foregroundStyle(.white)
                .padding(8)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 12))

            HStack(spacing: 10) {
                Button {
                    UIPasteboard.general.string = descriptionText
                    showCopiedFeedback(id: "description-copy")
                    bannerMessage = "概要欄をクリップボードにコピーしました"
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: copiedItemId == "description-copy" ? "checkmark" : "doc.on.doc")
                            .font(.system(size: 12))
                        Text("コピー")
                    }
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

    // MARK: - コピーボタン共通コンポーネント

    private func copyButton(id: String, text: @escaping () -> String) -> some View {
        Button {
            UIPasteboard.general.string = text()
            showCopiedFeedback(id: id)
        } label: {
            HStack(spacing: 4) {
                Image(systemName: copiedItemId == id ? "checkmark.circle.fill" : "doc.on.doc")
                    .font(.system(size: 13))
                Text(copiedItemId == id ? "コピー済" : "コピー")
                    .font(AppTheme.labelFont(11))
            }
            .foregroundStyle(copiedItemId == id ? AppTheme.statusComplete : AppTheme.textSecondary)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(AppTheme.cardBackgroundLight)
            .clipShape(Capsule())
        }
    }

    private func showCopiedFeedback(id: String) {
        withAnimation(.easeInOut(duration: 0.2)) {
            copiedItemId = id
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            withAnimation(.easeInOut(duration: 0.2)) {
                if copiedItemId == id {
                    copiedItemId = nil
                }
            }
        }
    }

    // MARK: - サムネ指示書テキスト化（コピー用）

    private func thumbnailDesignAsText(_ design: ThumbnailDesign) -> String {
        var lines: [String] = []
        lines.append("【サムネイル指示書】")
        lines.append("コンセプト: \(design.overallConcept)")
        lines.append("フォント: \(design.fontSuggestion)")
        lines.append("背景: \(design.backgroundSuggestion)")
        lines.append("")
        for (index, zone) in design.zones.enumerated() {
            let pos = zonePositionLabel(for: index)
            lines.append("[\(pos)] \(zone.role)")
            lines.append("  テキスト: \(zone.content)")
            if !zone.notes.isEmpty {
                lines.append("  補足: \(zone.notes)")
            }
            lines.append("  色: \(zone.colorSuggestion)")
            lines.append("")
        }
        return lines.joined(separator: "\n")
    }

    // MARK: - データ取得・保存

    private func loadAssets() async {
        isLoading = true
        defer { isLoading = false }

        do {
            let loaded = try await APIClient.shared.fetchYouTubeAssets(projectId: projectId)
            applyLoadedAssets(loaded)
            bannerMessage = nil
        } catch {
            assets = nil
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
               editedBy != APIClient.shared.actorName,
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
            // ポーリング失敗は静かに無視
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
                by: APIClient.shared.actorName
            )
            self.assets?.selectedTitleIndex = selectedTitleIndex
            self.assets?.editedTitle = finalTitle.isEmpty ? nil : finalTitle
            self.assets?.lastEditedBy = APIClient.shared.actorName
            bannerMessage = "タイトル案を保存しました"
        } catch {
            bannerMessage = "タイトル保存に失敗しました: \(error.localizedDescription)"
        }
    }

    private func saveDescription() async {
        isSavingDescription = true
        defer { isSavingDescription = false }

        do {
            try await APIClient.shared.updateDescription(
                projectId: projectId,
                edited: descriptionText,
                by: APIClient.shared.actorName
            )
            self.assets?.descriptionEdited = descriptionText
            self.assets?.lastEditedBy = APIClient.shared.actorName
            bannerMessage = "概要欄を保存しました"
        } catch {
            bannerMessage = "概要欄保存に失敗しました: \(error.localizedDescription)"
        }
    }

    // MARK: - UI部品

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

// MARK: - ボタンスタイル

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
