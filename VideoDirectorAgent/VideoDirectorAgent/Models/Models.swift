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
enum ProjectStatus: String, CaseIterable, Codable {
    case directed
    case editing
    case reviewPending
    case published

    var label: String {
        switch self {
        case .directed: return "ディレクション済"
        case .editing: return "編集中"
        case .reviewPending: return "レビュー待ち"
        case .published: return "公開"
        }
    }

    var color: Color {
        switch self {
        case .directed: return Color(hex: 0x4A90D9)
        case .editing: return Color(hex: 0xF5A623)
        case .reviewPending: return AppTheme.accent
        case .published: return AppTheme.statusComplete
        }
    }
}

struct VideoProject: Identifiable, Codable, Hashable {
    static func == (lhs: VideoProject, rhs: VideoProject) -> Bool { lhs.id == rhs.id }
    func hash(into hasher: inout Hasher) { hasher.combine(id) }

    let id: String
    let guestName: String
    let title: String
    let thumbnailSymbol: String
    let shootDate: String
    let guestAge: Int?
    let guestOccupation: String?
    let status: ProjectStatus
    let unreviewedCount: Int
    let qualityScore: Int?
    let hasUnsentFeedback: Bool
    let directionReportURL: String?
    let sourceVideoURL: String?
    let editedVideoURL: String?
    let knowledge: String?
    let category: String?
    let knowledgePageUrl: String?

    /// カテゴリの表示名
    var categoryDisplayName: String {
        switch category {
        case "teko_member": return "TEKOメンバー対談"
        case "teko_realestate": return "TEKO不動産対談"
        default: return "その他"
        }
    }

    /// カテゴリのアイコン（SF Symbols）
    var categoryIcon: String {
        switch category {
        case "teko_member": return "person.2.fill"
        case "teko_realestate": return "building.2.fill"
        default: return "questionmark.folder.fill"
        }
    }

    /// カテゴリのアクセントカラー
    var categoryColor: Color {
        switch category {
        case "teko_member": return Color(hex: 0x4A90D9)      // ブルー
        case "teko_realestate": return Color(hex: 0xE5A023)   // ゴールド
        default: return AppTheme.textMuted
        }
    }

    init(
        id: String,
        guestName: String,
        title: String,
        thumbnailSymbol: String = "video.fill",
        shootDate: String,
        guestAge: Int? = nil,
        guestOccupation: String? = nil,
        status: ProjectStatus,
        unreviewedCount: Int = 0,
        qualityScore: Int? = nil,
        hasUnsentFeedback: Bool = false,
        directionReportURL: String? = nil,
        sourceVideoURL: String? = nil,
        editedVideoURL: String? = nil,
        knowledge: String? = nil,
        category: String? = nil,
        knowledgePageUrl: String? = nil
    ) {
        self.id = id
        self.guestName = guestName
        self.title = title
        self.thumbnailSymbol = thumbnailSymbol
        self.shootDate = shootDate
        self.guestAge = guestAge
        self.guestOccupation = guestOccupation
        self.status = status
        self.unreviewedCount = unreviewedCount
        self.qualityScore = qualityScore
        self.hasUnsentFeedback = hasUnsentFeedback
        self.directionReportURL = directionReportURL
        self.sourceVideoURL = sourceVideoURL
        self.editedVideoURL = editedVideoURL
        self.knowledge = knowledge
        self.category = category
        self.knowledgePageUrl = knowledgePageUrl
    }

    enum CodingKeys: String, CodingKey {
        case id
        case guestName
        case title
        case thumbnailSymbol
        case shootDate
        case guestAge
        case guestOccupation
        case status
        case unreviewedCount
        case qualityScore
        case hasUnsentFeedback
        case directionReportURL
        case sourceVideoURL
        case editedVideoURL
        case knowledge
        case category
        case knowledgePageUrl
        // デコード専用キー（APIレスポンスのネスト構造を展開するため）
        case sourceVideo
        case editedVideo
        case feedbackSummary
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(guestName, forKey: .guestName)
        try container.encode(title, forKey: .title)
        try container.encode(thumbnailSymbol, forKey: .thumbnailSymbol)
        try container.encode(shootDate, forKey: .shootDate)
        try container.encodeIfPresent(guestAge, forKey: .guestAge)
        try container.encodeIfPresent(guestOccupation, forKey: .guestOccupation)
        try container.encode(status, forKey: .status)
        try container.encode(unreviewedCount, forKey: .unreviewedCount)
        try container.encodeIfPresent(qualityScore, forKey: .qualityScore)
        try container.encode(hasUnsentFeedback, forKey: .hasUnsentFeedback)
        try container.encodeIfPresent(directionReportURL, forKey: .directionReportURL)
        try container.encodeIfPresent(sourceVideoURL, forKey: .sourceVideoURL)
        try container.encodeIfPresent(editedVideoURL, forKey: .editedVideoURL)
        try container.encodeIfPresent(knowledge, forKey: .knowledge)
        try container.encodeIfPresent(category, forKey: .category)
        try container.encodeIfPresent(knowledgePageUrl, forKey: .knowledgePageUrl)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        guestName = try container.decode(String.self, forKey: .guestName)
        title = try container.decode(String.self, forKey: .title)
        shootDate = try container.decodeIfPresent(String.self, forKey: .shootDate) ?? ""
        guestAge = try container.decodeIfPresent(Int.self, forKey: .guestAge)
        guestOccupation = try container.decodeIfPresent(String.self, forKey: .guestOccupation)
        unreviewedCount = try container.decodeIfPresent(Int.self, forKey: .unreviewedCount) ?? 0
        qualityScore = try container.decodeIfPresent(Int.self, forKey: .qualityScore)
        hasUnsentFeedback = try container.decodeIfPresent(Bool.self, forKey: .hasUnsentFeedback) ?? false
        directionReportURL = try container.decodeIfPresent(String.self, forKey: .directionReportURL)
        sourceVideoURL = VideoProject.decodeNestedURL(from: container, key: .sourceVideoURL, fallbackKey: .sourceVideo)
        editedVideoURL = VideoProject.decodeNestedURL(from: container, key: .editedVideoURL, fallbackKey: .editedVideo)
        knowledge = VideoProject.decodeKnowledgeText(from: container)
        category = try container.decodeIfPresent(String.self, forKey: .category)
        knowledgePageUrl = try container.decodeIfPresent(String.self, forKey: .knowledgePageUrl)

