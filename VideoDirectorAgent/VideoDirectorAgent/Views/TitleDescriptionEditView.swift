import SwiftUI

// MARK: - タイトル案・概要欄の手修正画面
struct TitleDescriptionEditView: View {
    let projectId: String
    let projectTitle: String

    // タイトル案
    @State private var titleText = ""
    @State private var originalTitleText = ""

    // 概要欄
    @State private var descriptionText = ""
    @State private var originalDescriptionText = ""

    // UI状態
    @State private var selectedEditor = "なおとさん"
    @State private var isSavingTitle = false
    @State private var isSavingDescription = false
    @State private var isLoading = false
    @State private var showTitleDiff = false
    @State private var showDescriptionDiff = false
    @State private var saveSuccessMessage: String?
    @State private var errorMessage: String?

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

                        // タイトル案セクション
                        titleEditSection

                        // タイトルdiff
                        if showTitleDiff {
                            diffCard(
                                label: "タイトル案",
                                original: originalTitleText,
                                edited: titleText
                            )
                        }

                        // 概要欄セクション
                        descriptionEditSection

                        // 概要欄diff
                        if showDescriptionDiff {
                            diffCard(
                                label: "概要欄",
                                original: originalDescriptionText,
                                edited: descriptionText
                            )
                        }

                        Spacer(minLength: 40)
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 16)
                }
            }

            // 成功トースト
            if let message = saveSuccessMessage {
                VStack {
                    HStack(spacing: 8) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(AppTheme.statusComplete)
                            .font(.system(size: 20))
                        Text(message)
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

                    Spacer()
                }
                .transition(.move(edge: .top).combined(with: .opacity))
                .animation(.easeInOut(duration: 0.3), value: saveSuccessMessage)
            }
        }
        .navigationTitle("タイトル・概要編集")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task {
            await loadCurrentData()
        }
    }

    // MARK: - ヘッダーカード

    private var headerCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "character.cursor.ibeam")
                    .foregroundStyle(AppTheme.accent)
                Text("タイトル・概要編集")
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

    // MARK: - タイトル案編集セクション

    private var titleEditSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "textformat.size")
                    .foregroundStyle(AppTheme.accent)
                Text("タイトル案")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
            }

            TextField("タイトルを入力", text: $titleText)
                .font(AppTheme.bodyFont(16))
                .foregroundStyle(AppTheme.textPrimary)
                .padding(12)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 8))

            // 保存ボタン
            Button {
                Task { await saveTitle() }
            } label: {
                HStack(spacing: 6) {
                    if isSavingTitle {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.7)
                    } else {
                        Image(systemName: "checkmark")
                            .font(.system(size: 12, weight: .bold))
                    }
                    Text("タイトルを保存")
                        .font(.subheadline)
                        .fontWeight(.bold)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(isSavingTitle ? AppTheme.textMuted : AppTheme.accent)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            .disabled(isSavingTitle)
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 概要欄編集セクション

    private var descriptionEditSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "doc.text")
                    .foregroundStyle(AppTheme.accent)
                Text("概要欄")
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
            }

            TextEditor(text: $descriptionText)
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textSecondary)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 200)
                .padding(8)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 8))

            // 保存ボタン
            Button {
                Task { await saveDescription() }
            } label: {
                HStack(spacing: 6) {
                    if isSavingDescription {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.7)
                    } else {
                        Image(systemName: "checkmark")
                            .font(.system(size: 12, weight: .bold))
                    }
                    Text("概要欄を保存")
                        .font(.subheadline)
                        .fontWeight(.bold)
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(isSavingDescription ? AppTheme.textMuted : AppTheme.accent)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            .disabled(isSavingDescription)
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - Diff表示カード

    private func diffCard(label: String, original: String, edited: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Image(systemName: "arrow.left.arrow.right")
                    .foregroundStyle(AppTheme.accent)
                Text("\(label) 変更差分")
                    .font(AppTheme.sectionFont(16))
                    .foregroundStyle(.white)
            }

            if original == edited {
                Text("変更なし")
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(AppTheme.textMuted)
            } else {
                // 元テキスト
                if !original.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("変更前")
                            .font(AppTheme.labelFont(10))
                            .foregroundStyle(AppTheme.accent.opacity(0.8))
                        Text(original)
                            .font(AppTheme.bodyFont(12))
                            .foregroundStyle(AppTheme.accent)
                            .lineLimit(5)
                    }
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.accent.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }

                // 修正テキスト
                if !edited.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("変更後")
                            .font(AppTheme.labelFont(10))
                            .foregroundStyle(AppTheme.statusComplete.opacity(0.8))
                        Text(edited)
                            .font(AppTheme.bodyFont(12))
                            .foregroundStyle(AppTheme.statusComplete)
                            .lineLimit(5)
                    }
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.statusComplete.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
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
            Text("データを読み込み中...")
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    // MARK: - データ操作

    private func loadCurrentData() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let diff = try await APIClient.shared.fetchAssetEditDiff(projectId: projectId, assetType: "title")
            if let current = diff["current"] as? String {
                titleText = current
                originalTitleText = current
            }
        } catch {
            // 初回は空で開始
        }
        do {
            let diff = try await APIClient.shared.fetchAssetEditDiff(projectId: projectId, assetType: "description")
            if let current = diff["current"] as? String {
                descriptionText = current
                originalDescriptionText = current
            }
        } catch {
            // 初回は空で開始
        }
    }

    private func saveTitle() async {
        isSavingTitle = true
        defer { isSavingTitle = false }
        do {
            _ = try await APIClient.shared.updateTitle(
                projectId: projectId,
                editedContent: titleText,
                editedBy: selectedEditor
            )
            showTitleDiff = true
            showSuccess("タイトルを保存しました")
            originalTitleText = titleText
        } catch {
            errorMessage = "タイトルの保存に失敗: \(error.localizedDescription)"
        }
    }

    private func saveDescription() async {
        isSavingDescription = true
        defer { isSavingDescription = false }
        do {
            _ = try await APIClient.shared.updateDescription(
                projectId: projectId,
                editedContent: descriptionText,
                editedBy: selectedEditor
            )
            showDescriptionDiff = true
            showSuccess("概要欄を保存しました")
            originalDescriptionText = descriptionText
        } catch {
            errorMessage = "概要欄の保存に失敗: \(error.localizedDescription)"
        }
    }

    private func showSuccess(_ message: String) {
        saveSuccessMessage = message
        Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            saveSuccessMessage = nil
        }
    }
}
