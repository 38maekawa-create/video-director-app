import SwiftUI

/// FB承認詳細画面
/// 元の音声FBテキスト（Before）とLLM変換結果（After）を表示し、
/// 承認 / 修正 / 却下の3アクションを提供する
struct FeedbackApprovalDetailView: View {
    let feedback: FeedbackItem
    @ObservedObject var viewModel: FeedbackApprovalViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var isEditing = false
    @State private var editedText: String = ""
    @State private var showRejectConfirm = false
    @State private var isProcessing = false

    var body: some View {
        ZStack {
            AppTheme.background
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 20) {
                    // プロジェクト情報
                    projectInfoSection

                    // Before/After表示
                    beforeAfterSection

                    // 修正テキストエディタ（修正モード時）
                    if isEditing {
                        editSection
                    }

                    // アクションボタン
                    actionButtons

                    // メッセージ表示
                    if let error = viewModel.errorMessage {
                        messageView(text: error, isError: true)
                    }
                    if let success = viewModel.successMessage {
                        messageView(text: success, isError: false)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 16)
            }
        }
        .navigationTitle("FB承認")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .onAppear {
            // 修正用テキストの初期値はconvertedText
            editedText = feedback.convertedText ?? feedback.content
        }
        .confirmationDialog("このFBを却下しますか？", isPresented: $showRejectConfirm) {
            Button("却下する", role: .destructive) {
                Task { await rejectAction() }
            }
            Button("キャンセル", role: .cancel) {}
        } message: {
            Text("却下したFBはVimeoに投稿できなくなります")
        }
    }

    // MARK: - プロジェクト情報
    private var projectInfoSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                if let guest = feedback.guestName, !guest.isEmpty {
                    Text(guest)
                        .font(AppTheme.labelFont(16))
                        .foregroundStyle(.white)
                }
                Spacer()
                Text(feedback.approvalStatus.label)
                    .font(.caption)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(feedback.approvalStatus.color)
                    .clipShape(Capsule())
            }

            if let title = feedback.projectTitle, !title.isEmpty {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }

            HStack(spacing: 16) {
                if let ts = feedback.timestamp, !ts.isEmpty {
                    Label(ts, systemImage: "timer")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textSecondary)
                }
                Label(feedback.createdBy, systemImage: "person.fill")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textSecondary)
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

    // MARK: - Before/After表示
    private var beforeAfterSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Before / After")
                .font(AppTheme.labelFont(14))
                .foregroundStyle(AppTheme.accent)

            // Before（元の音声テキスト）
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "mic.fill")
                        .foregroundStyle(AppTheme.accent)
                    Text("元の音声FB")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(AppTheme.accent)
                }

                Text(feedback.rawVoiceText ?? "(なし)")
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(AppTheme.accent.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            // 矢印
            Image(systemName: "arrow.down")
                .font(.title3)
                .foregroundStyle(AppTheme.accent)
                .frame(maxWidth: .infinity)

            // After（LLM変換結果）
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: "sparkles")
                        .foregroundStyle(AppTheme.statusComplete)
                    Text("LLM変換結果")
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(AppTheme.statusComplete)
                }

                Text(feedback.convertedText ?? feedback.content)
                    .font(.subheadline)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(AppTheme.statusComplete.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - 修正テキストエディタ
    private var editSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "pencil.circle.fill")
                    .foregroundStyle(Color(hex: 0x4A90D9))
                Text("テキストを修正")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
            }

            TextEditor(text: $editedText)
                .font(.subheadline)
                .foregroundStyle(.white)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 150)
                .padding(12)
                .background(AppTheme.cardBackgroundLight)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color(hex: 0x4A90D9).opacity(0.5), lineWidth: 1)
                )

            // 修正承認ボタン
            Button {
                Task { await modifyAction() }
            } label: {
                HStack {
                    if isProcessing {
                        ProgressView().tint(.white).scaleEffect(0.8)
                    } else {
                        Image(systemName: "checkmark.circle.fill")
                    }
                    Text("修正して承認")
                }
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(editedText.isEmpty ? AppTheme.textMuted : Color(hex: 0x4A90D9))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            .disabled(editedText.isEmpty || isProcessing)
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    // MARK: - アクションボタン
    private var actionButtons: some View {
        VStack(spacing: 12) {
            // 承認ボタン
            if !isEditing {
                Button {
                    Task { await approveAction() }
                } label: {
                    HStack {
                        if isProcessing {
                            ProgressView().tint(.white).scaleEffect(0.8)
                        } else {
                            Image(systemName: "checkmark.circle.fill")
                        }
                        Text("そのまま承認")
                    }
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(isProcessing ? AppTheme.textMuted : AppTheme.statusComplete)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
                .disabled(isProcessing)
            }

            HStack(spacing: 12) {
                // 修正モード切替
                Button {
                    withAnimation { isEditing.toggle() }
                } label: {
                    HStack {
                        Image(systemName: isEditing ? "xmark" : "pencil")
                        Text(isEditing ? "修正をやめる" : "修正する")
                    }
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(AppTheme.cardBackgroundLight)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }

                // 却下ボタン
                Button {
                    showRejectConfirm = true
                } label: {
                    HStack {
                        Image(systemName: "xmark.circle")
                        Text("却下")
                    }
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundStyle(AppTheme.accent)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(AppTheme.accent.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .strokeBorder(AppTheme.accent.opacity(0.3), lineWidth: 1)
                    )
                }
                .disabled(isProcessing)
            }
        }
    }

    // MARK: - メッセージ表示
    private func messageView(text: String, isError: Bool) -> some View {
        HStack {
            Image(systemName: isError ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
                .foregroundStyle(isError ? AppTheme.accent : AppTheme.statusComplete)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(isError ? AppTheme.accent : AppTheme.statusComplete)
        }
        .padding(12)
        .frame(maxWidth: .infinity)
        .background((isError ? AppTheme.accent : AppTheme.statusComplete).opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - アクション
    private func approveAction() async {
        isProcessing = true
        await viewModel.approve(feedbackId: feedback.id)
        isProcessing = false
        if viewModel.errorMessage == nil {
            dismiss()
        }
    }

    private func modifyAction() async {
        isProcessing = true
        await viewModel.modify(feedbackId: feedback.id, modifiedText: editedText)
        isProcessing = false
        if viewModel.errorMessage == nil {
            dismiss()
        }
    }

    private func rejectAction() async {
        isProcessing = true
        await viewModel.reject(feedbackId: feedback.id)
        isProcessing = false
        if viewModel.errorMessage == nil {
            dismiss()
        }
    }
}