        // APIはsnake_case（"review_pending"）を返すが、enumのrawValueはcamelCase（"reviewPending"）
        // decodeIfPresentは値が存在するがデコード失敗時にエラーを投げるため、
        // まずStringとしてデコードし、snake_case→camelCase変換してからenum化する
        if let statusStr = try container.decodeIfPresent(String.self, forKey: .status) {
            // snake_case → camelCase 変換（"review_pending" → "reviewPending"）
            let camelCase = statusStr.split(separator: "_").enumerated().map { index, part in
                index == 0 ? String(part) : part.capitalized
            }.joined()
            self.status = ProjectStatus(rawValue: camelCase) ?? .directed
        } else {
            self.status = .directed
        }

        thumbnailSymbol = try container.decodeIfPresent(String.self, forKey: .thumbnailSymbol)
            ?? VideoProject.defaultThumbnailSymbol(for: title)
    }

    static func defaultThumbnailSymbol(for title: String) -> String {
        if title.contains("採用") { return "person.2.fill" }
        if title.contains("ブランド") { return "sparkles.tv.fill" }
        if title.contains("イベント") { return "film.stack.fill" }
        if title.contains("不動産") { return "building.2.fill" }
        return "video.fill"
    }

    private static func decodeNestedURL(
        from container: KeyedDecodingContainer<CodingKeys>,
        key: CodingKeys,
        fallbackKey: CodingKeys
    ) -> String? {
        // デバッグ: コンテナ内の全キーを出力
        print("[decodeNestedURL] key=\(key.stringValue), fallback=\(fallbackKey.stringValue), allKeys=\(container.allKeys.map { $0.stringValue })")
        if let direct = try? container.decodeIfPresent(String.self, forKey: key), !direct.isEmpty {
            print("[decodeNestedURL] primary hit: \(direct)")
            return direct
        }
        // fallbackKeyが文字列URLの場合（例: edited_video が "https://vimeo.com/..." の場合）
        if let directFallback = try? container.decodeIfPresent(String.self, forKey: fallbackKey), !directFallback.isEmpty {
            print("[decodeNestedURL] fallback hit: \(directFallback)")
            return directFallback
        }
        print("[decodeNestedURL] fallback String decode failed, trying JSON object...")
        // fallbackKeyがオブジェクトの場合（例: edited_video が { "url": "...", "vimeoUrl": "..." } の場合）
        if let payload = try? container.decodeIfPresent([String: JSONValue].self, forKey: fallbackKey) {
            print("[decodeNestedURL] JSON object found: \(payload.keys)")
            for candidateKey in ["url", "vimeoUrl", "videoUrl", "link"] {
                if let value = payload[candidateKey]?.stringValue, !value.isEmpty {
                    return value
                }
            }
        }
        print("[decodeNestedURL] returning nil")
        return nil
    }

    private static func decodeKnowledgeText(from container: KeyedDecodingContainer<CodingKeys>) -> String? {
        if let direct = try? container.decodeIfPresent(String.self, forKey: .knowledge), !direct.isEmpty {
            return direct
        }
        if let payload = try? container.decodeIfPresent([String: JSONValue].self, forKey: .knowledge) {
            if let highlights = payload["highlights"]?.arrayValue {
                let lines = highlights.compactMap { item -> String? in
                    guard let object = item.objectValue else { return nil }
                    let timestamp = object["timestamp"]?.stringValue ?? ""
                    let category = object["category"]?.stringValue ?? ""
                    let text = object["text"]?.stringValue ?? ""
                    let prefix = [timestamp, category].filter { !$0.isEmpty }.joined(separator: " ")
                    return [prefix, text].filter { !$0.isEmpty }.joined(separator: " ")
                }.filter { !$0.isEmpty }
                if !lines.isEmpty {
                    return lines.joined(separator: "\n")
                }
            }
            return payload.values.compactMap(\.stringValue).joined(separator: "\n")
        }
        return nil
    }
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

struct StructuredFeedbackItem: Codable, Identifiable {
    let id: String
    let timestamp: String?
    let element: String
    let priority: String
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

// MARK: - YouTube素材モデル
struct YouTubeAssets: Codable {
    var projectId: String
    var thumbnailDesign: ThumbnailDesign?
    var titleProposals: TitleProposals?
    var descriptionOriginal: String?
    var descriptionEdited: String?
    var descriptionFinalizedAt: String?
    var descriptionFinalizedBy: String?
    var selectedTitleIndex: Int?
    var editedTitle: String?
    var lastEditedBy: String?
    var generatedAt: String?
    var updatedAt: String?

    var activeDescription: String {
        if let descriptionEdited, !descriptionEdited.isEmpty {
            return descriptionEdited
        }
        return descriptionOriginal ?? ""
    }
}

struct ThumbnailDesign: Codable {
    var overallConcept: String
    var fontSuggestion: String
    var backgroundSuggestion: String
    var zones: [ThumbnailZone]

    init(
        overallConcept: String,
        fontSuggestion: String,
        backgroundSuggestion: String,
        zones: [ThumbnailZone]
    ) {
        self.overallConcept = overallConcept
        self.fontSuggestion = fontSuggestion
        self.backgroundSuggestion = backgroundSuggestion
        self.zones = zones
    }

    enum CodingKeys: String, CodingKey {
        case overallConcept
        case fontSuggestion
        case backgroundSuggestion
        case zones
        case topLeft
        case topRight
        case diagonal
        case bottomRight
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        overallConcept = try container.decodeIfPresent(String.self, forKey: .overallConcept) ?? ""
        fontSuggestion = try container.decodeIfPresent(String.self, forKey: .fontSuggestion) ?? ""
        backgroundSuggestion = try container.decodeIfPresent(String.self, forKey: .backgroundSuggestion) ?? ""

        if let zones = try container.decodeIfPresent([ThumbnailZone].self, forKey: .zones), !zones.isEmpty {
            self.zones = zones
        } else {
            let decodedZones = [
                try container.decodeIfPresent(ThumbnailZone.self, forKey: .topLeft),
                try container.decodeIfPresent(ThumbnailZone.self, forKey: .topRight),
                try container.decodeIfPresent(ThumbnailZone.self, forKey: .diagonal),
                try container.decodeIfPresent(ThumbnailZone.self, forKey: .bottomRight)
            ].compactMap { $0 }
            self.zones = decodedZones
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(overallConcept, forKey: .overallConcept)
        try container.encode(fontSuggestion, forKey: .fontSuggestion)
        try container.encode(backgroundSuggestion, forKey: .backgroundSuggestion)
        try container.encode(zones, forKey: .zones)
    }
}

struct ThumbnailZone: Codable, Identifiable {
    var id: String { role }
    var role: String
    var content: String
    var colorSuggestion: String
    var notes: String
}

struct TitleProposals: Codable {
    var candidates: [TitleCandidate]
    var recommendedIndex: Int
}

struct TitleCandidate: Codable, Identifiable {
    var id: String { title }
    var title: String
    var targetSegment: String
    var appealType: String
    var rationale: String
}

struct FeedbackItem: Identifiable, Codable {
    let id: String
    let projectId: String
    let content: String
    let createdBy: String
    let createdAt: String
    let timestamp: String?
    let feedbackType: String?
    let projectTitle: String?
    let guestName: String?
    let rawVoiceText: String?
    let convertedText: String?
    let isSent: Bool

