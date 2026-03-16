import SwiftUI

@main
struct VideoDirectorAgentApp: App {
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
    }
}
