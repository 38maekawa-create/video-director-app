import SwiftUI

// MARK: - ディレクションレポート手修正画面
struct DirectionEditView: View {
    let projectId: String
    let projectTitle: String

    // セクション別の編集テキスト
    @State private var directionText = ""
    @State private var telopText = ""
    @State private var bgmText = ""
    @State private var colorText = ""

    // 元テキスト（diff用）
    @State private var originalDirectionText = ""
    @State private var originalTelopText = ""
    @State private var originalBgmText = ""
    @State private var originalColorText = ""

    // UI状態
    @State private var expandedSections: Set<String> = ["direction", "telop", "bgm", "color"]
    @State private var selectedEditor = "なおとさん"
    @State private var editNotes = ""
    @State private var isSaving = false
    @State private var isLoading = false
    @State private var showDiff = false
    @State private var showHistory = false
    @State private var saveSuccess = false
    @State private var errorMessage: String?
    @State private var editHistory: [[String: Any]] = []
    @State private var diffData: [String: Any] = [:]

    private let editors = ["なおとさん", "パグさん"]

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

                        // セクション別編集フォーム
                        editableSection(
                            id: "direction",
                            title: "演出ディレクション",
                            icon: "film.fill",
                            text: $directionText
                        )

                        editableSection(
                            id: "telop",
                            title: "テロップ指示",
                            icon: "textformat.abc",
                            text: $telopText
                        )

                        editableSection(
                            id: "bgm",
                            title: "BGM指示",
                            icon: "music.note",
                            text: $bgmText
                        )

                        editableSection(
                            id: "color",
                            title: "色彩指示",
                            icon: "paintpalette.fill",
                            text: $colorText
                        )

