import SwiftUI

// MARK: - 編集後フィードバック画面（P1: Before/After差分確認）
/// 編集者から戻ってきた動画のフィードバックをiPhoneで即確認するための画面。
/// 品質スコア・コンテンツフィードバック・テロップチェック・ハイライト採用率を表示する。
struct EditFeedbackView: View {
    let project: VideoProject
    @State private var feedback: EditFeedbackResponse? = nil
    @State private var isLoading = false
    @State private var errorMessage: String? = nil

    // 編集済み動画メタデータ入力用（オプション）
    @State private var durationMinutes = ""
    @State private var originalDurationMinutes = ""
    @State private var editorName = ""
    @State private var selectedStage = "draft"
    @State private var showInputForm = false

    private let stages = ["draft", "revision_1", "revision_2", "final"]
    private let stageLabels = ["初稿", "修正1", "修正2", "最終稿"]

    var body: some View {
        ZStack {
            AppTheme.background
                .ignoresSafeArea()

            if isLoading {
                loadingView
            } else if let feedback {
                ScrollView(.vertical, showsIndicators: false) {
                    VStack(spacing: 0) {
                        // ヒーローバナー（グレード＋スコア）
                        gradeHeroSection(feedback)

                        VStack(spacing: 16) {
                            // サマリーテキスト
                            summarySection(feedback)

                            // ハイライト採用率
                            highlightCheckSection(feedback.highlightCheck)

                            // テロップチェック
                            telopCheckSection(feedback.telopCheck)

                            // コンテンツフィードバック
                            contentFeedbackSection(feedback.contentFeedback)

                            // ディレクション準拠度
                            directionAdherenceSection(feedback.directionAdherence)

                            // メタ情報
                            metaInfoSection(feedback)

                            // 再生成ボタン
                            regenerateButton
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 16)
                        .padding(.bottom, 48)
                    }
                }
            } else {
                emptyStateView
            }
        }
        .navigationTitle("編集後フィードバック")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showInputForm.toggle()
                } label: {
                    Image(systemName: "slider.horizontal.3")
                        .foregroundStyle(AppTheme.textSecondary)
                }
            }
        }
        .sheet(isPresented: $showInputForm) {
            inputFormSheet
        }
        .task {
            if feedback == nil {
                await loadFeedback()
            }
        }
    }

    // MARK: - ヒーローセクション（グレード＋スコアゲージ）

    @ViewBuilder
    private func gradeHeroSection(_ fb: EditFeedbackResponse) -> some View {
        ZStack(alignment: .bottom) {
            AppTheme.cardBackground
                .frame(maxWidth: .infinity)
                .frame(height: 200)

            VStack(spacing: 8) {
                // グレードバッジ
                ZStack {
                    Circle()
                        .fill(fb.gradeColor.opacity(0.15))
                        .frame(width: 96, height: 96)
                    Circle()
                        .strokeBorder(fb.gradeColor, lineWidth: 2)
                        .frame(width: 96, height: 96)
                    Text(fb.grade)
                        .font(AppTheme.heroFont(48))
                        .foregroundStyle(fb.gradeColor)
                }

                // スコア数値
                HStack(spacing: 4) {
                    Text(String(format: "%.1f", fb.qualityScore))
                        .font(AppTheme.heroFont(28))
                        .foregroundStyle(AppTheme.textPrimary)
                    Text("/ 10.0")
                        .font(AppTheme.bodyFont(14))
                        .foregroundStyle(AppTheme.textMuted)
                }

                // スコアゲージバー
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule()
                            .fill(Color.white.opacity(0.1))
                            .frame(height: 6)
                        Capsule()
                            .fill(fb.gradeColor)
                            .frame(width: geo.size.width * fb.scoreProgress, height: 6)
                            .animation(.spring(response: 0.8, dampingFraction: 0.8), value: fb.scoreProgress)
                    }
                }
                .frame(height: 6)
                .padding(.horizontal, 40)
                .padding(.bottom, 16)
            }
        }
    }

    // MARK: - サマリーセクション

    @ViewBuilder
    private func summarySection(_ fb: EditFeedbackResponse) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionHeader(icon: "text.alignleft", title: "サマリー")
            Text(fb.summary)
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textSecondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 10))
        }
    }

    // MARK: - ハイライト採用率セクション

    @ViewBuilder
    private func highlightCheckSection(_ hl: HighlightCheckSummary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionHeader(icon: "star.fill", title: "ハイライト採用率")

            VStack(spacing: 10) {
                // 採用率メーター
                HStack(spacing: 12) {
                    VStack(spacing: 2) {
                        Text(hl.inclusionPercent)
                            .font(AppTheme.heroFont(32))
                            .foregroundStyle(AppTheme.textPrimary)
                        Text("採用率")
                            .font(AppTheme.labelFont(11))
                            .foregroundStyle(AppTheme.textMuted)
                    }
                    .frame(width: 80)

                    VStack(alignment: .leading, spacing: 6) {
                        // 採用済み
                        labelledBar(
                            label: "採用",
                            count: hl.included,
                            total: max(hl.total, 1),
                            color: AppTheme.statusComplete
                        )
                        // カット済み
                        labelledBar(
                            label: "カット",
                            count: hl.excluded,
                            total: max(hl.total, 1),
                            color: AppTheme.accent
                        )
                    }
                }
                .padding(12)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 10))

                // コメント
                if !hl.comment.isEmpty {
                    Text(hl.comment)
                        .font(AppTheme.bodyFont(13))
                        .foregroundStyle(AppTheme.textSecondary)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(AppTheme.cardBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                // カットされた重要シーンリスト
                if !hl.keyExcluded.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("カットされたシーン")
                            .font(AppTheme.labelFont(11))
                            .foregroundStyle(AppTheme.textMuted)
                        ForEach(hl.keyExcluded, id: \.self) { item in
                            HStack(spacing: 6) {
                                Circle()
                                    .fill(AppTheme.accent)
                                    .frame(width: 5, height: 5)
                                Text(item)
                                    .font(AppTheme.bodyFont(13))
                                    .foregroundStyle(AppTheme.textSecondary)
                            }
                        }
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.cardBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }
        }
    }

    // MARK: - テロップチェックセクション

    @ViewBuilder
    private func telopCheckSection(_ telop: TelopCheckSummary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionHeader(icon: "textformat.abc", title: "テロップチェック")

            HStack(spacing: 12) {
                telopCountBadge(label: "エラー", count: telop.errorCount, color: AppTheme.accent)
                telopCountBadge(label: "警告", count: telop.warningCount, color: Color(hex: 0xF5A623))
                Spacer()
            }

            if !telop.note.isEmpty {
                Text(telop.note)
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(AppTheme.textMuted)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.cardBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
    }

    // MARK: - コンテンツフィードバックセクション

    @ViewBuilder
    private func contentFeedbackSection(_ items: [ContentFeedbackEntry]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionHeader(icon: "list.bullet.clipboard", title: "コンテンツフィードバック")

            if items.isEmpty {
                Text("フィードバック項目はありません")
                    .font(AppTheme.bodyFont(13))
                    .foregroundStyle(AppTheme.textMuted)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.cardBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                VStack(spacing: 8) {
                    ForEach(items) { item in
                        feedbackItemCard(item)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func feedbackItemCard(_ item: ContentFeedbackEntry) -> some View {
        HStack(alignment: .top, spacing: 10) {
            // 左側のカラーバー（severity別）
            Capsule()
                .fill(item.severityColor)
                .frame(width: 3)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    // カテゴリバッジ
                    Text(item.categoryLabel)
                        .font(AppTheme.labelFont(10))
                        .foregroundStyle(item.categoryColor)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(item.categoryColor.opacity(0.15))
                        .clipShape(Capsule())

                    // 領域
                    Text(item.area)
                        .font(AppTheme.labelFont(11))
                        .foregroundStyle(AppTheme.textMuted)
                }

                // メッセージ
                Text(item.message)
                    .font(AppTheme.bodyFont(13))
                    .foregroundStyle(AppTheme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Spacer(minLength: 0)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - ディレクション準拠度セクション

    @ViewBuilder
    private func directionAdherenceSection(_ adh: DirectionAdherenceSummary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionHeader(icon: "checkmark.circle", title: "ディレクション準拠度")

            if adh.total == 0 {
                // データなし
                Text(adh.note ?? "ディレクションタイムラインとの照合が必要です")
                    .font(AppTheme.bodyFont(13))
                    .foregroundStyle(AppTheme.textMuted)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.cardBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                HStack(spacing: 12) {
                    adherenceStat(label: "準拠", count: adh.followed, color: AppTheme.statusComplete)
                    adherenceStat(label: "部分準拠", count: adh.partial, color: Color(hex: 0xF5A623))
                    adherenceStat(label: "未準拠", count: adh.notFollowed, color: AppTheme.accent)
                    Spacer()
                    VStack(spacing: 2) {
                        Text(adh.adherencePercent)
                            .font(AppTheme.heroFont(22))
                            .foregroundStyle(AppTheme.textPrimary)
                        Text("準拠率")
                            .font(AppTheme.labelFont(10))
                            .foregroundStyle(AppTheme.textMuted)
                    }
                }
                .padding(12)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
    }

    // MARK: - メタ情報セクション

    @ViewBuilder
    private func metaInfoSection(_ fb: EditFeedbackResponse) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            if !fb.editorName.isEmpty {
                metaRow(label: "編集者", value: fb.editorName)
            }
            metaRow(label: "編集段階", value: stageDisplayLabel(fb.stage))
            metaRow(label: "生成日時", value: fb.generatedAt)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - 再生成ボタン

    private var regenerateButton: some View {
        Button {
            showInputForm = true
        } label: {
            Label("フィードバックを再生成", systemImage: "arrow.clockwise")
                .font(AppTheme.labelFont(14))
                .foregroundStyle(AppTheme.textPrimary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(AppTheme.textMuted.opacity(0.3), lineWidth: 1)
                )
        }
        .padding(.top, 4)
    }

    // MARK: - ローディング・エンプティ

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .progressViewStyle(.circular)
                .tint(AppTheme.accent)
                .scaleEffect(1.5)
            Text("フィードバックを生成中...")
                .font(AppTheme.bodyFont(14))
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: "film.stack.fill")
                .font(.system(size: 48))
                .foregroundStyle(AppTheme.textMuted)

            Text("編集後フィードバックを生成")
                .font(AppTheme.sectionFont(18))
                .foregroundStyle(AppTheme.textPrimary)

            Text("編集済み動画が手元にある場合、\nメタデータを入力してフィードバックを確認できます。")
                .font(AppTheme.bodyFont(13))
                .foregroundStyle(AppTheme.textMuted)
                .multilineTextAlignment(.center)

            if let errorMessage {
                Text(errorMessage)
                    .font(AppTheme.bodyFont(12))
                    .foregroundStyle(AppTheme.accent)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 24)
            }

            Button {
                Task { await loadFeedback() }
            } label: {
                Label("フィードバックを生成", systemImage: "sparkles")
                    .font(AppTheme.labelFont(14))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(AppTheme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
        .padding(32)
    }

    // MARK: - 入力フォームシート

    private var inputFormSheet: some View {
        NavigationStack {
            ZStack {
                AppTheme.background.ignoresSafeArea()

                Form {
                    Section("編集済み動画の情報") {
                        HStack {
                            Text("編集後の尺（分）")
                                .foregroundStyle(AppTheme.textSecondary)
                            Spacer()
                            TextField("例: 8", text: $durationMinutes)
                                .keyboardType(.numberPad)
                                .multilineTextAlignment(.trailing)
                                .foregroundStyle(AppTheme.textPrimary)
                        }
                        HStack {
                            Text("元素材の尺（分）")
                                .foregroundStyle(AppTheme.textSecondary)
                            Spacer()
                            TextField("例: 45", text: $originalDurationMinutes)
                                .keyboardType(.numberPad)
                                .multilineTextAlignment(.trailing)
                                .foregroundStyle(AppTheme.textPrimary)
                        }
                        HStack {
                            Text("担当編集者")
                                .foregroundStyle(AppTheme.textSecondary)
                            Spacer()
                            TextField("編集者名", text: $editorName)
                                .multilineTextAlignment(.trailing)
                                .foregroundStyle(AppTheme.textPrimary)
                        }
                    }
                    .listRowBackground(AppTheme.cardBackground)

                    Section("編集段階") {
                        Picker("編集段階", selection: $selectedStage) {
                            ForEach(Array(zip(stages, stageLabels)), id: \.0) { stage, label in
                                Text(label).tag(stage)
                            }
                        }
                        .pickerStyle(.segmented)
                    }
                    .listRowBackground(AppTheme.cardBackground)
                }
                .scrollContentBackground(.hidden)
                .foregroundStyle(AppTheme.textPrimary)
            }
            .navigationTitle("フィードバック設定")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("キャンセル") {
                        showInputForm = false
                    }
                    .foregroundStyle(AppTheme.textSecondary)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("生成") {
                        showInputForm = false
                        Task { await loadFeedbackWithInput() }
                    }
                    .foregroundStyle(AppTheme.accent)
                    .fontWeight(.semibold)
                }
            }
        }
    }

    // MARK: - ヘルパーサブビュー

    private func sectionHeader(icon: String, title: String) -> some View {
        HStack(spacing: 6) {
            Image(systemName: icon)
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(AppTheme.accent)
            Text(title)
                .font(AppTheme.labelFont(13))
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    @ViewBuilder
    private func labelledBar(label: String, count: Int, total: Int, color: Color) -> some View {
        HStack(spacing: 8) {
            Text(label)
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)
                .frame(width: 36, alignment: .leading)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.white.opacity(0.1))
                        .frame(height: 6)
                    Capsule()
                        .fill(color)
                        .frame(width: geo.size.width * CGFloat(count) / CGFloat(total), height: 6)
                }
            }
            .frame(height: 6)
            Text("\(count)")
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textPrimary)
                .frame(width: 24, alignment: .trailing)
        }
    }

    private func telopCountBadge(label: String, count: Int, color: Color) -> some View {
        VStack(spacing: 4) {
            Text("\(count)")
                .font(AppTheme.heroFont(28))
                .foregroundStyle(count > 0 ? color : AppTheme.textMuted)
            Text(label)
                .font(AppTheme.labelFont(11))
                .foregroundStyle(AppTheme.textMuted)
        }
        .frame(width: 72)
        .padding(.vertical, 12)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(count > 0 ? color.opacity(0.4) : Color.clear, lineWidth: 1)
        )
    }

    private func adherenceStat(label: String, count: Int, color: Color) -> some View {
        VStack(spacing: 2) {
            Text("\(count)")
                .font(AppTheme.heroFont(20))
                .foregroundStyle(color)
            Text(label)
                .font(AppTheme.labelFont(10))
                .foregroundStyle(AppTheme.textMuted)
        }
    }

    private func metaRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(AppTheme.labelFont(12))
                .foregroundStyle(AppTheme.textMuted)
            Spacer()
            Text(value)
                .font(AppTheme.bodyFont(12))
                .foregroundStyle(AppTheme.textSecondary)
        }
    }

    private func stageDisplayLabel(_ stage: String) -> String {
        switch stage {
        case "draft": return "初稿"
        case "revision_1": return "修正1"
        case "revision_2": return "修正2"
        case "final": return "最終稿"
        default: return stage
        }
    }

    // MARK: - データ取得

    private func loadFeedback() async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        do {
            let result = try await APIClient.shared.fetchEditFeedback(projectId: project.id)
            await MainActor.run { feedback = result }
        } catch {
            await MainActor.run {
                errorMessage = "フィードバックの取得に失敗しました: \(error.localizedDescription)"
            }
        }
        await MainActor.run { isLoading = false }
    }

    private func loadFeedbackWithInput() async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        let durationSec = (Int(durationMinutes) ?? 0) * 60
        let originalSec = (Int(originalDurationMinutes) ?? 0) * 60
        let body = EditFeedbackRequestBody(
            durationSeconds: durationSec,
            originalDurationSeconds: originalSec,
            editorName: editorName,
            stage: selectedStage
        )
        do {
            let result = try await APIClient.shared.fetchEditFeedback(
                projectId: project.id,
                body: body
            )
            await MainActor.run { feedback = result }
        } catch {
            await MainActor.run {
                errorMessage = "フィードバックの取得に失敗しました: \(error.localizedDescription)"
            }
        }
        await MainActor.run { isLoading = false }
    }
}

// MARK: - プレビュー

#Preview {
    NavigationStack {
        EditFeedbackView(
            project: VideoProject(
                id: "preview_001",
                guestName: "コテさん",
                title: "2月28日 大阪 TEKO対談",
                shootDate: "2026/02/28",
                status: .reviewPending
            )
        )
    }
}