    init(
        id: String,
        projectId: String,
        content: String,
        createdBy: String,
        createdAt: String,
        timestamp: String?,
        feedbackType: String?,
        projectTitle: String?,
        guestName: String?,
        rawVoiceText: String?,
        convertedText: String?,
        isSent: Bool
    ) {
        self.id = id
        self.projectId = projectId
        self.content = content
        self.createdBy = createdBy
        self.createdAt = createdAt
        self.timestamp = timestamp
        self.feedbackType = feedbackType
        self.projectTitle = projectTitle
        self.guestName = guestName
        self.rawVoiceText = rawVoiceText
        self.convertedText = convertedText
        self.isSent = isSent
    }

    enum CodingKeys: String, CodingKey {
        case id
        case projectId
        case content
        case createdBy
        case createdAt
        case timestamp
        case feedbackType
        case timestampMark
        case rawVoiceText
        case convertedText
        case category
        case priority
        case projectTitle
        case guestName
        case isSent
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        if let intId = try? container.decode(Int.self, forKey: .id) {
            id = String(intId)
        } else {
            id = try container.decode(String.self, forKey: .id)
        }
        projectId = try container.decodeIfPresent(String.self, forKey: .projectId) ?? ""
        let converted = try container.decodeIfPresent(String.self, forKey: .convertedText)
        let raw = try container.decodeIfPresent(String.self, forKey: .rawVoiceText)
        convertedText = converted
        rawVoiceText = raw
        content = (converted?.isEmpty == false ? converted : raw) ?? ""
        createdBy = try container.decodeIfPresent(String.self, forKey: .createdBy) ?? "unknown"
        createdAt = try container.decodeIfPresent(String.self, forKey: .createdAt) ?? ""
        timestamp = try container.decodeIfPresent(String.self, forKey: .timestampMark)
        feedbackType = try container.decodeIfPresent(String.self, forKey: .feedbackType)
            ?? ((raw?.isEmpty == false) ? "voice" : nil)
        projectTitle = try container.decodeIfPresent(String.self, forKey: .projectTitle)
        guestName = try container.decodeIfPresent(String.self, forKey: .guestName)
        // APIは is_sent を Int(0/1) で返す場合があるため、Bool と Int の両方に対応
        if let boolVal = try? container.decode(Bool.self, forKey: .isSent) {
            isSent = boolVal
        } else if let intVal = try? container.decode(Int.self, forKey: .isSent) {
            isSent = intVal != 0
        } else {
            isSent = true
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(projectId, forKey: .projectId)
        try container.encode(content, forKey: .convertedText)
        try container.encode(createdBy, forKey: .createdBy)
        try container.encode(createdAt, forKey: .createdAt)
        try container.encodeIfPresent(timestamp, forKey: .timestampMark)
        try container.encodeIfPresent(feedbackType, forKey: .category)
        try container.encodeIfPresent(projectTitle, forKey: .projectTitle)
        try container.encodeIfPresent(guestName, forKey: .guestName)
        try container.encode(isSent, forKey: .isSent)
    }
}

struct FeedbackCreateRequest: Encodable {
    let content: String
    let createdBy: String
    let timestamp: String?
    let feedbackType: String

    enum CodingKeys: String, CodingKey {
        case timestampMark
        case rawVoiceText
        case convertedText
        case category
        case priority
        case createdBy
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(timestamp, forKey: .timestampMark)
        if feedbackType == "voice" {
            try container.encode(content, forKey: .rawVoiceText)
        } else {
            try container.encode(content, forKey: .convertedText)
        }
        try container.encode(feedbackType, forKey: .category)
        try container.encode("medium", forKey: .priority)
        try container.encode(createdBy, forKey: .createdBy)
    }
}

struct DashboardSummary: Codable {
    let totalProjects: Int
    let withAssets: Int
    let avgQualityScore: Double?
    let statusCounts: [String: Int]
    let recentFeedbacks: [FeedbackItem]
    let unsentFeedbackCount: Int

    init(
        totalProjects: Int,
        withAssets: Int,
        avgQualityScore: Double?,
        statusCounts: [String: Int],
        recentFeedbacks: [FeedbackItem],
        unsentFeedbackCount: Int
    ) {
        self.totalProjects = totalProjects
        self.withAssets = withAssets
        self.avgQualityScore = avgQualityScore
        self.statusCounts = statusCounts
        self.recentFeedbacks = recentFeedbacks
        self.unsentFeedbackCount = unsentFeedbackCount
    }

    enum CodingKeys: String, CodingKey {
        case totalProjects
        case withAssets
        case projectsWithAssets
        case avgQualityScore
        case averageQualityScore
        case statusCounts
        case statusBreakdown
        case recentFeedbacks
        case unsentFeedbackCount
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        totalProjects = try container.decodeIfPresent(Int.self, forKey: .totalProjects) ?? 0
        withAssets = try container.decodeIfPresent(Int.self, forKey: .withAssets)
            ?? container.decodeIfPresent(Int.self, forKey: .projectsWithAssets)
            ?? 0
        avgQualityScore = try container.decodeIfPresent(Double.self, forKey: .avgQualityScore)
            ?? container.decodeIfPresent(Double.self, forKey: .averageQualityScore)
        statusCounts = try container.decodeIfPresent([String: Int].self, forKey: .statusCounts)
            ?? container.decodeIfPresent([String: Int].self, forKey: .statusBreakdown)
            ?? [:]
        recentFeedbacks = try container.decodeIfPresent([FeedbackItem].self, forKey: .recentFeedbacks) ?? []
        unsentFeedbackCount = try container.decodeIfPresent(Int.self, forKey: .unsentFeedbackCount) ?? 0
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(totalProjects, forKey: .totalProjects)
        try container.encode(withAssets, forKey: .withAssets)
        try container.encodeIfPresent(avgQualityScore, forKey: .avgQualityScore)
        try container.encode(statusCounts, forKey: .statusCounts)
        try container.encode(recentFeedbacks, forKey: .recentFeedbacks)
        try container.encode(unsentFeedbackCount, forKey: .unsentFeedbackCount)
    }
}

struct QualityTrendItem: Codable, Identifiable {
    var id: String { "\(guestName)-\(shootDate)" }
    let guestName: String
    let shootDate: String
    let qualityScore: Int?
}

struct Editor: Identifiable, Decodable {
    let id: String
    let name: String
    let contactInfo: String?
    let status: String
    let contractType: String?
    let skills: EditorSkills?
    let activeProjectCount: Int
    let completedCount: Int
    let avgQualityScore: Double?
    let createdAt: String

