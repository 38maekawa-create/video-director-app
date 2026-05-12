import SwiftUI

@main
struct VideoDirectorAgentApp: App {
    @Environment(\.scenePhase) private var scenePhase

    init() {
        print("API Primary: \(APIClient.shared.primaryURL.absoluteString)")
    }

    var body: some Scene {
        WindowGroup {
            if ProcessInfo.processInfo.arguments.contains("--ui-test-before-after") {
                BeforeAfterUITestHarness()
                    .preferredColorScheme(.dark)
                    .tint(AppTheme.accent)
            } else if ProcessInfo.processInfo.arguments.contains("--ui-test-direction-before-after") {
                DirectionBeforeAfterUITestHarness()
                    .preferredColorScheme(.dark)
                    .tint(AppTheme.accent)
            } else {
                RootTabView()
                    .preferredColorScheme(.dark)
                    .tint(AppTheme.accent)
                    .task {
                        // アプリ起動時に到達可能なAPIサーバーを自動検出
                        await APIClient.shared.probeAndConnect()
                    }
            }
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                // BG→FG復帰時に再接続を実行
                // hasEverConnected=trueの場合、probeAndConnect内で
                // connectingバナーを出さないように制御済み
                print("📱 ScenePhase → active: 再接続を開始")
                Task {
                    await APIClient.shared.probeAndConnect()
                }
            }
        }
    }
}

private struct BeforeAfterUITestHarness: View {
    @State private var showBeforeAfter = false
    @State private var isReady = false

    private let projectId = "p-20260328-バーボン"

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Text("BeforeAfter UI Test")
                    .font(AppTheme.sectionFont(18))
                    .foregroundStyle(.white)

                Button {
                    showBeforeAfter = true
                } label: {
                    Text(isReady ? "ビフォーアフター" : "接続確認中")
                        .font(AppTheme.labelFont(15))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 18)
                        .padding(.vertical, 12)
                        .background(isReady ? AppTheme.accent : AppTheme.textMuted)
                        .clipShape(Capsule())
                }
                .disabled(!isReady)
                .accessibilityIdentifier("ui-test-open-before-after")
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(AppTheme.background.ignoresSafeArea())
        }
        .task {
            await APIClient.shared.probeAndConnect()
            isReady = true
        }
        .fullScreenCover(isPresented: $showBeforeAfter) {
            BeforeAfterView(projectId: projectId, projectTitle: "UI Test")
                .accessibilityIdentifier("ui-test-before-after-screen")
        }
    }
}

private struct DirectionBeforeAfterUITestHarness: View {
    @State private var showProject = false

    private let project = VideoProject(
        id: "p-20260328-バーボン",
        guestName: "バーボン",
        title: "UI Test",
        shootDate: "2026/03/28",
        status: .directed
    )

    var body: some View {
        Button {
            showProject = true
        } label: {
            Text("Open Direction Report")
                .font(AppTheme.labelFont(15))
                .foregroundStyle(.white)
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
                .background(AppTheme.accent)
                .clipShape(Capsule())
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(AppTheme.background.ignoresSafeArea())
        .accessibilityIdentifier("ui-test-open-direction-report")
        .task {
            await APIClient.shared.probeAndConnect()
        }
        .fullScreenCover(isPresented: $showProject) {
            NavigationStack {
                DirectionReportView(project: project)
            }
        }
    }
}
