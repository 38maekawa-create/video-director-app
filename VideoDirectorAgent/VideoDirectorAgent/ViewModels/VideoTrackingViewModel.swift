import Foundation

@MainActor
final class VideoTrackingViewModel: ObservableObject {
    @Published var videos: [TrackedVideo] = []
    @Published var insights: [TrackingInsight] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    private var hasLoaded = false

    func load(forceRefresh: Bool = false) async {
        if !forceRefresh && hasLoaded { return }
        if isLoading { return }
        isLoading = true
        defer { isLoading = false }

        var errors: [String] = []

        do {
            videos = try await APIClient.shared.fetchTrackingVideos()
        } catch {
            if videos.isEmpty { errors.append("動画") }
        }

        do {
            insights = try await APIClient.shared.fetchTrackingInsights()
        } catch {
            if insights.isEmpty { errors.append("インサイト") }
        }

        if errors.isEmpty {
            errorMessage = nil
            hasLoaded = true
        } else {
            errorMessage = "\(errors.joined(separator: "・"))の取得に失敗しました"
        }
    }
}
