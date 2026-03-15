import SwiftUI

struct EditorManagementView: View {
    @ObservedObject var viewModel: EditorManagementViewModel
    @State private var selectedEditorID: String?

    private var selectedEditor: Editor? {
        viewModel.editors.first { $0.id == selectedEditorID } ?? viewModel.editors.first
    }

    var body: some View {
        VStack(spacing: 16) {
            if let message = viewModel.errorMessage {
                banner(message)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(viewModel.editors) { editor in
                        Button {
                            selectedEditorID = editor.id
                        } label: {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(editor.name)
                                        .font(.headline)
                                        .foregroundStyle(.white)
                                    Spacer()
                                    Text(statusLabel(editor.status))
                                        .font(.caption2)
                                        .foregroundStyle(.white)
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 4)
                                        .background(statusColor(editor.status))
                                        .clipShape(Capsule())
                                }
                                Text("\(editor.activeProjectCount)件進行中 / 累計\(editor.completedCount)件")
                                    .font(.caption)
                                    .foregroundStyle(AppTheme.textSecondary)
                                Text(editor.contractType ?? "契約種別未設定")
                                    .font(.caption2)
                                    .foregroundStyle(AppTheme.textMuted)
                            }
                            .padding(16)
                            .frame(width: 220, alignment: .leading)
                            .background(selectedEditorID == editor.id ? AppTheme.cardBackgroundLight : AppTheme.cardBackground)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .strokeBorder(selectedEditorID == editor.id ? AppTheme.accent : .clear, lineWidth: 1)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            if let editor = selectedEditor {
                editorDetail(editor)
            }
        }
        .onAppear {
            if selectedEditorID == nil {
                selectedEditorID = viewModel.editors.first?.id
            }
        }
    }

    private func editorDetail(_ editor: Editor) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("編集者詳細")
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(.white)

            if let skills = editor.skills {
                VStack(alignment: .leading, spacing: 10) {
                    Text("スキルマトリクス")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                    skillRow("カット", value: skills.cutting)
                    skillRow("色彩", value: skills.color)
                    skillRow("テロップ", value: skills.telop)
                    skillRow("BGM", value: skills.bgm)
                    skillRow("カメラ", value: skills.cameraWork)
                    skillRow("構図", value: skills.composition)
                    skillRow("テンポ", value: skills.tempo)
                }
            }

            HStack {
                metric(title: "平均品質", value: editor.avgQualityScore.map { String(format: "%.1f", $0) } ?? "-")
                metric(title: "連絡先", value: editor.contactInfo ?? "-")
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private func skillRow(_ title: String, value: Double) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textSecondary)
                Spacer()
                Text(String(format: "%.1f", value))
                    .font(.caption2)
                    .foregroundStyle(.white)
            }
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(AppTheme.cardBackgroundLight)
                    RoundedRectangle(cornerRadius: 4)
                        .fill(AppTheme.accent)
                        .frame(width: proxy.size.width * min(max(value / 5.0, 0), 1))
                }
            }
            .frame(height: 8)
        }
    }

    private func metric(title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)
            Text(value)
                .font(.subheadline)
                .foregroundStyle(.white)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(AppTheme.cardBackgroundLight)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func banner(_ message: String) -> some View {
        Text(message)
            .font(.caption)
            .foregroundStyle(AppTheme.textSecondary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .background(Color(hex: 0x2A1717))
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private func statusLabel(_ status: String) -> String {
        switch status {
        case "active": return "稼働中"
        case "inactive": return "停止中"
        case "on_leave": return "休止中"
        default: return status
        }
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "active": return AppTheme.statusComplete
        case "inactive": return AppTheme.textMuted
        default: return Color(hex: 0xF5A623)
        }
    }
}