    // 通常のイニシャライザ（MockData用）
    init(
        id: String, name: String, contactInfo: String?, status: String,
        contractType: String?, skills: EditorSkills?,
        activeProjectCount: Int, completedCount: Int,
        avgQualityScore: Double?, createdAt: String
    ) {
        self.id = id; self.name = name; self.contactInfo = contactInfo
        self.status = status; self.contractType = contractType; self.skills = skills
        self.activeProjectCount = activeProjectCount; self.completedCount = completedCount
        self.avgQualityScore = avgQualityScore; self.createdAt = createdAt
    }

    enum CodingKeys: String, CodingKey {
        case id, name, contactInfo, status, contractType, skills
        case activeProjects, activeProjectCount
        case completedCount, totalCompleted
        case avgQualityScore, createdAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        contactInfo = try container.decodeIfPresent(String.self, forKey: .contactInfo)
        status = try container.decode(String.self, forKey: .status)
        contractType = try container.decodeIfPresent(String.self, forKey: .contractType)
        skills = try container.decodeIfPresent(EditorSkills.self, forKey: .skills)
        avgQualityScore = try container.decodeIfPresent(Double.self, forKey: .avgQualityScore)
        createdAt = try container.decodeIfPresent(String.self, forKey: .createdAt) ?? ""

        // activeProjects: APIは配列[]を返す場合があるのでInt/Array両対応
        if let count = try? container.decode(Int.self, forKey: .activeProjects) {
            activeProjectCount = count
        } else if let arr = try? container.decode([String].self, forKey: .activeProjects) {
            activeProjectCount = arr.count
        } else if let count = try? container.decode(Int.self, forKey: .activeProjectCount) {
            activeProjectCount = count
        } else {
            activeProjectCount = 0
        }

        // completedCount: APIキー名のバリエーション対応
        completedCount = try container.decodeIfPresent(Int.self, forKey: .completedCount)
            ?? container.decodeIfPresent(Int.self, forKey: .totalCompleted)
            ?? 0
    }
}

struct EditorSkills: Codable {
    let cutting: Double
    let color: Double
    let telop: Double
    let bgm: Double
    let cameraWork: Double
    let composition: Double
    let tempo: Double

    // 通常のイニシャライザ（MockData用）
    init(cutting: Double, color: Double, telop: Double, bgm: Double,
         cameraWork: Double, composition: Double, tempo: Double) {
        self.cutting = cutting; self.color = color; self.telop = telop
        self.bgm = bgm; self.cameraWork = cameraWork
        self.composition = composition; self.tempo = tempo
    }

    // 空オブジェクト{}の場合デフォルト0.0で初期化
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        cutting = try container.decodeIfPresent(Double.self, forKey: .cutting) ?? 0.0
        color = try container.decodeIfPresent(Double.self, forKey: .color) ?? 0.0
        telop = try container.decodeIfPresent(Double.self, forKey: .telop) ?? 0.0
        bgm = try container.decodeIfPresent(Double.self, forKey: .bgm) ?? 0.0
        cameraWork = try container.decodeIfPresent(Double.self, forKey: .cameraWork) ?? 0.0
        composition = try container.decodeIfPresent(Double.self, forKey: .composition) ?? 0.0
        tempo = try container.decodeIfPresent(Double.self, forKey: .tempo) ?? 0.0
    }
}

struct TrackedVideo: Identifiable, Codable {
    let id: String
    let url: String
    let title: String
    let channelName: String?
    let thumbnailUrl: String?
    let analysisStatus: String
    let analysisResult: VideoAnalysis?
    let createdAt: String
}

struct VideoAnalysis: Codable {
    let overallScore: Double?
    let composition: String?
    let tempo: String?
    let cuttingStyle: String?
    let colorGrading: String?
    let keyTechniques: [String]?
    let summary: String?
}

struct TrackingInsight: Identifiable, Codable {
    let id: String
    let category: String
    let pattern: String
    let sourceCount: Int
    let confidence: Double
    let createdAt: String
}

// MARK: - フレーム評価モデル

struct FrameEvaluationResponse: Codable {
    let projectId: String
    let status: String
    let evaluatedAt: String?
    let totalFrames: Int?
    let issueCount: Int?
    let reviewCount: Int?
    let averageScore: Double?
    let isStub: Bool?
    let message: String?
    let evaluations: [FrameEvaluationItem]?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        projectId = try container.decodeIfPresent(String.self, forKey: .projectId) ?? ""
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "unknown"
        evaluatedAt = try container.decodeIfPresent(String.self, forKey: .evaluatedAt)
        totalFrames = try container.decodeIfPresent(Int.self, forKey: .totalFrames)
        issueCount = try container.decodeIfPresent(Int.self, forKey: .issueCount)
        reviewCount = try container.decodeIfPresent(Int.self, forKey: .reviewCount)
        averageScore = try container.decodeIfPresent(Double.self, forKey: .averageScore)
        isStub = try container.decodeIfPresent(Bool.self, forKey: .isStub)
        message = try container.decodeIfPresent(String.self, forKey: .message)
        evaluations = try container.decodeIfPresent([FrameEvaluationItem].self, forKey: .evaluations)
    }
}

struct FrameEvaluationItem: Codable, Identifiable {
    var id: String { frame?.timestamp ?? UUID().uuidString }
    let frame: FrameInfoModel?
    let consensusScore: Double?
    let agreementLevel: String?
    let findings: [FindingModel]?
}

struct FrameInfoModel: Codable {
    let timestamp: String
    let frameIndex: Int?
    let sceneDescription: String?
    let isStub: Bool?
}

struct FindingModel: Codable, Identifiable {
    var id: String { "\(axis)-\(level)" }
    let axis: String
    let axisLabel: String
    let level: String  // "issue" / "review"
    let description: String
    let suggestion: String?
}

// MARK: - 学習サマリーモデル

struct LearningSummary: Codable {
    let feedbackLearning: LearningDetail?
    let videoLearning: LearningDetail?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        feedbackLearning = try container.decodeIfPresent(LearningDetail.self, forKey: .feedbackLearning)
        videoLearning = try container.decodeIfPresent(LearningDetail.self, forKey: .videoLearning)
    }
}

struct LearningDetail: Codable {
    let totalPatterns: Int?
    let totalRules: Int?
    let activeRules: Int?
    let highConfidencePatterns: Int?
    let categoryDistribution: [String: Int]?
    let totalSourceVideos: Int?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        totalPatterns = try container.decodeIfPresent(Int.self, forKey: .totalPatterns)
        totalRules = try container.decodeIfPresent(Int.self, forKey: .totalRules)
        activeRules = try container.decodeIfPresent(Int.self, forKey: .activeRules)
        highConfidencePatterns = try container.decodeIfPresent(Int.self, forKey: .highConfidencePatterns)
        categoryDistribution = try container.decodeIfPresent([String: Int].self, forKey: .categoryDistribution)
        totalSourceVideos = try container.decodeIfPresent(Int.self, forKey: .totalSourceVideos)
    }
}

