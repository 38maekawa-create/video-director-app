import SwiftUI
import WebKit

/// ナレッジページ閲覧画面
struct KnowledgePagesView: View {
    @ObservedObject var viewModel: KnowledgePagesViewModel
    @State private var selectedPage: KnowledgePage?

    var body: some View {
        VStack(spacing: 0) {
            // 検索バー
            searchBar

            // コンテンツ
            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: 12) {
                    if viewModel.isLoading {
                        ProgressView()
                            .tint(AppTheme.accent)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 40)
                    } else if viewModel.isInSearchMode {
                        searchResultsSection
                    } else {
                        pagesListSection
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 40)
            }
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("ナレッジ")
                    .font(AppTheme.heroFont(17))
                    .foregroundStyle(.white)
                    .tracking(1)
            }
        }
        .task {
            await viewModel.loadPagesIfNeeded()
        }
        .sheet(item: $selectedPage) { page in
            knowledgeDetailSheet(page)
        }
    }

    // MARK: - 検索バー
    private var searchBar: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(AppTheme.textMuted)
            TextField("ナレッジを検索...", text: $viewModel.searchQuery)
                .foregroundStyle(.white)
                .autocorrectionDisabled()
                .onSubmit {
                    Task { await viewModel.search() }
                }
            if !viewModel.searchQuery.isEmpty {
                Button {
                    viewModel.searchQuery = ""
                    viewModel.searchResults = []
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(AppTheme.textMuted)
                }
            }
            if viewModel.isSearching {
                ProgressView()
                    .tint(AppTheme.accent)
                    .scaleEffect(0.7)
            }
        }
        .padding(12)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    // MARK: - ページ一覧
    private var pagesListSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "book.fill")
                    .foregroundStyle(AppTheme.accent)
                Text("ナレッジページ一覧")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(viewModel.pages.count)件")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }

            if viewModel.pages.isEmpty {
                Text("ナレッジページがありません")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
            } else {
                ForEach(viewModel.pages) { page in
                    pageCard(page)
                        .onTapGesture {
                            selectedPage = page
                        }
                }
            }
        }
    }

    private func pageCard(_ page: KnowledgePage) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "doc.richtext.fill")
                    .foregroundStyle(AppTheme.accent)
                Text(page.title)
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .lineLimit(2)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }

            HStack(spacing: 12) {
                if let guest = page.guestName, !guest.isEmpty {
                    Label(guest, systemImage: "person.fill")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textSecondary)
                }
                if let date = page.shootDate, !date.isEmpty {
                    Label(date, systemImage: "calendar")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                }
            }

            if let summary = page.summary, !summary.isEmpty {
                Text(summary)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                    .lineLimit(2)
            }
        }
        .padding(14)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - 検索結果
    private var searchResultsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(AppTheme.accent)
                Text("検索結果")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                Spacer()
                Text("\(viewModel.searchResults.count)件")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }

            if viewModel.searchResults.isEmpty && !viewModel.isSearching {
                Text("検索結果がありません")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
            } else {
                ForEach(viewModel.searchResults) { result in
                    searchResultCard(result)
                        .onTapGesture {
                            // 検索結果をKnowledgePageに変換してシートを開く
                            let page = KnowledgePage.fromSearchResult(result)
                            selectedPage = page
                        }
                }
            }
        }
    }

    private func searchResultCard(_ result: KnowledgeSearchResult) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "doc.text.magnifyingglass")
                    .foregroundStyle(AppTheme.accent)
                Text(result.title)
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .foregroundStyle(.white)
                    .lineLimit(1)
                Spacer()
                if let score = result.score {
                    Text(String(format: "%.0f%%", score * 100))
                        .font(.caption2)
                        .foregroundStyle(AppTheme.textMuted)
                }
            }

            if let guest = result.guestName, !guest.isEmpty {
                Label(guest, systemImage: "person.fill")
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textSecondary)
            }

            if let snippet = result.matchSnippet, !snippet.isEmpty {
                Text(snippet)
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                    .lineLimit(3)
            }
        }
        .padding(14)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    // MARK: - ページ詳細シート
    private func knowledgeDetailSheet(_ page: KnowledgePage) -> some View {
        NavigationStack {
            KnowledgePageDetailView(
                viewModel: viewModel,
                page: page
            )
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        selectedPage = nil
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left")
                            Text("戻る")
                        }
                        .foregroundStyle(AppTheme.accent)
                    }
                }
                ToolbarItem(placement: .principal) {
                    Text(page.title)
                        .font(AppTheme.sectionFont(15))
                        .foregroundStyle(.white)
                        .lineLimit(1)
                }
            }
        }
    }
}

