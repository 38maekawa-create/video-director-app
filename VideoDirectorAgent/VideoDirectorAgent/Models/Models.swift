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
        knowledge: String? = nil
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

        if let status = try container.decodeIfPresent(ProjectStatus.self, forKey: .status) {
            self.status = status
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
        if let direct = try? container.decodeIfPresent(String.self, forKey: key), !direct.isEmpty {
            return direct
        }
        if let payload = try? container.decodeIfPresent([String: JSONValue].self, forKey: fallbackKey) {
            for candidateKey in ["url", "vimeoUrl", "videoUrl", "link"] {
                if let value = payload[candidateKey]?.stringValue, !value.isEmpty {
                    return value
                }
            }
        }
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
