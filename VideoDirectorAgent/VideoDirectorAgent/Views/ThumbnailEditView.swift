import SwiftUI

// MARK: - サムネ指示書の手修正画面
struct ThumbnailEditView: View {
    let projectId: String
    let projectTitle: String

    // Z型4ゾーンデータ
    @State private var hookText = ""           // 左上フック
    @State private var hookFontNote = ""
    @State private var hookImageNote = ""

    @State private var personText = ""         // 右上人物
    @State private var personFontNote = ""
    @State private var personImageNote = ""

    @State private var contentText = ""        // 斜め降下コンテンツ
    @State private var contentFontNote = ""
    @State private var contentImageNote = ""

    @State private var benefitText = ""        // 右下ベネフィット
    @State private var benefitFontNote = ""
    @State private var benefitImageNote = ""

    // 全体設定
    @State private var overallConcept = ""
    @State private var fontProposal = ""
    @State private var backgroundProposal = ""

    // 元テキスト（diff用）
    @State private var originalContent = ""

    // UI状態
    @State private var selectedEditor = "なおとさん"
    @State private var expandedZone: String?    // 1つだけ展開
    @State private var isSaving = false
    @State private var isLoading = false
    @State private var showDiff = false
    @State private var saveSuccess = false
    @State private var errorMessage: String?

    private let editors = ["なおとさん", "パグさん"]

    // ゾーン定義
    private struct ZoneConfig {
        let id: String
        let title: String
        let icon: String
        let borderColor: Color
    }

    private let zones: [ZoneConfig] = [
        ZoneConfig(id: "hook", title: "左上 フック", icon: "exclamationmark.triangle.fill", borderColor: Color(hex: 0xd32f2f)),
        ZoneConfig(id: "person", title: "右上 人物", icon: "person.fill", borderColor: Color(hex: 0x1565c0)),
        ZoneConfig(id: "content", title: "斜め降下 コンテンツ", icon: "arrow.down.right", borderColor: Color(hex: 0xff9800)),
        ZoneConfig(id: "benefit", title: "右下 ベネフィット", icon: "gift.fill", borderColor: Color(hex: 0x2e7d32)),
    ]

    var body: some View {
        ZStack {
            AppTheme.background.ignoresSafeArea()

            if isLoading {
                loadingView
            } else {
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: 16) {
                        // ヘッダー
                        headerCard

                        // 編集者選択
                        editorPickerSection

                        // Z型レイアウトプレビュー（2x2グリッド）
                        zLayoutPreview

                        // 各ゾーンカード
                        ForEach(zones, id: \.id) { zone in
                            zoneCard(zone)
                        }

                        // 全体設定
                        overallSettingsSection

                        // diff表示
                        if showDiff {
                            diffSection
                        }

                        Spacer(minLength: 100)
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 16)
                }
            }

