import SwiftUI

@main
struct VideoDirectorAgentApp: App {
    init() {
        print("API Base: \(APIClient.shared.baseURL.absoluteString)")
    }

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .preferredColorScheme(.dark)
                .tint(AppTheme.accent)
        }
    }
}
