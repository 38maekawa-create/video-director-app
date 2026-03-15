import Foundation

/// ナレッジページ閲覧画面のViewModel
@MainActor
final class KnowledgePagesViewModel: ObservableObject {
    @Published var pages: [KnowledgePage] = []
    @Published var searchResults: [KnowledgeSearchResult] = []
    @Published var searchQuery: String = ""
    @Published var isLoading = false
    @Published var isSearching = false
    @Published var errorMessage: String?
    @Published var selectedPageDetail: KnowledgePageDetail?
    @Published var isLoadingDetail = false

    private var hasLoaded = false

    /// ページ一覧を取得（初回のみ）
    func loadPagesIfNeeded() async {
        guard !hasLoaded else { return }
        hasLoaded = true
        await loadPages()
    }

    /// ページ一覧を取得
    func loadPages() async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await APIClient.shared.fetchKnowledgePages(limit: 100)
            self.pages = response.pages
        } catch {
            if pages.isEmpty {
                errorMessage = "ナレッジページの取得に失敗しました"
            }
            print("ナレッジページ取得エラー: \(error)")
        }

        isLoading = false
    }

    /// ナレッジ検索
    func search() async {
        let query = searchQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else {
            searchResults = []
            return
        }

        isSearching = true

        do {
            let response = try await APIClient.shared.searchKnowledge(query: query)
            searchResults = response.results
        } catch {
            print("ナレッジ検索エラー: \(error)")
        }

        isSearching = false
    }

    /// ページ詳細を取得（HTML内容）
    func loadPageDetail(pageId: String) async {
        isLoadingDetail = true

        do {
            let detail = try await APIClient.shared.fetchKnowledgePageDetail(pageId: pageId)
            selectedPageDetail = detail
        } catch {
            print("ナレッジページ詳細取得エラー: \(error)")
        }

        isLoadingDetail = false
    }

    /// 検索中かどうか（UIの表示切替用）
    var isInSearchMode: Bool {
        !searchQuery.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }
}
