import SwiftUI
import UIKit

// MARK: - 画面1: プロジェクト一覧（ホーム）— Netflix風
struct ProjectListView: View {
    @ObservedObject var viewModel: ProjectListViewModel
    var onShowKnowledge: (() -> Void)? = nil
    @State private var searchText = ""
    @State private var selectedProject: VideoProject?
    @State private var showAllProjects = false

    var body: some View {
        NavigationStack {
            ScrollView(.vertical, showsIndicators: false) {
                VStack(spacing: 0) {
                    if let hero = viewModel.heroProject {
                        heroSection(hero)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                selectedProject = hero
                            }
                    }

                    searchBar

                    VStack(spacing: 24) {
                        if !viewModel.recentFeedbackProjects.isEmpty {
                            carouselSection(
                                title: "最近のフィードバック",
                                icon: "bubble.left.fill",
                                projects: viewModel.recentFeedbackProjects
                            )
                        }

                        if !viewModel.actionRequiredProjects.isEmpty {
                            carouselSection(
                                title: "要対応",
                                icon: "exclamationmark.triangle.fill",
                                projects: viewModel.actionRequiredProjects
                            )
                        }

                        carouselSection(
                            title: "全プロジェクト",
                            icon: "film.stack.fill",
                            projects: viewModel.filteredProjects,
                            showSeeAll: true
                        )

                        // カテゴリ別セクション
                        if !viewModel.tekoMemberProjects.isEmpty {
                            categorySection(
                                title: "TEKOメンバー対談",
                                icon: "person.2.fill",
                                accentColor: Color(hex: 0x4A90D9),
                                projects: viewModel.tekoMemberProjects
                            )
                        }

                        if !viewModel.tekoRealestateProjects.isEmpty {
                            categorySection(
                                title: "TEKO不動産対談",
                                icon: "building.2.fill",
                                accentColor: Color(hex: 0xE5A023),
                                projects: viewModel.tekoRealestateProjects
                            )
                        }

                        if !viewModel.uncategorizedProjects.isEmpty {
                            categorySection(
                                title: "その他",
                                icon: "questionmark.folder.fill",
                                accentColor: AppTheme.textMuted,
                                projects: viewModel.uncategorizedProjects
                            )
                        }
                    }
                    .padding(.bottom, 32)
                }
            }
            .background(AppTheme.background.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text("VIDEO DIRECTOR")
                        .font(AppTheme.heroFont(20))
                        .foregroundStyle(AppTheme.accent)
                        .tracking(4)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        onShowKnowledge?()
                    } label: {
                        Image(systemName: "book.fill")
                            .foregroundStyle(AppTheme.textSecondary)
                    }
                }
            }
            .refreshable {
                await viewModel.refresh()
            }
            .task {
                await viewModel.loadProjectsIfNeeded()
            }
            .onChange(of: searchText) { _, newValue in
                viewModel.searchText = newValue
            }
        }
        .fullScreenCover(item: $selectedProject) { project in
            NavigationStack {
                DirectionReportView(project: project)
                    .toolbar {
                        ToolbarItem(placement: .topBarLeading) {
                            Button {
                                selectedProject = nil
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: "chevron.left")
                                    Text("戻る")
                                }
                                .foregroundStyle(AppTheme.accent)
                            }
                        }
                    }
            }
        }
        .fullScreenCover(isPresented: $showAllProjects) {
            AllProjectsListView(
                projects: viewModel.filteredProjects,
                onSelect: { project in
                    showAllProjects = false
                    // 少し遅延させてからプロジェクト詳細を表示（fullScreenCover切り替え）
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                        selectedProject = project
                    }
                },
                onDismiss: {
                    showAllProjects = false
                }
            )
        }
    }

    @ViewBuilder
    private func heroSection(_ project: VideoProject) -> some View {
        ZStack(alignment: .bottomLeading) {
            ZStack {
                LinearGradient(
                    colors: [AppTheme.accent.opacity(0.3), AppTheme.cardBackground],
                    startPoint: .topTrailing,
                    endPoint: .bottomLeading
                )

                Image(systemName: project.thumbnailSymbol)
                    .font(.system(size: 80))
                    .foregroundStyle(.white.opacity(0.1))
            }
            .frame(height: 280)

            LinearGradient(
                colors: [.clear, AppTheme.background],
                startPoint: .top,
                endPoint: .bottom
            )
            .frame(height: 160)
            .frame(maxHeight: .infinity, alignment: .bottom)

            VStack(alignment: .leading, spacing: 8) {
                Text("最新プロジェクト")
                    .font(AppTheme.labelFont(11))
                    .foregroundStyle(AppTheme.accent)
                    .textCase(.uppercase)
                    .tracking(2)

                Text(project.guestName)
                    .font(.system(size: 36, weight: .bold, design: .serif))
                    .tracking(3)
                    .foregroundStyle(.white)

                Text(project.title)
                    .font(AppTheme.titleFont(20))
                    .foregroundStyle(AppTheme.textSecondary)
                    .tracking(1)

                if let errorMessage = viewModel.errorMessage {
                    Text(errorMessage)
                        .font(.caption)
                        .foregroundStyle(AppTheme.textSecondary)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(AppTheme.cardBackground.opacity(0.85))
                        .clipShape(Capsule())
                }

                HStack(spacing: 12) {
                    Label(project.shootDate, systemImage: "calendar")
                    if let score = project.qualityScore {
                        Label("スコア \(score)", systemImage: "chart.bar.fill")
                    }
                }
                .font(.caption)
                .foregroundStyle(AppTheme.textMuted)

                HStack(spacing: 8) {
                    statusBadge(project.status)
                    if project.unreviewedCount > 0 {
                        Text("未レビュー \(project.unreviewedCount)")
                            .font(.caption)
                            .fontWeight(.bold)
                            .foregroundStyle(.black)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 5)
                            .background(AppTheme.accent)
                            .clipShape(Capsule())
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 20)
        }
    }

    private var searchBar: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(AppTheme.textMuted)
            TextField("プロジェクト名、ゲスト名、日付で検索", text: $searchText)
                .foregroundStyle(.white)
                .autocorrectionDisabled()
        }
        .padding(12)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    @ViewBuilder
    private func carouselSection(title: String, icon: String, projects: [VideoProject], showSeeAll: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: icon)
                    .foregroundStyle(AppTheme.accent)
                Text(title)
                    .font(AppTheme.sectionFont(17))
                    .foregroundStyle(.white)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(showSeeAll ? AppTheme.accent : AppTheme.textMuted)
            }
            .padding(.horizontal, 16)
            .contentShape(Rectangle())
            .onTapGesture {
                if showSeeAll {
                    showAllProjects = true
                }
            }

            ProjectCarouselScrollView(projects: projects) { project in
                selectedProject = project
            }
            .frame(height: 170)
        }
    }

    @ViewBuilder
    private func categorySection(title: String, icon: String, accentColor: Color, projects: [VideoProject]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .foregroundStyle(accentColor)
                Text(title)
                    .font(AppTheme.sectionFont(17))
                    .foregroundStyle(.white)
                Text("\(projects.count)件")
                    .font(.caption)
                    .foregroundStyle(AppTheme.textMuted)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(AppTheme.cardBackground)
                    .clipShape(Capsule())
                Spacer()
            }
            .padding(.horizontal, 16)

            ProjectCarouselScrollView(projects: projects) { project in
                selectedProject = project
            }
            .frame(height: 170)
        }
    }

    private func statusBadge(_ status: ProjectStatus) -> some View {
        Text(status.label)
            .font(.caption)
            .fontWeight(.medium)
            .foregroundStyle(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(status.color.opacity(0.3))
            .clipShape(Capsule())
            .overlay(
                Capsule()
                    .strokeBorder(status.color.opacity(0.5), lineWidth: 1)
            )
    }
}