struct AuditReport: Codable, Identifiable {
    var id: String { runAt }
    let runAt: String
    let pipelineStatus: String
    let pendingVideos: Int
    let qualityAnomalies: [String]
    let staleProjects: [String]
    let overallHealth: String
}

struct FeedbackConvertRequest: Encodable {
    let rawText: String
    let projectId: String
}

struct FeedbackConvertResponse: Codable {
    let convertedText: String
    let structuredItems: [StructuredFeedbackItem]
}

// MARK: - Vimeoレビューコメント投稿モデル

struct VimeoCommentPayload: Encodable {
    let timecode: String
    let text: String
    let priority: String
    let feedbackId: String?

    enum CodingKeys: String, CodingKey {
        case timecode
        case text
        case priority
        case feedbackId
    }
}

struct VimeoPostReviewRequest: Encodable {
    let vimeoVideoId: String
    let comments: [VimeoCommentPayload]
}

struct VimeoReviewPlanItem: Codable {
    let index: Int
    let feedbackId: String
    let timecode: String
    let timestampSeconds: Double
    let priority: String
    let vimeoPayload: [String: String]?

    // vimeoPayloadは動的キーのため柔軟にデコード
    enum CodingKeys: String, CodingKey {
        case index
        case feedbackId
        case timecode
        case timestampSeconds
        case priority
        case vimeoPayload
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        index = try container.decode(Int.self, forKey: .index)
        feedbackId = try container.decode(String.self, forKey: .feedbackId)
        timecode = try container.decode(String.self, forKey: .timecode)
        timestampSeconds = try container.decode(Double.self, forKey: .timestampSeconds)
        priority = try container.decode(String.self, forKey: .priority)
        // vimeoPayloadはString値のみ想定。デコード失敗時はnilにフォールバック
        vimeoPayload = try? container.decodeIfPresent([String: String].self, forKey: .vimeoPayload)
    }
}

struct VimeoPostReviewResponse: Codable {
    let mode: String
    let targetVideoId: String
    let commentCount: Int?
    let plan: [VimeoReviewPlanItem]?
    let summary: VimeoPostSummary?

    struct VimeoPostSummary: Codable {
        let total: Int
        let posted: Int?
        let failed: Int?
    }
}

