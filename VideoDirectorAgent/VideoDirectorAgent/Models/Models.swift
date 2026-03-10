import Foundation
import SwiftUI

// MARK: - Netflix風カラーパレット
enum AppTheme {
    // 背景系
    static let background = Color(hex: 0x000000)       // 純黒
    static let cardBackground = Color(hex: 0x181818)    // ダークグレー（Netflixカード色）
    static let cardBackgroundLight = Color(hex: 0x222222)

    // アクセント
    static let accent = Color(hex: 0xE50914)            // Netflix赤
    static let accentGlow = Color(hex: 0xE50914).opacity(0.4)

    // テキスト
    static let textPrimary = Color.white
    static let textSecondary = Color(hex: 0xE5E5E5)     // ウォームホワイト
    static let textMuted = Color(hex: 0x808080)          // グレー

    // ステータス
    static let statusComplete = Color(hex: 0x46D369)     // Netflix風グリーン
    static let statusRecording = Color(hex: 0xE50914)    // パルスレッド

    // フォント — Netflix風スタイリッシュ
    // ヒーロータイトル（コンデンスド+ヘビー、映画ポスター風）
    static func heroFont(_ size: CGFloat) -> Font {
        .system(size: size, weight: .heavy, design: .default).width(.condensed)
    }
    // セクション見出し（太めのセリフ体、シネマ風）
    static func sectionFont(_ size: CGFloat) -> Font {
        .system(size: size, weight: .bold, design: .serif)
    }
    // 映像タイトル（イタリックセリフ、映画クレジット風）
    static func titleFont(_ size: CGFloat) -> Font {
        .system(size: size, weight: .light, design: .serif).italic()
    }
    // ナビ/ラベル（コンデンスド+ボールド、コンパクト）
    static func labelFont(_ size: CGFloat) -> Font {
        .system(size: size, weight: .bold, design: .default).width(.condensed)
    }
    // 本文（クリーンなデフォルト）
    static func bodyFont(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .default)
    }
}

// MARK: - Color Hex拡張
extension Color {
    init(hex: UInt, alpha: Double = 1.0) {
        self.init(
            red: Double((hex >> 16) & 0xFF) / 255.0,
            green: Double((hex >> 8) & 0xFF) / 255.0,
            blue: Double(hex & 0xFF) / 255.0,
            opacity: alpha
        )
    }
}

// MARK: - プロジェクト関連モデル
enum ProjectStatus: String, CaseIterable {
    case directed = "ディレクション済"
    case editing = "編集中"
    case reviewPending = "レビュー待ち"
    case published = "公開"

    var color: Color {
        switch self {
        case .directed: return Color(hex: 0x4A90D9)
        case .editing: return Color(hex: 0xF5A623)
        case .reviewPending: return AppTheme.accent
        case .published: return AppTheme.statusComplete
        }
    }
}

struct VideoProject: Identifiable {
    let id: UUID
    let guestName: String           // ゲスト名
    let title: String               // プロジェクト名
    let thumbnailSymbol: String     // SF Symbols（サムネイル代替）
    let shootDate: String           // 撮影日
    let guestAge: Int?              // 年齢
    let guestOccupation: String?    // 職業
    let status: ProjectStatus
    let unreviewedCount: Int
    let qualityScore: Int?          // 品質スコア
    let hasUnsentFeedback: Bool     // 未送信FBあり
}

struct ReportSection: Identifiable {
    let id: UUID
    let title: String
    let icon: String                // SF Symbols
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
        case .high: return AppTheme.accent
        case .medium: return Color(hex: 0xF5A623)
        case .low: return Color(hex: 0x4A90D9)
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
    let guestName: String
    let date: String                // 日付（グループ化用）
    let timestamp: String
    let rawVoiceText: String
    let convertedText: String
    let isSent: Bool                // 送信済み
    let editorStatus: String
    let learningEffect: String
}

struct QualityTrendPoint: Identifiable {
    let id: UUID
    let label: String
    let score: Int
}

struct CategoryScore: Identifiable {
    let id: UUID
    let category: String
    let score: Int
    let icon: String
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

struct ImprovementSuggestion: Identifiable {
    let id: UUID
    let category: String
    let suggestion: String
    let priority: FeedbackPriority
}

enum SendDestination: String, CaseIterable {
    case vimeo = "Vimeoレビュー"
    case chat = "編集者チャット"
}
