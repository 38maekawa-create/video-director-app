import SwiftUI

@main
struct VideoDirectorAgentApp: App {
    var body: some Scene {
        WindowGroup {
            RootTabView()
                .preferredColorScheme(.dark)
                .tint(AppTheme.accent)
        }
    }
}
