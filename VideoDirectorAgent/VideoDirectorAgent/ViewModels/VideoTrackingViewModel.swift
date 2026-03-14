import Foundation

@MainActor
final class VideoTrackingViewModel: ObservableObject {
    @Published var videos: [TrackedVideo] = []
    @Published var insights: [TrackingInsight] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    func load() async {
        if isLoading { return }
        isLoading = true
        defer { isLoading = false }

        async let videosTask = APIClient.shared.fetchTrackingVideos()
        async let insightsTask = APIClient.shared.fetchTrackingInsights()

        do {
            videos = try await videosTask
            insights = try await insightsTask
            errorMessage = nil
        } catch {
            errorMessage = "トラッキングAPIに接続できません: \(error.localizedDescription)"
        }
    }
}