enum JSONValue: Codable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case array([JSONValue])
    case object([String: JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let string = try? container.decode(String.self) {
            self = .string(string)
        } else if let number = try? container.decode(Double.self) {
            self = .number(number)
        } else if let bool = try? container.decode(Bool.self) {
            self = .bool(bool)
        } else if let array = try? container.decode([JSONValue].self) {
            self = .array(array)
        } else if let object = try? container.decode([String: JSONValue].self) {
            self = .object(object)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }

    var stringValue: String? {
        switch self {
        case .string(let value): return value
        case .number(let value): return String(value)
        case .bool(let value): return String(value)
        default: return nil
        }
    }

    var arrayValue: [JSONValue]? {
        if case .array(let value) = self { return value }
        return nil
    }

    var objectValue: [String: JSONValue]? {
        if case .object(let value) = self { return value }
        return nil
    }
}

// MARK: - 品質ダッシュボード統計モデル（P2: 実データ連動）

/// グレード分布1件（グレードラベル + 件数）
struct GradeDistEntry: Identifiable {
    let id = UUID()
    let grade: String
    let count: Int

    /// グレードに対応するAppTheme準拠カラー
    var color: Color {
        switch grade {
        case "A+", "A": return AppTheme.statusComplete
        case "B+", "B": return Color(hex: 0x4A90D9)
        case "C": return Color(hex: 0xF5A623)
        default: return AppTheme.accent
        }
    }
}

/// `/api/v1/dashboard/quality` レスポンス
struct QualityStats: Codable {
    let totalScored: Int
    let totalUnscored: Int
    let averageScore: Double?
    let gradeDistribution: [String: Int]
    let recentTrend: [QualityTrendItem]
    let improvementDelta: Double?

    /// gradeDistribution をUIに使いやすい順序付き配列に変換
    var sortedGradeEntries: [GradeDistEntry] {
        let order = ["A+", "A", "B+", "B", "C", "D", "E"]
        return order.map { GradeDistEntry(grade: $0, count: gradeDistribution[$0] ?? 0) }
    }

    /// 改善傾向ラベル（+/-付き文字列）
    var deltaLabel: String {
        guard let d = improvementDelta else { return "-" }
        return d >= 0 ? String(format: "+%.1f", d) : String(format: "%.1f", d)
    }
}

// MARK: - 編集後フィードバックモデル（P1: Before/After差分）

/// APIリクエストボディ（編集済み動画のメタデータ）
struct EditFeedbackRequestBody: Encodable {
    let durationSeconds: Int
    let originalDurationSeconds: Int
    let includedTimestamps: [String]
    let excludedTimestamps: [String]
    let telopTexts: [String]
    let sceneOrder: [String]
    let editorName: String
    let stage: String

    init(
        durationSeconds: Int = 0,
        originalDurationSeconds: Int = 0,
        includedTimestamps: [String] = [],
        excludedTimestamps: [String] = [],
        telopTexts: [String] = [],
        sceneOrder: [String] = [],
        editorName: String = "",
        stage: String = "draft"
    ) {
        self.durationSeconds = durationSeconds
        self.originalDurationSeconds = originalDurationSeconds
        self.includedTimestamps = includedTimestamps
        self.excludedTimestamps = excludedTimestamps
        self.telopTexts = telopTexts
        self.sceneOrder = sceneOrder
        self.editorName = editorName
        self.stage = stage
    }
}

/// コンテンツフィードバック1件
struct ContentFeedbackEntry: Identifiable, Decodable {
    var id: String { "\(area)_\(category)" }
    let category: String   // "positive" / "improvement" / "critical"
    let area: String
    let message: String
    let severity: String   // "high" / "medium" / "low"

    enum CodingKeys: String, CodingKey {
        case category, area, message, severity
    }

    /// severity に応じたAppTheme準拠カラー
    var severityColor: Color {
        switch severity {
        case "high": return AppTheme.accent
        case "medium": return Color(hex: 0xF5A623)
        default: return Color(hex: 0x4A90D9)
        }
    }

    /// category に応じた表示色
    var categoryColor: Color {
        switch category {
        case "positive": return AppTheme.statusComplete
        case "critical": return AppTheme.accent
        default: return Color(hex: 0xF5A623)
        }
    }

    /// category に応じた日本語ラベル
    var categoryLabel: String {
        switch category {
        case "positive": return "良好"
        case "critical": return "要改善"
        default: return "改善推奨"
        }
    }
}

/// テロップチェックサマリー
struct TelopCheckSummary: Decodable {
    let errorCount: Int
    let warningCount: Int
    let note: String
}

/// ハイライトチェックサマリー
struct HighlightCheckSummary: Decodable {
    let total: Int
    let included: Int
    let excluded: Int
    let inclusionRate: Double
    let keyExcluded: [String]
    let comment: String

    var inclusionPercent: String {
        "\(Int(inclusionRate * 100))%"
    }
}

/// ディレクション準拠度サマリー
struct DirectionAdherenceSummary: Decodable {
    let total: Int
    let followed: Int
    let partial: Int
    let notFollowed: Int
    let adherenceRate: Double
    let note: String?

    var adherencePercent: String {
        "\(Int(adherenceRate * 100))%"
    }
}

/// 編集後フィードバックAPIレスポンス全体
struct EditFeedbackResponse: Decodable {
    let projectId: String
    let qualityScore: Double
    let grade: String
    let contentFeedback: [ContentFeedbackEntry]
    let telopCheck: TelopCheckSummary
    let highlightCheck: HighlightCheckSummary
    let directionAdherence: DirectionAdherenceSummary
    let summary: String
    let editorName: String
    let stage: String
    let generatedAt: String

    /// グレードに対応するAppTheme準拠カラー
    var gradeColor: Color {
        switch grade {
        case "A+", "A": return AppTheme.statusComplete
        case "B+", "B": return Color(hex: 0x4A90D9)
        case "C": return Color(hex: 0xF5A623)
        default: return AppTheme.accent
        }
    }

    /// 0-10スコアを0-1の進捗値に変換（ゲージ表示用）
    var scoreProgress: Double {
        min(max(qualityScore / 10.0, 0.0), 1.0)
    }
}

// MARK: - Vimeoタイムライン関連モデル

struct VimeoFeedbackItem: Identifiable, Codable {
    let id: UUID
    /// タイムコード（秒単位）
    let timestampMark: TimeInterval
    /// 映像要素カテゴリ（カット割り・テロップ等）
    let element: String
    /// 優先度
    let priorityRaw: String
    /// フィードバック本文
    let note: String
    /// Vimeo動画ID
    let vimeoVideoId: String

    var priority: FeedbackPriority {
        FeedbackPriority(rawValue: priorityRaw) ?? .medium
    }

    /// タイムコードを MM:SS 文字列で返す
    var timestampString: String {
        let minutes = Int(timestampMark) / 60
        let seconds = Int(timestampMark) % 60
        return String(format: "%02d:%02d", minutes, seconds)
    }

    enum CodingKeys: String, CodingKey {
        case id
        case timestampMark = "timestamp_mark"
        case element
        case priorityRaw = "priority"
        case note
        case vimeoVideoId = "vimeo_video_id"
    }
}

/// Vimeoプレイヤーの再生状態（ViewModelと共有）
enum VimeoPlaybackState {
    case idle
    case playing
    case paused
    case error(String)
}

// MARK: - E2Eパイプラインモデル

/// E2Eパイプライン実行リクエスト
struct E2EPipelineRequestBody: Encodable {
    let vimeoVideoId: String?
    let dryRun: Bool
    let useLlm: Bool

    init(vimeoVideoId: String? = nil, dryRun: Bool = true, useLlm: Bool = true) {
        self.vimeoVideoId = vimeoVideoId
        self.dryRun = dryRun
        self.useLlm = useLlm
    }
}

/// E2Eパイプライン各ステップの状態
struct E2EPipelineStepStatus: Codable {
    let status: String
    let feedbackCount: Int?
    let projectTitle: String?
    let guestName: String?
    let insights: [String: JSONValue]?
    let error: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "unknown"
        feedbackCount = try container.decodeIfPresent(Int.self, forKey: .feedbackCount)
        projectTitle = try container.decodeIfPresent(String.self, forKey: .projectTitle)
        guestName = try container.decodeIfPresent(String.self, forKey: .guestName)
        insights = try container.decodeIfPresent([String: JSONValue].self, forKey: .insights)
        error = try container.decodeIfPresent(String.self, forKey: .error)
    }
}

/// E2Eパイプラインのディレクションエントリ
struct E2EDirectionEntry: Identifiable, Codable {
    var id: String { "\(timestamp)_\(element)" }
    let timestamp: String
    let element: String
    let instruction: String
    let priority: String
    let reasoning: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        timestamp = try container.decodeIfPresent(String.self, forKey: .timestamp) ?? ""
        element = try container.decodeIfPresent(String.self, forKey: .element) ?? ""
        instruction = try container.decodeIfPresent(String.self, forKey: .instruction) ?? ""
        priority = try container.decodeIfPresent(String.self, forKey: .priority) ?? "medium"
        reasoning = try container.decodeIfPresent(String.self, forKey: .reasoning)
    }

    /// 優先度カラー
    var priorityColor: Color {
        switch priority.lowercased() {
        case "high": return AppTheme.accent
        case "medium": return Color(hex: 0xF5A623)
        default: return Color(hex: 0x4A90D9)
        }
    }
}

/// E2Eパイプラインレスポンス
struct E2EPipelineResponse: Codable {
    let projectId: String
    let status: String
    let steps: [String: E2EPipelineStepStatus]?
    let directionEntries: [E2EDirectionEntry]?
    let errors: [String]?
    let vimeoResult: VimeoPostReviewResponse?
    let generatedAt: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        projectId = try container.decodeIfPresent(String.self, forKey: .projectId) ?? ""
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "unknown"
        steps = try container.decodeIfPresent([String: E2EPipelineStepStatus].self, forKey: .steps)
        directionEntries = try container.decodeIfPresent([E2EDirectionEntry].self, forKey: .directionEntries)
        errors = try container.decodeIfPresent([String].self, forKey: .errors)
        vimeoResult = try container.decodeIfPresent(VimeoPostReviewResponse.self, forKey: .vimeoResult)
        generatedAt = try container.decodeIfPresent(String.self, forKey: .generatedAt)
    }
}

// MARK: - テロップチェックモデル

/// テロップチェック実行リクエスト
struct TelopCheckRequestBody: Encodable {
    let videoPath: String?
    let useOcr: Bool
    let numSamples: Int