// MARK: - 全プロジェクト一覧画面（縦スクロール・グリッド）
private struct AllProjectsListView: View {
    let projects: [VideoProject]
    let onSelect: (VideoProject) -> Void
    let onDismiss: () -> Void

    private let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12),
    ]

    var body: some View {
        NavigationStack {
            ScrollView(.vertical, showsIndicators: false) {
                LazyVGrid(columns: columns, spacing: 16) {
                    ForEach(projects) { project in
                        AllProjectsCard(project: project)
                            .onTapGesture {
                                onSelect(project)
                            }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 32)
            }
            .background(AppTheme.background.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        onDismiss()
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: "chevron.left")
                            Text("ホーム")
                        }
                        .foregroundStyle(AppTheme.accent)
                    }
                }
                ToolbarItem(placement: .principal) {
                    Text("全プロジェクト")
                        .font(AppTheme.sectionFont(17))
                        .foregroundStyle(.white)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Text("\(projects.count)件")
                        .font(.caption)
                        .foregroundStyle(AppTheme.textMuted)
                }
            }
        }
    }
}

// MARK: - 全プロジェクト一覧用カード（大きめ）
private struct AllProjectsCard: View {
    let project: VideoProject

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // サムネイル部分
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(
                        LinearGradient(
                            colors: [AppTheme.cardBackground, project.status.color.opacity(0.2)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )

                Image(systemName: project.thumbnailSymbol)
                    .font(.system(size: 36))
                    .foregroundStyle(.white.opacity(0.3))

                // クオリティスコアバー
                if let score = project.qualityScore {
                    VStack {
                        Spacer()
                        GeometryReader { geo in
                            Rectangle()
                                .fill(AppTheme.accent)
                                .frame(width: geo.size.width * CGFloat(score) / 100.0, height: 3)
                        }
                        .frame(height: 3)
                    }
                }
            }
            .frame(height: 110)
            .clipShape(RoundedRectangle(cornerRadius: 10))
            .overlay(alignment: .topTrailing) {
                if project.hasUnsentFeedback {
                    Circle()
                        .fill(AppTheme.accent)
                        .frame(width: 10, height: 10)
                        .offset(x: -6, y: 6)
                }
            }
            .overlay(alignment: .topLeading) {
                // ステータスバッジ
                Text(project.status.label)
                    .font(.system(size: 9, weight: .medium))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(project.status.color.opacity(0.6))
                    .clipShape(Capsule())
                    .padding(6)
            }

            // テキスト情報
            Text(project.guestName)
                .font(.system(size: 15, weight: .bold, design: .serif))
                .tracking(1.5)
                .foregroundStyle(.white)
                .lineLimit(1)

            if let occupation = project.guestOccupation, !occupation.isEmpty {
                Text(occupation)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textSecondary)
                    .lineLimit(1)
            }

