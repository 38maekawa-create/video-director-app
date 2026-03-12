import Foundation

@MainActor
final class VideoTrackingViewModel: ObservableObject {
    @Published var videos: [TrackedVideo] = MockData.trackedVideos
    @Published var insights: [TrackingInsight] = MockData.trackingInsights
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
            videos = MockData.trackedVideos
            insights = MockData.trackingInsights
            errorMessage = "トラッキングAPIに接続できなかったためモックデータを表示しています"
        }
    }
}
