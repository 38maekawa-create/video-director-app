import SwiftUI

@main
struct VideoDirectorAgentApp: App {
    @Environment(\.scenePhase) private var scenePhase

    init() {
        print("API Primary: \(APIClient.shared.primaryURL.absoluteString)")
    }

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .preferredColorScheme(.dark)
                .tint(AppTheme.accent)
                .task {
                    // アプリ起動時に到達可能なAPIサーバーを自動検出
                    await APIClient.shared.probeAndConnect()
                }
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                // BG→FG復帰時に再接続を実行
                print("📱 ScenePhase → active: 再接続を開始")
                Task {
                    await APIClient.shared.probeAndConnect()
                }
            }
        }
    }
}