    init(videoPath: String? = nil, useOcr: Bool = true, numSamples: Int = 10) {
        self.videoPath = videoPath
        self.useOcr = useOcr
        self.numSamples = numSamples
    }
}

/// テロップチェック問題1件
struct TelopIssue: Identifiable, Codable {
    var id: String { "\(type)_\(description.prefix(30))" }
    let type: String           // "spelling" / "consistency" / "timing"
    let severity: String       // "error" / "warning" / "info"
    let description: String
    let location: String?
    let suggestion: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decodeIfPresent(String.self, forKey: .type) ?? "unknown"
        severity = try container.decodeIfPresent(String.self, forKey: .severity) ?? "info"
        description = try container.decodeIfPresent(String.self, forKey: .description) ?? ""
        location = try container.decodeIfPresent(String.self, forKey: .location)
        suggestion = try container.decodeIfPresent(String.self, forKey: .suggestion)
    }

    /// severity に応じたAppTheme準拠カラー
    var severityColor: Color {
        switch severity.lowercased() {
        case "error": return AppTheme.accent
        case "warning": return Color(hex: 0xF5A623)
        default: return Color(hex: 0x4A90D9)
        }
    }

    /// severity に応じたSFSymbol
    var severityIcon: String {
        switch severity.lowercased() {
        case "error": return "xmark.circle.fill"
        case "warning": return "exclamationmark.triangle.fill"
        default: return "info.circle.fill"
        }
    }
}

/// フレームベーステロップチェック結果
struct TelopFrameCheckResult: Codable {
    let totalFramesChecked: Int
    let totalTelopsFound: Int
    let extractionMethod: String?
    let spellingIssues: [TelopIssue]?
    let consistencyIssues: [TelopIssue]?
    let timingIssues: [TelopIssue]?
    let errorCount: Int
    let warningCount: Int
    let overallScore: Double?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        totalFramesChecked = try container.decodeIfPresent(Int.self, forKey: .totalFramesChecked) ?? 0
        totalTelopsFound = try container.decodeIfPresent(Int.self, forKey: .totalTelopsFound) ?? 0
        extractionMethod = try container.decodeIfPresent(String.self, forKey: .extractionMethod)
        spellingIssues = try container.decodeIfPresent([TelopIssue].self, forKey: .spellingIssues)
        consistencyIssues = try container.decodeIfPresent([TelopIssue].self, forKey: .consistencyIssues)
        timingIssues = try container.decodeIfPresent([TelopIssue].self, forKey: .timingIssues)
        errorCount = try container.decodeIfPresent(Int.self, forKey: .errorCount) ?? 0
        warningCount = try container.decodeIfPresent(Int.self, forKey: .warningCount) ?? 0
        overallScore = try container.decodeIfPresent(Double.self, forKey: .overallScore)
    }

    /// 全問題を統合して返す
    var allIssues: [TelopIssue] {
        (spellingIssues ?? []) + (consistencyIssues ?? []) + (timingIssues ?? [])
    }
}

/// テロップチェックレスポンス
struct TelopCheckResponse: Codable {
    let projectId: String
    let status: String
    let checkedAt: String?
    let frameCheck: TelopFrameCheckResult?
    let message: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        projectId = try container.decodeIfPresent(String.self, forKey: .projectId) ?? ""
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "unknown"
        checkedAt = try container.decodeIfPresent(String.self, forKey: .checkedAt)
        frameCheck = try container.decodeIfPresent(TelopFrameCheckResult.self, forKey: .frameCheck)
        message = try container.decodeIfPresent(String.self, forKey: .message)
    }
}

// MARK: - 音声品質評価モデル

/// 音声品質評価の軸別スコア
struct AudioAxisScore: Identifiable, Codable {
    var id: String { axis }
    let axis: String
    let axisLabel: String?
    let score: Double
    let grade: String?
    let description: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        axis = try container.decodeIfPresent(String.self, forKey: .axis) ?? ""
        axisLabel = try container.decodeIfPresent(String.self, forKey: .axisLabel)
        score = try container.decodeIfPresent(Double.self, forKey: .score) ?? 0
        grade = try container.decodeIfPresent(String.self, forKey: .grade)
        description = try container.decodeIfPresent(String.self, forKey: .description)
    }

    /// 表示用ラベル
    var displayLabel: String {
        axisLabel ?? axis
    }

    /// スコアに応じたAppTheme準拠カラー
    var scoreColor: Color {
        if score >= 85 { return AppTheme.statusComplete }
        if score >= 70 { return Color(hex: 0xF5A623) }
        return AppTheme.accent
    }
}

/// 音声品質問題1件
struct AudioIssue: Identifiable, Codable {
    var id: String { "\(axis)_\(description.prefix(30))" }
    let axis: String
    let severity: String
    let description: String
    let suggestion: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        axis = try container.decodeIfPresent(String.self, forKey: .axis) ?? ""
        severity = try container.decodeIfPresent(String.self, forKey: .severity) ?? "info"
        description = try container.decodeIfPresent(String.self, forKey: .description) ?? ""
        suggestion = try container.decodeIfPresent(String.self, forKey: .suggestion)
    }

    /// severity に応じたカラー
    var severityColor: Color {
        switch severity.lowercased() {
        case "error", "high": return AppTheme.accent
        case "warning", "medium": return Color(hex: 0xF5A623)
        default: return Color(hex: 0x4A90D9)
        }
    }
}

/// 音声品質評価レスポンス
struct AudioEvaluationResponse: Codable {
    let projectId: String
    let status: String
    let evaluatedAt: String?
    let overallScore: Double
    let grade: String
    let analysisMethod: String?
    let isEstimated: Bool?
    let axisScores: [AudioAxisScore]?
    let issues: [AudioIssue]?
    let errorCount: Int?
    let warningCount: Int?
    let message: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        projectId = try container.decodeIfPresent(String.self, forKey: .projectId) ?? ""
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "unknown"
        evaluatedAt = try container.decodeIfPresent(String.self, forKey: .evaluatedAt)
        overallScore = try container.decodeIfPresent(Double.self, forKey: .overallScore) ?? 0
        grade = try container.decodeIfPresent(String.self, forKey: .grade) ?? "D"
        analysisMethod = try container.decodeIfPresent(String.self, forKey: .analysisMethod)
        isEstimated = try container.decodeIfPresent(Bool.self, forKey: .isEstimated)
        axisScores = try container.decodeIfPresent([AudioAxisScore].self, forKey: .axisScores)
        issues = try container.decodeIfPresent([AudioIssue].self, forKey: .issues)
        errorCount = try container.decodeIfPresent(Int.self, forKey: .errorCount)
        warningCount = try container.decodeIfPresent(Int.self, forKey: .warningCount)
        message = try container.decodeIfPresent(String.self, forKey: .message)
    }

    /// グレードカラー
    var gradeColor: Color {
        switch grade {
        case "A+", "A": return AppTheme.statusComplete
        case "B+", "B": return Color(hex: 0x4A90D9)
        case "C": return Color(hex: 0xF5A623)
        default: return AppTheme.accent
        }
    }
}

