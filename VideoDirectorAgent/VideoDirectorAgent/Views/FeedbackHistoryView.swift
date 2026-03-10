import SwiftUI

// MARK: - 画面4: FB履歴（タイムライン表示・日付グループ化）
struct FeedbackHistoryView: View {
    @State private var filterMode: HistoryFilter = .all
    @State private var searchText = ""

    enum HistoryFilter: String, CaseIterable {
        case all = "すべて"
        case unsent = "未送信のみ"

        var label: String { rawValue }
    }

    // 日付グループ化
    private var groupedItems: [(String, [FeedbackHistoryItem])] {
        let filtered = filteredItems
        let grouped = Dictionary(grouping: filtered) { $0.date }
        return grouped.sorted { $0.key > $1.key }
    }

    private var filteredItems: [FeedbackHistoryItem] {
        var items = MockData.historyItems

        // フィルタ
        switch filterMode {
        case .all: break
        case .unsent:
            items = items.filter { !$0.isSent }
        }

        // 検索
        if !searchText.isEmpty {
            items = items.filter {
                $0.projectTitle.localizedCaseInsensitiveContains(searchText) ||
                $0.guestName.localizedCaseInsensitiveContains(searchText) ||
                $0.rawVoiceText.localizedCaseInsensitiveContains(searchText)
            }
        }

        return items
    }

    var body: some View {
        VStack(spacing: 0) {
            // フィルタ + 検索
            VStack(spacing: 12) {
                // 検索バー
                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(AppTheme.textMuted)
                    TextField("プロジェクト、ゲスト名で検索", text: $searchText)
                        .foregroundStyle(.white)
                        .autocorrectionDisabled()
                }
                .padding(12)
                .background(AppTheme.cardBackground)
                .clipShape(RoundedRectangle(cornerRadius: 10))

                // フィルタ切替
                HStack(spacing: 8) {
                    ForEach(HistoryFilter.allCases, id: \.self) { filter in
                        Button {
                            withAnimation { filterMode = filter }
                        } label: {
                            Text(filter.label)
                                .font(.caption)
                                .fontWeight(.medium)
                                .foregroundStyle(filterMode == filter ? .white : AppTheme.textMuted)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 8)
                                .background(filterMode == filter ? AppTheme.accent : AppTheme.cardBackground)
                                .clipShape(Capsule())
                        }
                    }
                    Spacer()
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)

            // タイムライン
            ScrollView(.vertical, showsIndicators: false) {
                LazyVStack(spacing: 0, pinnedViews: [.sectionHeaders]) {
                    ForEach(groupedItems, id: \.0) { date, items in
                        Section {
                            ForEach(items) { item in
                                feedbackCard(item)
                                    .padding(.horizontal, 16)
                                    .padding(.bottom, 12)
                            }
                        } header: {
                            dateHeader(date)
                        }
                    }
                }
                .padding(.bottom, 40)
            }
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationTitle("フィードバック履歴")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("フィードバック履歴")
                    .font(.headline)
                    .foregroundStyle(.white)
            }
        }
    }

    // MARK: - 日付ヘッダー
    private func dateHeader(_ date: String) -> some View {
        HStack {
            Text(date)
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(AppTheme.accent)
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(AppTheme.background)
    }

    // MARK: - FBカード
    private func feedbackCard(_ item: FeedbackHistoryItem) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // ヘッダー行
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(item.guestName)
                        .font(.subheadline)
                        .fontWeight(.bold)
                        .foregroundStyle(.white)
                    Text(item.projectTitle)
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }

                Spacer()

                // タイムスタンプ
                Text(item.timestamp)
                    .font(.system(.caption, design: .monospaced))
                    .fontWeight(.bold)
                    .foregroundStyle(AppTheme.accent)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(AppTheme.accent.opacity(0.15))
                    .clipShape(Capsule())
            }

            // 元の音声
            HStack(alignment: .top, spacing: 10) {
                // 再生ボタン（モック）
                Button {} label: {
                    Image(systemName: "play.circle.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(AppTheme.textMuted)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text("音声")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                    Text(item.rawVoiceText)
                        .font(.caption)
                        .foregroundStyle(AppTheme.textSecondary)
                }
            }

            // AI変換結果
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "arrow.right.circle.fill")
                    .font(.system(size: 28))
                    .foregroundStyle(AppTheme.statusComplete)

                VStack(alignment: .leading, spacing: 4) {
                    Text("変換後")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.statusComplete)
                    Text(item.convertedText)
                        .font(.caption)
                        .foregroundStyle(.white)
                }
            }

            // ステータス行
            HStack {
                // 送信ステータス
                HStack(spacing: 4) {
                    Image(systemName: item.isSent ? "checkmark.circle.fill" : "clock.fill")
                        .font(.caption2)
                    Text(item.isSent ? "送信済み" : "未送信")
                        .font(.caption2)
                }
                .foregroundStyle(item.isSent ? AppTheme.statusComplete : AppTheme.accent)

                Text("・")
                    .foregroundStyle(AppTheme.textMuted)

                Text(item.editorStatus)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textMuted)

                Spacer()

                if !item.learningEffect.isEmpty {
                    Text(item.learningEffect)
                        .font(.caption2)
                        .foregroundStyle(AppTheme.statusComplete)
                }
            }
        }
        .padding(16)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