// MARK: - ナレッジページ詳細（WKWebView表示）
struct KnowledgePageDetailView: View {
    @ObservedObject var viewModel: KnowledgePagesViewModel
    let page: KnowledgePage

    var body: some View {
        ZStack {
            AppTheme.background.ignoresSafeArea()

            if viewModel.isLoadingDetail {
                VStack(spacing: 12) {
                    ProgressView()
                        .tint(AppTheme.accent)
                    Text("ページを読み込み中...")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
            } else if let detail = viewModel.selectedPageDetail {
                if let htmlContent = detail.htmlContent, !htmlContent.isEmpty {
                    // HTML内容をWKWebViewで表示
                    KnowledgeHTMLView(htmlContent: htmlContent)
                } else if let urlString = detail.url ?? page.url,
                          let url = URL(string: urlString) {
                    // URLベースで表示
                    WebViewRepresentable(url: url)
                } else {
                    Text("このページの内容を表示できません")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
            } else {
                Text("読み込みを開始しています...")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
            }
        }
        .task {
            await viewModel.loadPageDetail(pageId: page.pageId)
        }
    }
}

/// HTML文字列をWKWebViewで表示するビュー
struct KnowledgeHTMLView: UIViewRepresentable {
    let htmlContent: String

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.isOpaque = false
        webView.backgroundColor = UIColor(AppTheme.background)
        webView.scrollView.backgroundColor = UIColor(AppTheme.background)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        // ダークテーマのCSS注入
        let styledHTML = """
        <!DOCTYPE html>
        <html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                background-color: #000000;
                color: #E5E5E5;
                font-family: -apple-system, sans-serif;
                font-size: 15px;
                line-height: 1.6;
                padding: 16px;
                margin: 0;
            }
            h1, h2, h3, h4 { color: #FFFFFF; }
            a { color: #E50914; }
            pre, code {
                background-color: #181818;
                padding: 8px;
                border-radius: 6px;
                overflow-x: auto;
            }
            table { border-collapse: collapse; width: 100%; }
            th, td {
                border: 1px solid #333;
                padding: 8px;
                text-align: left;
            }
            th { background-color: #181818; color: #E50914; }
            img { max-width: 100%; height: auto; }
        </style>
        </head>
        <body>
        \(htmlContent)
        </body>
        </html>
        """
        // ナレッジHTMLは外部コンテンツなのでbaseURLはnil（youtube.comだとReferer問題を起こす）
        webView.loadHTMLString(styledHTML, baseURL: nil)
    }
}

// MARK: - KnowledgePage拡張（検索結果からの変換用）
extension KnowledgePage {
    static func fromSearchResult(_ result: KnowledgeSearchResult) -> KnowledgePage {
        // JSONデコードをバイパスして直接初期化
        let data = try? JSONEncoder().encode([
            "page_id": result.pageId,
            "title": result.title,
            "guest_name": result.guestName ?? "",
        ])
        if let data = data,
           let page = try? JSONDecoder().decode(KnowledgePage.self, from: data) {
            return page
        }
        // フォールバック: 最小限の情報で構築
        let fallbackJSON = """
        {"page_id":"\(result.pageId)","title":"\(result.title)"}
        """.data(using: .utf8)!
        return try! JSONDecoder().decode(KnowledgePage.self, from: fallbackJSON)
    }
}