// MARK: - ナレッジページモデル

/// ナレッジページ概要（一覧表示用）
struct KnowledgePage: Identifiable, Codable {
    var id: String { pageId }
    let pageId: String
    let title: String
    let guestName: String?
    let shootDate: String?
    let createdAt: String?
    let url: String?
    let summary: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        pageId = try container.decodeIfPresent(String.self, forKey: .pageId) ?? UUID().uuidString
        title = try container.decodeIfPresent(String.self, forKey: .title) ?? ""
        guestName = try container.decodeIfPresent(String.self, forKey: .guestName)
        shootDate = try container.decodeIfPresent(String.self, forKey: .shootDate)
        createdAt = try container.decodeIfPresent(String.self, forKey: .createdAt)
        url = try container.decodeIfPresent(String.self, forKey: .url)
        summary = try container.decodeIfPresent(String.self, forKey: .summary)
    }
}

/// ナレッジページ一覧レスポンス
struct KnowledgePagesResponse: Codable {
    let total: Int
    let offset: Int
    let pages: [KnowledgePage]

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        total = try container.decodeIfPresent(Int.self, forKey: .total) ?? 0
        offset = try container.decodeIfPresent(Int.self, forKey: .offset) ?? 0
        pages = try container.decodeIfPresent([KnowledgePage].self, forKey: .pages) ?? []
    }
}

/// ナレッジ検索結果1件
struct KnowledgeSearchResult: Identifiable, Codable {
    var id: String { pageId }
    let pageId: String
    let title: String
    let guestName: String?
    let matchSnippet: String?
    let score: Double?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        pageId = try container.decodeIfPresent(String.self, forKey: .pageId) ?? UUID().uuidString
        title = try container.decodeIfPresent(String.self, forKey: .title) ?? ""
        guestName = try container.decodeIfPresent(String.self, forKey: .guestName)
        matchSnippet = try container.decodeIfPresent(String.self, forKey: .matchSnippet)
        score = try container.decodeIfPresent(Double.self, forKey: .score)
    }
}

/// ナレッジ検索レスポンス
struct KnowledgeSearchResponse: Codable {
    let query: String
    let total: Int
    let results: [KnowledgeSearchResult]

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        query = try container.decodeIfPresent(String.self, forKey: .query) ?? ""
        total = try container.decodeIfPresent(Int.self, forKey: .total) ?? 0
        results = try container.decodeIfPresent([KnowledgeSearchResult].self, forKey: .results) ?? []
    }
}

/// ナレッジページ詳細レスポンス
struct KnowledgePageDetail: Codable {
    let pageId: String
    let title: String
    let htmlContent: String?
    let url: String?
    let guestName: String?
    let format: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        pageId = try container.decodeIfPresent(String.self, forKey: .pageId) ?? ""
        title = try container.decodeIfPresent(String.self, forKey: .title) ?? ""
        htmlContent = try container.decodeIfPresent(String.self, forKey: .htmlContent)
        url = try container.decodeIfPresent(String.self, forKey: .url)
        guestName = try container.decodeIfPresent(String.self, forKey: .guestName)
        format = try container.decodeIfPresent(String.self, forKey: .format)
    }
}

// MARK: - ビフォーアフター比較モデル

/// 素材動画（YouTube）の情報
struct BeforeAfterSourceVideo: Codable, Identifiable {
    var id: String { videoId }
    let youtubeUrl: String
    let videoId: String
    let title: String?
    let duration: String?
    let embedUrl: String
}

/// 編集後動画（Vimeo）の情報
struct BeforeAfterEditedVideo: Codable {
    let vimeoUrl: String
    let vimeoId: String
    let embedUrl: String?
    let version: String?
}

/// FBハイライト（タイムスタンプ付き差分）
struct DiffHighlight: Codable, Identifiable {
    var id: String { "\(timestamp)_\(text.prefix(20))" }
    let timestamp: String
    let category: String?
    let text: String
    let priority: String?
}

/// ビフォーアフターAPIレスポンス
struct BeforeAfterResponse: Codable {
    let projectId: String
    let guestName: String
    let title: String
    let sourceVideos: [BeforeAfterSourceVideo]
    let editedVideo: BeforeAfterEditedVideo?
    let fbRevisedVideo: BeforeAfterEditedVideo?
    let diffHighlights: [DiffHighlight]
}

// MARK: - 文字起こしdiff可視化モデル

/// 文字起こしセグメント（1行分）
struct TranscriptSegment: Codable, Identifiable {
    var id: Int { lineNumber }
    let lineNumber: Int
    let text: String
    let status: String        // "unused" / "highlight" / "punchline"
    let matchedFeedback: String?

    /// ステータスに応じた色
    var statusColor: Color {
        switch status {
        case "punchline":
            return Color(hex: 0xFFD700)   // 金色
        case "highlight":
            return AppTheme.accent         // Netflix赤
        default:
            return AppTheme.textMuted.opacity(0.4) // グレー半透明
        }
    }

    /// ステータスの表示ラベル
    var statusLabel: String {
        switch status {
        case "punchline": return "パンチライン"
        case "highlight": return "ハイライト"
        default: return "未使用"
        }
    }
}

/// 文字起こしdiffレスポンス
struct TranscriptDiffResponse: Codable {
    let projectId: String
    let status: String
    let totalSegments: Int?
    let usedCount: Int?
    let highlightCount: Int?
    let punchlineCount: Int?
    let unusedCount: Int?
    let segments: [TranscriptSegment]
    let message: String?

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        projectId = try container.decodeIfPresent(String.self, forKey: .projectId) ?? ""
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "unknown"
        totalSegments = try container.decodeIfPresent(Int.self, forKey: .totalSegments)
        usedCount = try container.decodeIfPresent(Int.self, forKey: .usedCount)
        highlightCount = try container.decodeIfPresent(Int.self, forKey: .highlightCount)
        punchlineCount = try container.decodeIfPresent(Int.self, forKey: .punchlineCount)
        unusedCount = try container.decodeIfPresent(Int.self, forKey: .unusedCount)
        segments = try container.decodeIfPresent([TranscriptSegment].self, forKey: .segments) ?? []
        message = try container.decodeIfPresent(String.self, forKey: .message)
    }
}
