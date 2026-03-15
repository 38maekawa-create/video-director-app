import SwiftUI

struct DirectionReportView: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                ForEach(MockData.reportSections) { section in
                    VStack(alignment: .leading, spacing: 8) {
                        Text(section.title)
                            .font(.headline)
                            .foregroundStyle(.white)

                        ForEach(section.items, id: \.self) { item in
                            Text("• \(item)")
                                .font(.subheadline)
                                .foregroundStyle(.white.opacity(0.85))
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .padding()
                    .background(AppTheme.card)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                }

                // --- 追加: before/after 品質スコア比較セクション ---
                QualityScoreComparisonSection(comparisons: MockData.qualityScoreComparisons)

                HStack(spacing: 12) {
                    Button("この方針でOK") {}
                        .buttonStyle(.borderedProminent)
                        .tint(AppTheme.accent)
                    Button("修正指示") {}
                        .buttonStyle(.bordered)
                }
                .padding(.top, 4)
            }
            .padding()
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationTitle("ディレクションレポート")
    }
}

// MARK: - before/after 品質スコア比較セクション

private struct QualityScoreComparisonSection: View {
    let comparisons: [QualityScoreComparison]

    /// 総合スコア（比較対象全要素の平均）
    private var beforeAvg: Int {
        guard !comparisons.isEmpty else { return 0 }
        return comparisons.map(\.beforeScore).reduce(0, +) / comparisons.count
    }
    private var afterAvg: Int {
        guard !comparisons.isEmpty else { return 0 }
        return comparisons.map(\.afterScore).reduce(0, +) / comparisons.count
    }
    private var totalDiff: Int { afterAvg - beforeAvg }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // ヘッダー
            Label("編集前後 品質スコア比較", systemImage: "chart.bar.doc.horizontal")
                .font(.headline)
                .foregroundStyle(.white)

            // 総合スコアサマリー
            HStack(spacing: 0) {
                ScoreSummaryBadge(label: "Before", score: beforeAvg, color: .gray)
                Image(systemName: "arrow.right")
                    .foregroundStyle(.white.opacity(0.5))
                    .padding(.horizontal, 8)
                ScoreSummaryBadge(label: "After", score: afterAvg, color: AppTheme.accent)
                Spacer()
                DiffBadge(diff: totalDiff)
            }

            Divider().background(.white.opacity(0.15))

            // 要素別差分リスト
            ForEach(comparisons) { item in
                QualityComparisonRow(item: item)
            }
        }
        .padding()
        .background(AppTheme.card)
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }
}

/// 総合スコアの数値バッジ
private struct ScoreSummaryBadge: View {
    let label: String
    let score: Int
    let color: Color

    var body: some View {
        VStack(spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.55))
            Text("\(score)")
                .font(.title2)
                .bold()
                .foregroundStyle(color)
        }
    }
}

/// 改善幅バッジ（正=緑、負=赤）
private struct DiffBadge: View {
    let diff: Int

    private var isPositive: Bool { diff >= 0 }

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: isPositive ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
            Text("\(isPositive ? "+" : "")\(diff)pt")
                .font(.subheadline)
                .bold()
        }
        .foregroundStyle(isPositive ? .green : .red)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background((isPositive ? Color.green : Color.red).opacity(0.15))
        .clipShape(Capsule())
    }
}

/// 要素単位の before/after バーとスコア差分
private struct QualityComparisonRow: View {
    let item: QualityScoreComparison

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(item.element)
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.80))
                    .frame(width: 80, alignment: .leading)

                // Before バー（グレー）
                ScoreBar(score: item.beforeScore, color: .gray.opacity(0.5))

                // After バー（アクセント）
                ScoreBar(score: item.afterScore, color: AppTheme.accent)

                DiffBadge(diff: item.diff)
            }
        }
    }
}

/// スコア値をバーで表現（スコア/100 の幅）
private struct ScoreBar: View {
    let score: Int
    let color: Color

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(color.opacity(0.15))
                Capsule()
                    .fill(color)
                    .frame(width: geo.size.width * CGFloat(score) / 100)
            }
        }
        .frame(height: 8)
        .overlay(
            Text("\(score)")
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.75))
                .offset(y: -12),
            alignment: .trailing
        )
    }
}
