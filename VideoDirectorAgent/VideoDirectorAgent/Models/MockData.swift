import Foundation

enum MockData {
    static let projects: [VideoProject] = [
        .init(id: UUID(), title: "CEO対談 Vol.12", thumbnailSymbol: "video.fill", status: .reviewPending, unreviewedCount: 3),
        .init(id: UUID(), title: "採用密着ドキュメント", thumbnailSymbol: "person.2.fill", status: .editing, unreviewedCount: 1),
        .init(id: UUID(), title: "ブランドムービー 2026", thumbnailSymbol: "sparkles.tv.fill", status: .directed, unreviewedCount: 0),
        .init(id: UUID(), title: "イベントダイジェスト", thumbnailSymbol: "film.stack.fill", status: .published, unreviewedCount: 0)
    ]

    static let reportSections: [ReportSection] = [
        .init(
            id: UUID(),
            title: "ゲスト分類",
            items: [
                "層b（実務志向）: 成果の再現性を重視",
                "刺さる訴求: プロセスと判断基準を明示"
            ]
        ),
        .init(
            id: UUID(),
            title: "年収演出判断",
            items: [
                "年収ワードは補助的に使用。主軸は意思決定スピード",
                "金額より『改善幅』を見せる方が信頼形成に有効"
            ]
        ),
        .init(
            id: UUID(),
            title: "カットポイント提案",
            items: [
                "00:12-00:26: 冒頭フックを強化（結論先出し）",
                "02:18-02:34: テロップ情報量を50%削減",
                "05:01-05:16: Bロール差し替えでテンポ改善"
            ]
        )
    ]

    static let timelineMarkers: [TimelineMarker] = [
        .init(id: UUID(), time: 12, label: "導入"),
        .init(id: UUID(), time: 138, label: "訴求ズレ"),
        .init(id: UUID(), time: 301, label: "BGM過多")
    ]

    static let historyItems: [FeedbackHistoryItem] = [
        .init(
            id: UUID(),
            projectTitle: "CEO対談 Vol.12",
            timestamp: "02:18",
            rawVoiceText: "ここマジで伝わりづらい。テロップ多すぎる。",
            convertedText: "02:18付近のテロップ情報量を減らし、1カット1メッセージに整理してください。",
            editorStatus: "対応済み",
            learningEffect: "次案件で平均テロップ文字数が18%改善"
        ),
        .init(
            id: UUID(),
            projectTitle: "採用密着ドキュメント",
            timestamp: "00:44",
            rawVoiceText: "BGMが前に出すぎて声が弱い。",
            convertedText: "00:44-01:05のBGMレベルを-3dB調整し、ナレーション明瞭度を優先してください。",
            editorStatus: "確認中",
            learningEffect: "同編集者の音声明瞭度スコア +7"
        )
    ]

    static let qualityTrend: [QualityTrendPoint] = [
        .init(id: UUID(), label: "v1", score: 68),
        .init(id: UUID(), label: "v2", score: 74),
        .init(id: UUID(), label: "v3", score: 81),
        .init(id: UUID(), label: "v4", score: 86)
    ]

    static let editorSkills: [EditorSkill] = [
        .init(id: UUID(), editorName: "Editor A", strengths: ["カットテンポ", "構図"], weakPoints: ["BGM設計"], growth: 12),
        .init(id: UUID(), editorName: "Editor B", strengths: ["テロップ", "色補正"], weakPoints: ["導入フック"], growth: 8)
    ]

    static let alerts: [QualityAlert] = [
        .init(id: UUID(), level: "High", message: "最新2本で音声明瞭度が基準値を下回りました"),
        .init(id: UUID(), level: "Medium", message: "レビュー待ち案件が3件滞留中です")
    ]

    // --- YouTube素材モックデータ ---
    static let youtubeAssets = YouTubeAssets(
        thumbnailZones: ThumbnailZones(
            topLeft: "大きなテキスト: ゲスト名 + 肩書き",
            topRight: "インパクト数字（例: 年収3,000万）",
            bottomLeft: "TEKO ロゴ + 番組名",
            bottomRight: "表情サムネイル（驚き・熱量系）"
        ),
        titleCandidates: [
            "【年収3,000万の実態】CEO直撃インタビュー｜TEKO対談",
            "成功者が語る「失敗の乗り越え方」後悔ゼロの意思決定術",
            "たった3年で資産10倍！経営者が明かす再現可能な戦略",
            "【本音対談】一流経営者がこっそり実践するお金の増やし方",
            "年収を3倍にした思考習慣｜TEKO経営者対談Vol.12"
        ],
        description: """
        今回のゲストはXX株式会社CEO・○○氏。
        独立から3年で年収3,000万を達成した具体的なプロセスを余すことなく語っていただきました。
        再現可能な意思決定フレームワーク、失敗を資産に変える思考法、今すぐ始めるべき習慣とは？

        ▼タイムスタンプ
        00:00 オープニング
        02:15 独立前の葛藤
        08:40 年収が爆増したターニングポイント
        15:22 TEKO流マネーマインドセット
        22:10 視聴者へのメッセージ

        ▼チャンネル登録はこちら
        https://www.youtube.com/@teko
        """
    )

    // --- before/after 品質スコア比較モックデータ ---
    static let qualityScoreComparisons: [QualityScoreComparison] = [
        .init(id: UUID(), element: "カット割り", beforeScore: 62, afterScore: 78),
        .init(id: UUID(), element: "テロップ",   beforeScore: 58, afterScore: 75),
        .init(id: UUID(), element: "BGM",        beforeScore: 71, afterScore: 80),
        .init(id: UUID(), element: "カメラワーク", beforeScore: 65, afterScore: 72),
        .init(id: UUID(), element: "構図",        beforeScore: 70, afterScore: 77),
        .init(id: UUID(), element: "色彩",        beforeScore: 68, afterScore: 74),
        .init(id: UUID(), element: "テンポ",      beforeScore: 60, afterScore: 79)
    ]
}