            HStack(spacing: 6) {
                Text(project.shootDate)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textMuted)

                if project.unreviewedCount > 0 {
                    Text("未レビュー\(project.unreviewedCount)")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(.black)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(AppTheme.accent)
                        .clipShape(Capsule())
                }
            }
        }
        .padding(10)
        .background(AppTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

private struct ProjectCarouselCard: View {
    let project: VideoProject

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ZStack {
                RoundedRectangle(cornerRadius: 8)
                    .fill(
                        LinearGradient(
                            colors: [AppTheme.cardBackground, project.status.color.opacity(0.2)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )

                Image(systemName: project.thumbnailSymbol)
                    .font(.system(size: 32))
                    .foregroundStyle(.white.opacity(0.3))

                if let score = project.qualityScore {
                    VStack {
                        Spacer()
                        Rectangle()
                            .fill(AppTheme.accent)
                            .frame(height: 3)
                            .frame(
                                width: 150 * CGFloat(score) / 100.0,
                                alignment: .leading
                            )
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
            .frame(width: 150, height: 100)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(alignment: .topTrailing) {
                if project.hasUnsentFeedback {
                    Circle()
                        .fill(AppTheme.accent)
                        .frame(width: 10, height: 10)
                        .offset(x: -4, y: 4)
                }
            }

            Text(project.guestName)
                .font(.system(size: 14, weight: .bold, design: .serif))
                .tracking(1.5)
                .foregroundStyle(.white)
                .lineLimit(1)

            if let occupation = project.guestOccupation, !occupation.isEmpty {
                Text(occupation)
                    .font(.caption2)
                    .foregroundStyle(AppTheme.textSecondary)
                    .lineLimit(1)
            }

            Text(project.shootDate)
                .font(.caption2)
                .foregroundStyle(AppTheme.textMuted)
        }
        .frame(width: 150, height: 170, alignment: .top)
    }
}

// MARK: - UICollectionViewベースのカルーセル（タップ確実動作）
// UICollectionView.didSelectItemAt はiOS標準のセル選択機能。
// ScrollView内タップ問題（SwiftUI/UIControl 11回失敗）を根本解決。
private struct ProjectCarouselScrollView: UIViewControllerRepresentable {
    let projects: [VideoProject]
    let onSelect: (VideoProject) -> Void

    func makeUIViewController(context: Context) -> CarouselCollectionVC {
        let vc = CarouselCollectionVC()
        vc.configure(projects: projects, onSelect: onSelect)
        return vc
    }

    func updateUIViewController(_ vc: CarouselCollectionVC, context: Context) {
        vc.configure(projects: projects, onSelect: onSelect)
    }
}

final class CarouselCollectionVC: UIViewController {
    private var collectionView: UICollectionView!
    private var projects: [VideoProject] = []
    private var onSelect: ((VideoProject) -> Void)?
    private var currentIDs = ""

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .clear

        // Compositional Layout: 横スクロール
        let itemSize = NSCollectionLayoutSize(
            widthDimension: .absolute(150),
            heightDimension: .absolute(170)
        )
        let item = NSCollectionLayoutItem(layoutSize: itemSize)

        let groupSize = NSCollectionLayoutSize(
            widthDimension: .absolute(150),
            heightDimension: .absolute(170)
        )
        let group = NSCollectionLayoutGroup.horizontal(layoutSize: groupSize, subitems: [item])

        let section = NSCollectionLayoutSection(group: group)
        section.orthogonalScrollingBehavior = .continuous
        section.interGroupSpacing = 12
        section.contentInsets = NSDirectionalEdgeInsets(top: 0, leading: 16, bottom: 0, trailing: 16)

        let layout = UICollectionViewCompositionalLayout(section: section)

        collectionView = UICollectionView(frame: .zero, collectionViewLayout: layout)
        collectionView.backgroundColor = .clear
        collectionView.delegate = self
        collectionView.dataSource = self
        collectionView.register(CarouselCardCell.self, forCellWithReuseIdentifier: CarouselCardCell.reuseID)
        collectionView.translatesAutoresizingMaskIntoConstraints = false
        collectionView.showsHorizontalScrollIndicator = false

        view.addSubview(collectionView)
        NSLayoutConstraint.activate([
            collectionView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            collectionView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            collectionView.topAnchor.constraint(equalTo: view.topAnchor),
            collectionView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])

        // viewDidLoad前にconfigure()が呼ばれた場合のデータ反映
        if !projects.isEmpty {
            collectionView.reloadData()
        }
    }

    func configure(projects: [VideoProject], onSelect: @escaping (VideoProject) -> Void) {
        let ids = projects.map(\.id).joined(separator: ",")
        self.onSelect = onSelect
        guard ids != currentIDs else { return }
        currentIDs = ids
        self.projects = projects
        collectionView?.reloadData()
    }
}

extension CarouselCollectionVC: UICollectionViewDataSource {
    func collectionView(_ cv: UICollectionView, numberOfItemsInSection section: Int) -> Int {
        projects.count
    }

    func collectionView(_ cv: UICollectionView, cellForItemAt indexPath: IndexPath) -> UICollectionViewCell {
        let cell = cv.dequeueReusableCell(withReuseIdentifier: CarouselCardCell.reuseID, for: indexPath) as! CarouselCardCell
        cell.set(project: projects[indexPath.item])
        return cell
    }
}

extension CarouselCollectionVC: UICollectionViewDelegate {
    func collectionView(_ cv: UICollectionView, didSelectItemAt indexPath: IndexPath) {
        onSelect?(projects[indexPath.item])
    }
}

private final class CarouselCardCell: UICollectionViewCell {
    static let reuseID = "CarouselCardCell"
    private var hostingController: UIHostingController<ProjectCarouselCard>?

    override func prepareForReuse() {
        super.prepareForReuse()
        hostingController?.willMove(toParent: nil)
        hostingController?.view.removeFromSuperview()
        hostingController?.removeFromParent()
        hostingController = nil
    }

    func set(project: VideoProject) {
        prepareForReuse()

        let hc = UIHostingController(rootView: ProjectCarouselCard(project: project))
        hc.view.translatesAutoresizingMaskIntoConstraints = false
        hc.view.backgroundColor = .clear
        // タッチをセルに透過させる（didSelectItemAtが発火するように）
        hc.view.isUserInteractionEnabled = false

        // UIHostingControllerを正しくVC hierarchyに登録（レイアウト安定化）
        if let parentVC = findParentViewController() {
            parentVC.addChild(hc)
            contentView.addSubview(hc.view)
            hc.didMove(toParent: parentVC)
        } else {
            contentView.addSubview(hc.view)
        }

        NSLayoutConstraint.activate([
            hc.view.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            hc.view.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            hc.view.topAnchor.constraint(equalTo: contentView.topAnchor),
            hc.view.bottomAnchor.constraint(equalTo: contentView.bottomAnchor),
        ])
        hostingController = hc
    }

    private func findParentViewController() -> UIViewController? {
        var responder: UIResponder? = self
        while let next = responder?.next {
            if let vc = next as? UIViewController {
                return vc
            }
            responder = next
        }
        return nil
    }
}
