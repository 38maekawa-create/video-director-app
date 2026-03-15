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

private struct ProjectCarouselScrollView: UIViewRepresentable {
    let projects: [VideoProject]
    let onSelect: (VideoProject) -> Void

    func makeUIView(context: Context) -> CarouselScrollView {
        let scrollView = CarouselScrollView()
        scrollView.configure(projects: projects, onSelect: onSelect)
        return scrollView
    }

    func updateUIView(_ uiView: CarouselScrollView, context: Context) {
        uiView.configure(projects: projects, onSelect: onSelect)
    }
}

private final class CarouselScrollView: UIScrollView {
    private let stackView = UIStackView()
    private var contentSignature = ""

    override init(frame: CGRect) {
        super.init(frame: frame)

        delaysContentTouches = false
        canCancelContentTouches = true
        showsHorizontalScrollIndicator = false
        showsVerticalScrollIndicator = false
        alwaysBounceHorizontal = true
        alwaysBounceVertical = false
        isDirectionalLockEnabled = true
        backgroundColor = .clear

        stackView.axis = .horizontal
        stackView.alignment = .top
        stackView.spacing = 12
        stackView.translatesAutoresizingMaskIntoConstraints = false

        addSubview(stackView)
        NSLayoutConstraint.activate([
            stackView.leadingAnchor.constraint(equalTo: contentLayoutGuide.leadingAnchor, constant: 16),
            stackView.trailingAnchor.constraint(equalTo: contentLayoutGuide.trailingAnchor, constant: -16),
            stackView.topAnchor.constraint(equalTo: contentLayoutGuide.topAnchor),
            stackView.bottomAnchor.constraint(equalTo: contentLayoutGuide.bottomAnchor),
            stackView.heightAnchor.constraint(equalTo: frameLayoutGuide.heightAnchor),
        ])
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func touchesShouldCancel(in view: UIView) -> Bool {
        true
    }

    func configure(projects: [VideoProject], onSelect: @escaping (VideoProject) -> Void) {
        let newSignature = projects.map { project in
            [
                project.id,
                project.guestName,
                project.shootDate,
                project.guestOccupation ?? "",
                String(project.unreviewedCount),
                String(project.hasUnsentFeedback),
                String(project.qualityScore ?? -1),
            ].joined(separator: "|")
        }.joined(separator: ",")
        guard newSignature != contentSignature || stackView.arrangedSubviews.isEmpty else { return }

        contentSignature = newSignature
        stackView.arrangedSubviews.forEach { view in
            stackView.removeArrangedSubview(view)
            view.removeFromSuperview()
        }

        for project in projects {
            let cardView = CarouselCardButton(project: project, onSelect: onSelect)
            stackView.addArrangedSubview(cardView)
            NSLayoutConstraint.activate([
                cardView.widthAnchor.constraint(equalToConstant: 150),
                cardView.heightAnchor.constraint(equalToConstant: 170),
            ])
        }
    }
}

private final class CarouselCardButton: UIControl {
    private let hostingController: UIHostingController<ProjectCarouselCard>
    private let project: VideoProject
    private let onSelect: (VideoProject) -> Void

    init(project: VideoProject, onSelect: @escaping (VideoProject) -> Void) {
        self.project = project
        self.onSelect = onSelect
        hostingController = UIHostingController(rootView: ProjectCarouselCard(project: project))
        super.init(frame: .zero)

        translatesAutoresizingMaskIntoConstraints = false
        backgroundColor = .clear

        let hostedView = hostingController.view!
        hostedView.translatesAutoresizingMaskIntoConstraints = false
        hostedView.backgroundColor = .clear
        hostedView.isUserInteractionEnabled = false

        addSubview(hostedView)
        NSLayoutConstraint.activate([
            hostedView.leadingAnchor.constraint(equalTo: leadingAnchor),
            hostedView.trailingAnchor.constraint(equalTo: trailingAnchor),
            hostedView.topAnchor.constraint(equalTo: topAnchor),
            hostedView.bottomAnchor.constraint(equalTo: bottomAnchor),
        ])

        addTarget(self, action: #selector(handleTap), for: .touchUpInside)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    @objc
    private func handleTap() {
        onSelect(project)
    }
}
