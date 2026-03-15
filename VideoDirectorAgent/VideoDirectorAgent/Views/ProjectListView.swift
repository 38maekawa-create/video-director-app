import SwiftUI
import UIKit

// MARK: - 画面1: プロジェクト一覧（ホーム）— Netflix風
struct ProjectListView: View {
    @ObservedObject var viewModel: ProjectListViewModel
    @State private var searchText = ""
    @State private var selectedProject: VideoProject?

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
                            projects: viewModel.filteredProjects
                        )
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
    private func carouselSection(title: String, icon: String, projects: [VideoProject]) -> some View {
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
                    .foregroundStyle(AppTheme.textMuted)
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
