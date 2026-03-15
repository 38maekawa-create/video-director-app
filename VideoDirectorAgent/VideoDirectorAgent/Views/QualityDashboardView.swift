import SwiftUI

struct QualityDashboardView: View {
    @ObservedObject var viewModel: DashboardViewModel

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                qualityTrendCard
                editorSkillCard
                alertsCard
            }
            .padding()
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationTitle("品質ダッシュボード")
    }

    private var qualityTrendCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("品質スコア推移")
                .font(.headline)

            HStack(alignment: .bottom, spacing: 10) {
                ForEach(viewModel.trend) { point in
                    VStack {
                        Text("\(point.score)")
                            .font(.caption)
                        RoundedRectangle(cornerRadius: 6)
                            .fill(AppTheme.accent)
                            .frame(width: 30, height: CGFloat(point.score))
                        Text(point.label)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .frame(maxWidth: .infinity)
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var editorSkillCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("編集者別スキルマトリクス")
                .font(.headline)

            ForEach(viewModel.skills) { skill in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(skill.editorName).bold()
                        Spacer()
                        Text("成長 +\(skill.growth)%")
                            .font(.caption)
                            .foregroundStyle(.green)
                    }
                    Text("得意: \(skill.strengths.joined(separator: ", "))")
                        .font(.caption)
                    Text("課題: \(skill.weakPoints.joined(separator: ", "))")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
                .padding(.vertical, 4)
            }
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var alertsCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("品質アラート")
                .font(.headline)

            ForEach(viewModel.alerts) { alert in
                Text("[\(alert.level)] \(alert.message)")
                    .font(.subheadline)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}
