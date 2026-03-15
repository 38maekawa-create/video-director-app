import Foundation
import SwiftUI

enum ProjectStatus: String, CaseIterable {
    case directed = "ディレクション済"
    case editing = "編集中"
    case reviewPending = "レビュー待ち"
    case published = "公開"

    var color: Color {
        switch self {
        case .directed: return .blue
        case .editing: return .orange
        case .reviewPending: return .yellow
        case .published: return .green
        }
    }
}

struct VideoProject: Identifiable {
    let id: UUID
    let title: String
    let thumbnailSymbol: String
    let status: ProjectStatus
    let unreviewedCount: Int
}

struct ReportSection: Identifiable {
    let id: UUID
    let title: String
    let items: [String]
}

struct TimelineMarker: Identifiable {
    let id: UUID
    let time: TimeInterval
    let label: String
}

enum FeedbackPriority: String {
    case high = "高"
    case medium = "中"
    case low = "低"

    var color: Color {
        switch self {
        case .high: return .red
        case .medium: return .orange
        case .low: return .blue
        }
    }
}

struct StructuredFeedback: Identifiable {
    let id: UUID
    let timestamp: String
    let element: String
    let priority: FeedbackPriority
    let note: String
}

struct FeedbackHistoryItem: Identifiable {
    let id: UUID
    let projectTitle: String
    let timestamp: String
    let rawVoiceText: String
    let convertedText: String
    let editorStatus: String
    let learningEffect: String
}

struct QualityTrendPoint: Identifiable {
    let id: UUID
    let label: String
    let score: Int
}

struct EditorSkill: Identifiable {
    let id: UUID
    let editorName: String
    let strengths: [String]
    let weakPoints: [String]
    let growth: Int
}

struct QualityAlert: Identifiable {
    let id: UUID
    let level: String
    let message: String
}

enum SendDestination: String, CaseIterable {
    case vimeo = "Vimeoレビュー"
    case chat = "編集者チャット"
}

enum AppTheme {
    static let accent = Color(red: 0.22, green: 0.58, blue: 0.96)
    static let background = Color(red: 0.06, green: 0.08, blue: 0.12)
    static let card = Color(red: 0.12, green: 0.14, blue: 0.20)
}

// --- YouTube素材モデル ---

/// サムネイル指示書: Z型4ゾーンのレイアウト指示
struct ThumbnailZones: Codable {
    let topLeft: String
    let topRight: String
    let bottomLeft: String
    let bottomRight: String

    enum CodingKeys: String, CodingKey {
        case topLeft = "top_left"
        case topRight = "top_right"
        case bottomLeft = "bottom_left"
        case bottomRight = "bottom_right"
    }
}

/// YouTube公開素材: サムネイル指示書・タイトル案・概要欄
struct YouTubeAssets: Codable {
    let thumbnailZones: ThumbnailZones
    let titleCandidates: [String]
    let description: String

    enum CodingKeys: String, CodingKey {
        case thumbnailZones = "thumbnail_zones"
        case titleCandidates = "title_candidates"
        case description
    }
}

// --- before/after 品質スコア比較モデル ---

/// 編集前後の品質スコア差分（要素単位）
struct QualityScoreComparison: Identifiable {
    let id: UUID
    let element: String
    let beforeScore: Int
    let afterScore: Int
    /// 改善幅（正=改善、負=悪化）
    var diff: Int { afterScore - beforeScore }
}