                        // 編集メモ
                        editNotesSection

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
        .navigationTitle("ディレクション編集")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: 12) {
                    Button {
                        showHistory = true
                    } label: {
                        Image(systemName: "clock.arrow.circlepath")
                            .foregroundStyle(AppTheme.textSecondary)
                    }
                }
            }
        }
        .overlay(alignment: .bottom) {
            saveButton
        }
        .sheet(isPresented: $showHistory) {
            editHistorySheet
        }
        .task {
            await loadCurrentReport()
        }
    }

    // MARK: - ヘッダーカード

    private var headerCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "pencil.and.outline")
                    .foregroundStyle(AppTheme.accent)
                Text("手修正モード")
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)
            }
            Text(projectTitle)
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textSecondary)
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

    // MARK: - 折りたたみ可能な編集セクション

    private func editableSection(
        id: String,
        title: String,
        icon: String,
        text: Binding<String>
    ) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // セクションヘッダー（タップで折りたたみ）
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    if expandedSections.contains(id) {
                        expandedSections.remove(id)
                    } else {
                        expandedSections.insert(id)
                    }
                }
            } label: {
                HStack {
                    Image(systemName: icon)
                        .foregroundStyle(AppTheme.accent)
                    Text(title)
                        .font(.headline)
                        .foregroundStyle(.white)
                    Spacer()
                    Image(systemName: expandedSections.contains(id) ? "chevron.up" : "chevron.down")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
                .padding(16)
            }

            // 展開時のTextEditor
            if expandedSections.contains(id) {
                TextEditor(text: text)
                    .font(AppTheme.bodyFont(14))
                    .foregroundStyle(AppTheme.textSecondary)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 120)
                    .padding(.horizontal, 12)
                    .padding(.bottom, 12)
            }
        }
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 編集メモ

    private var editNotesSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "note.text")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(AppTheme.accent)
                Text("編集メモ（任意）")
                    .font(AppTheme.labelFont(13))
                    .foregroundStyle(AppTheme.textMuted)
            }

            TextField("修正理由やメモを入力", text: $editNotes)
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textSecondary)
                .padding(12)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Diff表示セクション

    private var diffSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "arrow.left.arrow.right")
                    .foregroundStyle(AppTheme.accent)
                Text("変更差分")
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)
            }

            diffRow(label: "演出ディレクション", original: originalDirectionText, edited: directionText)
            diffRow(label: "テロップ指示", original: originalTelopText, edited: telopText)
            diffRow(label: "BGM指示", original: originalBgmText, edited: bgmText)
            diffRow(label: "色彩指示", original: originalColorText, edited: colorText)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func diffRow(label: String, original: String, edited: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label)
                .font(AppTheme.labelFont(12))
                .foregroundStyle(AppTheme.textMuted)

            if original == edited {
                Text("変更なし")
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(AppTheme.textMuted)
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    // 元テキスト（赤背景）
                    if !original.isEmpty {
                        Text(original)
                            .font(AppTheme.bodyFont(12))
                            .foregroundStyle(AppTheme.accent)
                            .padding(8)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(AppTheme.accent.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                    // 修正テキスト（緑背景）
                    if !edited.isEmpty {
                        Text(edited)
                            .font(AppTheme.bodyFont(12))
                            .foregroundStyle(AppTheme.statusComplete)
                            .padding(8)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(AppTheme.statusComplete.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                }
            }
        }
    }

    // MARK: - 保存ボタン

    private var saveButton: some View {
        HStack(spacing: 16) {
            Button {
                Task { await saveReport() }
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

    // MARK: - 編集履歴シート

    private var editHistorySheet: some View {
        NavigationStack {
            ZStack {
                AppTheme.background.ignoresSafeArea()

                if editHistory.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "clock.arrow.circlepath")
                            .font(.system(size: 40))
                            .foregroundStyle(AppTheme.textMuted)
                        Text("編集履歴はまだありません")
                            .font(AppTheme.bodyFont(14))
                            .foregroundStyle(AppTheme.textMuted)
                    }
                } else {
                    ScrollView {
                        VStack(spacing: 12) {
                            ForEach(0..<editHistory.count, id: \.self) { index in
                                let entry = editHistory[index]
                                historyCard(entry)
                            }
                        }
                        .padding(16)
                    }
                }
            }
            .navigationTitle("編集履歴")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("閉じる") {
                        showHistory = false
                    }
                    .foregroundStyle(AppTheme.textSecondary)
                }
            }
            .task {
                await loadEditHistory()
            }
        }
    }

    private func historyCard(_ entry: [String: Any]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text((entry["edited_by"] as? String) ?? "不明")
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundStyle(AppTheme.accent)
                Spacer()
                Text((entry["edited_at"] as? String) ?? "")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textMuted)
            }
            if let notes = entry["edit_notes"] as? String, !notes.isEmpty {
                Text(notes)
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.textSecondary)
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - ローディング

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .progressViewStyle(.circular)
                .tint(AppTheme.accent)
                .scaleEffect(1.5)
            Text("レポートを読み込み中...")
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    // MARK: - データ操作

    private func loadCurrentReport() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let result = try await APIClient.shared.fetchDirectionEditDiff(projectId: projectId)
            if let current = result["current"] as? String {
                // セクション分割を試みる（サーバー側でセクション分けされている場合）
                parseReportSections(current)
            }
        } catch {
            // 初回は空で開始
        }
    }

    private func parseReportSections(_ content: String) {
        // セクションヘッダーで分割
        let lines = content.components(separatedBy: "\n")
        var currentSection = "direction"
        var sections: [String: [String]] = [
            "direction": [],
            "telop": [],
            "bgm": [],
            "color": []
        ]

        for line in lines {
            let lower = line.lowercased()
            if lower.contains("テロップ") {
                currentSection = "telop"
                continue
            } else if lower.contains("bgm") || lower.contains("音楽") {
                currentSection = "bgm"
                continue
            } else if lower.contains("色彩") || lower.contains("カラー") {
                currentSection = "color"
                continue
            }
            sections[currentSection, default: []].append(line)
        }

        directionText = sections["direction"]?.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        telopText = sections["telop"]?.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        bgmText = sections["bgm"]?.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        colorText = sections["color"]?.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        // 元テキストを保存
        originalDirectionText = directionText
        originalTelopText = telopText
        originalBgmText = bgmText
        originalColorText = colorText
    }

    private func saveReport() async {
        isSaving = true
        defer { isSaving = false }

        // セクションを結合
        var combined = ""
        if !directionText.isEmpty {
            combined += "## 演出ディレクション\n\(directionText)\n\n"
        }
        if !telopText.isEmpty {
            combined += "## テロップ指示\n\(telopText)\n\n"
        }
        if !bgmText.isEmpty {
            combined += "## BGM指示\n\(bgmText)\n\n"
        }
        if !colorText.isEmpty {
            combined += "## 色彩指示\n\(colorText)\n\n"
        }

        do {
            _ = try await APIClient.shared.updateDirectionReport(
                projectId: projectId,
                editedContent: combined.trimmingCharacters(in: .whitespacesAndNewlines),
                editedBy: selectedEditor,
                editNotes: editNotes.isEmpty ? nil : editNotes
            )

            // 保存成功 → diff表示
            showDiff = true
            saveSuccess = true

            // 元テキストを更新
            originalDirectionText = directionText
            originalTelopText = telopText
            originalBgmText = bgmText
            originalColorText = colorText

            // トーストを2秒後に非表示
            Task {
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                saveSuccess = false
            }
        } catch {
            errorMessage = "保存に失敗しました: \(error.localizedDescription)"
        }
    }

    private func loadEditHistory() async {
        do {
            editHistory = try await APIClient.shared.fetchDirectionEditHistory(projectId: projectId)
        } catch {
            editHistory = []
        }
    }
}
