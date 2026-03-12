import SwiftUI

@main
struct VideoDirectorAgentApp: App {
    init() {
        print("🚀 API Base: http://localhost:8210")
    }

    var body: some Scene {
        WindowGroup {
            RootTabView()
                .preferredColorScheme(.dark)
                .tint(AppTheme.accent)
        }
    }
}