            // 成功トースト
            if saveSuccess {
                VStack {
                    successToast
                    Spacer()
                }
                .transition(.move(edge: .top).combined(with: .opacity))
                .animation(.easeInOut(duration: 0.3), value: saveSuccess)
            }
        }
        .navigationTitle("サムネ指示編集")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .overlay(alignment: .bottom) {
            saveButton
        }
        .task {
            await loadCurrentData()
        }
    }

    // MARK: - ヘッダーカード

    private var headerCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "photo.artframe")
                    .foregroundStyle(AppTheme.accent)
                Text("サムネ指示書編集")
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)
            }
            Text(projectTitle)
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textSecondary)
            Text("Z型4ゾーン構成")
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 編集者Picker

    private var editorPickerSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "person.fill")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(AppTheme.accent)
                Text("編集者")
                    .font(AppTheme.labelFont(13))
                    .foregroundStyle(AppTheme.textMuted)
            }

            Picker("編集者", selection: $selectedEditor) {
                ForEach(editors, id: \.self) { editor in
                    Text(editor).tag(editor)
                }
            }
            .pickerStyle(.segmented)
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Z型レイアウトプレビュー（ミニマップ）

    private var zLayoutPreview: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "square.grid.2x2")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(AppTheme.accent)
                Text("Z型レイアウト")
                    .font(AppTheme.labelFont(13))
                    .foregroundStyle(AppTheme.textMuted)
            }

            // 2x2グリッド
            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 8),
                GridItem(.flexible(), spacing: 8)
            ], spacing: 8) {
                zonePreviewCell("フック", Color(hex: 0xd32f2f), hookText)
                zonePreviewCell("人物", Color(hex: 0x1565c0), personText)
                zonePreviewCell("コンテンツ", Color(hex: 0xff9800), contentText)
                zonePreviewCell("ベネフィット", Color(hex: 0x2e7d32), benefitText)
            }

            // Z型矢印（装飾）
            HStack {
                Spacer()
                Text("Z")
                    .font(AppTheme.heroFont(24))
                    .foregroundStyle(AppTheme.textMuted.opacity(0.3))
                Spacer()
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func zonePreviewCell(_ label: String, _ color: Color, _ text: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(AppTheme.labelFont(10))
                .foregroundStyle(color)
            Text(text.isEmpty ? "未入力" : text)
                .font(AppTheme.bodyFont(11))
                .foregroundStyle(text.isEmpty ? AppTheme.textMuted : AppTheme.textSecondary)
                .lineLimit(2)
        }
        .padding(10)
        .frame(maxWidth: .infinity, minHeight: 60, alignment: .topLeading)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(color.opacity(0.5), lineWidth: 2)
        )
    }

    // MARK: - ゾーンカード（タップで展開 → 編集）

    private func zoneCard(_ zone: ZoneConfig) -> some View {
        let isExpanded = expandedZone == zone.id

        return VStack(alignment: .leading, spacing: 0) {
            // ゾーンヘッダー（タップで展開/折りたたみ）
            Button {
                withAnimation(.easeInOut(duration: 0.25)) {
                    expandedZone = isExpanded ? nil : zone.id
                }
            } label: {
                HStack {
                    Image(systemName: zone.icon)
                        .foregroundStyle(zone.borderColor)
                    Text(zone.title)
                        .font(.headline)
                        .foregroundStyle(.white)
                    Spacer()
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
                .padding(16)
            }

            // 展開時の編集フォーム
            if isExpanded {
                VStack(alignment: .leading, spacing: 12) {
                    // テキスト内容
                    VStack(alignment: .leading, spacing: 4) {
                        Text("テキスト")
                            .font(AppTheme.labelFont(11))
                            .foregroundStyle(AppTheme.textMuted)
                        TextField("テキストを入力", text: textBinding(for: zone.id))
                            .font(AppTheme.bodyFont(14))
                            .foregroundStyle(AppTheme.textPrimary)
                            .padding(10)
                            .background(AppTheme.cardBackgroundLight)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }

                    // フォント指示
                    VStack(alignment: .leading, spacing: 4) {
                        Text("フォント指示")
                            .font(AppTheme.labelFont(11))
                            .foregroundStyle(AppTheme.textMuted)
                        TextField("フォントスタイル・サイズ等", text: fontBinding(for: zone.id))
                            .font(AppTheme.bodyFont(14))
                            .foregroundStyle(AppTheme.textPrimary)
                            .padding(10)
                            .background(AppTheme.cardBackgroundLight)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }

                    // 画像指示
                    VStack(alignment: .leading, spacing: 4) {
                        Text("画像指示")
                            .font(AppTheme.labelFont(11))
                            .foregroundStyle(AppTheme.textMuted)
                        TextField("画像の配置・スタイル等", text: imageBinding(for: zone.id))
                            .font(AppTheme.bodyFont(14))
                            .foregroundStyle(AppTheme.textPrimary)
                            .padding(10)
                            .background(AppTheme.cardBackgroundLight)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 16)
            }
        }
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(zone.borderColor.opacity(isExpanded ? 0.6 : 0.2), lineWidth: isExpanded ? 2 : 1)
        )
    }

    // MARK: - 全体設定セクション

    private var overallSettingsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "gearshape.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("全体設定")
                    .font(.headline)
                    .foregroundStyle(.white)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("全体コンセプト")
                    .font(AppTheme.labelFont(11))
                    .foregroundStyle(AppTheme.textMuted)
                TextEditor(text: $overallConcept)
                    .font(AppTheme.bodyFont(14))
                    .foregroundStyle(AppTheme.textSecondary)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 80)
                    .padding(8)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("フォント提案")
                    .font(AppTheme.labelFont(11))
                    .foregroundStyle(AppTheme.textMuted)
                TextField("使用フォントの提案", text: $fontProposal)
                    .font(AppTheme.bodyFont(14))
                    .foregroundStyle(AppTheme.textPrimary)
                    .padding(10)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("背景提案")
                    .font(AppTheme.labelFont(11))
                    .foregroundStyle(AppTheme.textMuted)
                TextField("背景画像・グラデーション等", text: $backgroundProposal)
                    .font(AppTheme.bodyFont(14))
                    .foregroundStyle(AppTheme.textPrimary)
                    .padding(10)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Diff表示

    private var diffSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "arrow.left.arrow.right")
                    .foregroundStyle(AppTheme.accent)
                Text("変更差分")
                    .font(AppTheme.sectionFont(16))
                    .foregroundStyle(.white)
            }

            let currentContent = buildContent()
            if originalContent == currentContent {
                Text("変更なし")
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(AppTheme.textMuted)
            } else {
                if !originalContent.isEmpty {
                    Text("変更前")
                        .font(AppTheme.labelFont(10))
                        .foregroundStyle(AppTheme.accent.opacity(0.8))
                    Text(originalContent)
                        .font(AppTheme.bodyFont(11))
                        .foregroundStyle(AppTheme.accent)
                        .lineLimit(10)
                        .padding(8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(AppTheme.accent.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                }

                Text("変更後")
                    .font(AppTheme.labelFont(10))
                    .foregroundStyle(AppTheme.statusComplete.opacity(0.8))
                Text(currentContent)
                    .font(AppTheme.bodyFont(11))
                    .foregroundStyle(AppTheme.statusComplete)
                    .lineLimit(10)
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.statusComplete.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 保存ボタン

    private var saveButton: some View {
        HStack(spacing: 16) {
            Button {
                Task { await saveThumbnail() }
            } label: {
                HStack(spacing: 8) {
                    if isSaving {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "checkmark.circle.fill")
                            .font(.system(size: 16, weight: .bold))
                    }
                    Text("保存")
                        .font(.subheadline)
                        .fontWeight(.bold)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(isSaving ? AppTheme.textMuted : AppTheme.accent)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            .disabled(isSaving)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(
            Rectangle()
                .fill(AppTheme.cardBackground)
                .shadow(color: .black.opacity(0.5), radius: 10, y: -2)
                .ignoresSafeArea(edges: .bottom)
        )
    }

    // MARK: - 成功トースト

    private var successToast: some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(AppTheme.statusComplete)
                .font(.system(size: 20))
            Text("保存しました")
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundStyle(.white)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(
            Capsule()
                .fill(AppTheme.cardBackground)
                .shadow(color: .black.opacity(0.3), radius: 8, y: 2)
        )
        .padding(.top, 60)
    }

    // MARK: - ローディング

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .progressViewStyle(.circular)
                .tint(AppTheme.accent)
                .scaleEffect(1.5)
            Text("サムネ指示を読み込み中...")
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    // MARK: - Binding ヘルパー

    private func textBinding(for zoneId: String) -> Binding<String> {
        switch zoneId {
        case "hook": return $hookText
        case "person": return $personText
        case "content": return $contentText
        case "benefit": return $benefitText
        default: return .constant("")
        }
    }

    private func fontBinding(for zoneId: String) -> Binding<String> {
        switch zoneId {
        case "hook": return $hookFontNote
        case "person": return $personFontNote
        case "content": return $contentFontNote
        case "benefit": return $benefitFontNote
        default: return .constant("")
        }
    }

    private func imageBinding(for zoneId: String) -> Binding<String> {
        switch zoneId {
        case "hook": return $hookImageNote
        case "person": return $personImageNote
        case "content": return $contentImageNote
        case "benefit": return $benefitImageNote
        default: return .constant("")
        }
    }

    // MARK: - コンテンツ構築

    private func buildContent() -> String {
        var parts: [String] = []

        parts.append("## Z型レイアウト")

        if !hookText.isEmpty || !hookFontNote.isEmpty || !hookImageNote.isEmpty {
            parts.append("### 左上 フック")
            if !hookText.isEmpty { parts.append("テキスト: \(hookText)") }
            if !hookFontNote.isEmpty { parts.append("フォント: \(hookFontNote)") }
            if !hookImageNote.isEmpty { parts.append("画像: \(hookImageNote)") }
        }

        if !personText.isEmpty || !personFontNote.isEmpty || !personImageNote.isEmpty {
            parts.append("### 右上 人物")
            if !personText.isEmpty { parts.append("テキスト: \(personText)") }
            if !personFontNote.isEmpty { parts.append("フォント: \(personFontNote)") }
            if !personImageNote.isEmpty { parts.append("画像: \(personImageNote)") }
        }

        if !contentText.isEmpty || !contentFontNote.isEmpty || !contentImageNote.isEmpty {
            parts.append("### 斜め降下 コンテンツ")
            if !contentText.isEmpty { parts.append("テキスト: \(contentText)") }
            if !contentFontNote.isEmpty { parts.append("フォント: \(contentFontNote)") }
            if !contentImageNote.isEmpty { parts.append("画像: \(contentImageNote)") }
        }

        if !benefitText.isEmpty || !benefitFontNote.isEmpty || !benefitImageNote.isEmpty {
            parts.append("### 右下 ベネフィット")
            if !benefitText.isEmpty { parts.append("テキスト: \(benefitText)") }
            if !benefitFontNote.isEmpty { parts.append("フォント: \(benefitFontNote)") }
            if !benefitImageNote.isEmpty { parts.append("画像: \(benefitImageNote)") }
        }

        if !overallConcept.isEmpty {
            parts.append("\n## 全体コンセプト\n\(overallConcept)")
        }
        if !fontProposal.isEmpty {
            parts.append("\n## フォント提案\n\(fontProposal)")
        }
        if !backgroundProposal.isEmpty {
            parts.append("\n## 背景提案\n\(backgroundProposal)")
        }

        return parts.joined(separator: "\n")
    }

    // MARK: - データ操作

    private func loadCurrentData() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let diff = try await APIClient.shared.fetchAssetEditDiff(projectId: projectId, assetType: "thumbnail")
            if let current = diff["current"] as? String {
                originalContent = current
                // テキストのパース（簡易的に全体をoverallConceptに入れる。本来はサーバー側の構造化データに合わせる）
                overallConcept = current
            }
        } catch {
            // 初回は空で開始
        }
    }

    private func saveThumbnail() async {
        isSaving = true
        defer { isSaving = false }

        let content = buildContent()

        do {
            _ = try await APIClient.shared.updateThumbnailInstruction(
                projectId: projectId,
                editedContent: content,
                editedBy: selectedEditor
            )
            showDiff = true
            saveSuccess = true
            originalContent = content

            Task {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                saveSuccess = false
            }
        } catch {
            errorMessage = "保存に失敗しました: \(error.localizedDescription)"
        }
    }
}
