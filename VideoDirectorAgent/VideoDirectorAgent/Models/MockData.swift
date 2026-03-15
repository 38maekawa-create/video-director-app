import Foundation

enum MockData {
    // MARK: - プロジェクト一覧（撮影日の新しい順）
    static let projects: [VideoProject] = [
        .init(
            id: "p-satoimo-thomas", guestName: "さといも・トーマス", title: "CEO対談 Vol.12",
            thumbnailSymbol: "video.fill", shootDate: "2026/03/08",
            guestAge: 34, guestOccupation: "不動産投資家",
            status: .reviewPending, unreviewedCount: 3, qualityScore: 78,
            hasUnsentFeedback: true,
            directionReportURL: "https://example.com/report/satoimo",
            sourceVideoURL: "https://vimeo.com/100000001",
            editedVideoURL: "https://vimeo.com/1145126331",
            knowledge: "02:18 テロップ情報量が多い\n05:01 Bロールのテンポ改善余地あり"
        ),
        .init(
            id: "p-menichi", guestName: "メンイチ", title: "採用密着ドキュメント",
            thumbnailSymbol: "person.2.fill", shootDate: "2026/03/05",
            guestAge: 29, guestOccupation: "Webマーケター",
            status: .editing, unreviewedCount: 1, qualityScore: 82,
            hasUnsentFeedback: true,
            directionReportURL: "https://example.com/report/menichi",
            sourceVideoURL: "https://vimeo.com/100000003",
            editedVideoURL: nil,
            knowledge: "00:44 BGMとナレーションの帯域整理が必要"
        ),
        .init(
            id: "p-kee", guestName: "けー", title: "ブランドムービー 2026",
            thumbnailSymbol: "sparkles.tv.fill", shootDate: "2026/03/01",
            guestAge: 31, guestOccupation: "コンサルタント",
            status: .directed, unreviewedCount: 0, qualityScore: 91,
            hasUnsentFeedback: false,
            directionReportURL: nil,
            sourceVideoURL: nil,
            editedVideoURL: nil,
            knowledge: nil
        ),
        .init(
            id: "p-hirai", guestName: "hirai", title: "イベントダイジェスト",
            thumbnailSymbol: "film.stack.fill", shootDate: "2026/02/28",
            guestAge: 27, guestOccupation: "映像クリエイター",
            status: .published, unreviewedCount: 0, qualityScore: 88,
            hasUnsentFeedback: false,
            directionReportURL: nil,
            sourceVideoURL: nil,
            editedVideoURL: "https://vimeo.com/1145126331",
            knowledge: "全体テンポ良好"
        ),
        .init(
            id: "p-kote", guestName: "コテ", title: "不動産投資入門シリーズ #3",
            thumbnailSymbol: "building.2.fill", shootDate: "2026/02/25",
            guestAge: 38, guestOccupation: "不動産オーナー",
            status: .published, unreviewedCount: 0, qualityScore: 85,
            hasUnsentFeedback: false,
            directionReportURL: nil,
            sourceVideoURL: "https://vimeo.com/100000005",
            editedVideoURL: "https://vimeo.com/1145126331",
            knowledge: "実績数字の見せ方が強い"
        )
    ]

    static let sampleYouTubeAssets = YouTubeAssets(
        projectId: "p-izu",
        thumbnailDesign: ThumbnailDesign(
            overallConcept: "元アクセンチュアの会社員が不動産投資で意思決定を変えた流れを、Z型4ゾーンで一瞬で伝える",
            fontSuggestion: "太めのゴシック体。数字は縦詰めで視認性重視",
            backgroundSuggestion: "暗めネイビー背景に赤とゴールドでアクセント",
            zones: [
                ThumbnailZone(
                    role: "フック",
                    content: "元アクセンチュアが不動産投資で何を変えたか",
                    colorSuggestion: "赤",
                    notes: "左上で最も大きく、2行以内に圧縮"
                ),
                ThumbnailZone(
                    role: "人物+属性",
                    content: "30代中盤 / 元アクセンチュア / 会社員",
                    colorSuggestion: "白",
                    notes: "人物シルエット横に属性を短く置く"
                ),
                ThumbnailZone(
                    role: "コンテンツ要素",
                    content: "意思決定 / 行動変化 / 投資判断の実例",
                    colorSuggestion: "ゴールド",
                    notes: "視線が左上から右下へ流れる斜め配置"
                ),
                ThumbnailZone(
                    role: "ベネフィット",
                    content: "再現できる判断軸がわかる",
                    colorSuggestion: "黄色",
                    notes: "右下にCTA的に配置"
                )
            ]
        ),
        titleProposals: TitleProposals(
            candidates: [
                TitleCandidate(
                    title: "元アクセンチュア会社員が不動産投資で手にした判断軸",
                    targetSegment: "会社員投資初心者",
                    appealType: "権威系",
                    rationale: "属性の強さと学びを両立"
                ),
                TitleCandidate(
                    title: "30代会社員が不動産投資で変えた意思決定のリアル",
                    targetSegment: "再現性重視の視聴者",
                    appealType: "ストーリー系",
                    rationale: "変化のプロセスを見せやすい"
                ),
                TitleCandidate(
                    title: "なぜ元アクセンチュアは不動産投資を選んだのか？",
                    targetSegment: "比較検討層",
                    appealType: "問いかけ系",
                    rationale: "クリック動機が明確"
                )
            ],
            recommendedIndex: 0
        ),
        descriptionOriginal: """
元アクセンチュアの30代中盤会社員ゲストが、不動産投資を通じてどう意思決定を変えたのかを深掘りした対談です。

▼ 今回のトーク内容
・会社員時代の判断軸
・不動産投資を始めた背景
・行動が変わった具体ポイント

▼ タイムスタンプ
0:00 オープニング
1:14 投資を始めた理由
4:32 判断軸が変わった瞬間
7:20 今後の展望

▼ TEKO（テコ）について詳しくはこちら
https://teko-lp.com/

#不動産投資 #資産形成 #会社員投資
""",
        descriptionEdited: nil,
        descriptionFinalizedAt: nil,
        descriptionFinalizedBy: nil,
        selectedTitleIndex: 0,
        editedTitle: nil,
        lastEditedBy: "なおとさん",
        generatedAt: "2026-03-12T12:00:00Z",
        updatedAt: "2026-03-12T12:00:00Z"
    )

    // MARK: - ディレクションレポートセクション
    static let reportSections: [ReportSection] = [
        .init(
            id: UUID(),
            title: "演出ディレクション",
            icon: "theatermasks.fill",
            items: [
                "層b（実務志向）: 成果の再現性を重視",
                "刺さる訴求: プロセスと判断基準を明示",
                "冒頭15秒で「自分ごと化」できるフックを入れる"
            ]
        ),
        .init(
            id: UUID(),
            title: "テロップ指示",
            icon: "textformat.size",
            items: [
                "年収ワードは補助的に使用。主軸は意思決定スピード",
                "金額より『改善幅』を見せる方が信頼形成に有効",
                "1カット1メッセージ厳守。情報過多にしない"
            ]
        ),
        .init(
            id: UUID(),
            title: "カメラワーク",
            icon: "camera.fill",
            items: [
                "00:12-00:26: 冒頭フックを強化（結論先出し）",
                "02:18-02:34: Bロール差し替えでテンポ改善",
                "05:01-05:16: ゲストの表情を寄りで捉える"
            ]
        ),
        .init(
            id: UUID(),
            title: "音声FB履歴",
            icon: "mic.fill",
            items: [
                "「テロップ多すぎ」→ 1カット1メッセージに整理",
                "「BGM強い」→ ナレーション帯域を避けるEQ調整"
            ]
        )
    ]

    // MARK: - タイムラインマーカー
    static let timelineMarkers: [TimelineMarker] = [
        .init(id: UUID(), time: 12, label: "導入"),
        .init(id: UUID(), time: 138, label: "訴求ズレ"),
        .init(id: UUID(), time: 301, label: "BGM過多"),
        .init(id: UUID(), time: 420, label: "テンポ落ち")
    ]

    // MARK: - FB履歴（日付グループ化対応）
    static let historyItems: [FeedbackHistoryItem] = [
        .init(
            id: UUID(), projectTitle: "CEO対談 Vol.12", guestName: "さといも・トーマス",
            date: "2026/03/10", timestamp: "02:18",
            rawVoiceText: "ここマジで伝わりづらい。テロップ多すぎる。",
            convertedText: "02:18付近のテロップ情報量を減らし、1カット1メッセージに整理してください。",
            isSent: true, editorStatus: "対応済み",
            learningEffect: "次案件で平均テロップ文字数が18%改善"
        ),
        .init(
            id: UUID(), projectTitle: "CEO対談 Vol.12", guestName: "さといも・トーマス",
            date: "2026/03/10", timestamp: "05:01",
            rawVoiceText: "ここのBロールダサい。もっとテンポ良くして。",
            convertedText: "05:01-05:16のBロールを差し替え、カット間隔を2秒以内に短縮してください。",
            isSent: false, editorStatus: "未対応",
            learningEffect: ""
        ),
        .init(
            id: UUID(), projectTitle: "採用密着ドキュメント", guestName: "メンイチ",
            date: "2026/03/09", timestamp: "00:44",
            rawVoiceText: "BGMが前に出すぎて声が弱い。",
            convertedText: "00:44-01:05のBGMレベルを-3dB調整し、ナレーション明瞭度を優先してください。",
            isSent: true, editorStatus: "確認中",
            learningEffect: "同編集者の音声明瞭度スコア +7"
        ),
        .init(
            id: UUID(), projectTitle: "ブランドムービー 2026", guestName: "けー",
            date: "2026/03/08", timestamp: "01:30",
            rawVoiceText: "冒頭のフックが弱い。もっとガツンと。",
            convertedText: "冒頭15秒に結論を先出しし、視聴者が自分ごと化できるフックを挿入してください。",
            isSent: true, editorStatus: "対応済み",
            learningEffect: "冒頭離脱率が23%改善"
        )
    ]

    // MARK: - 品質ダッシュボード
    static let qualityTrend: [QualityTrendPoint] = [
        .init(id: UUID(), label: "Vol.7", score: 62),
        .init(id: UUID(), label: "Vol.8", score: 68),
        .init(id: UUID(), label: "Vol.9", score: 74),
        .init(id: UUID(), label: "Vol.10", score: 78),
        .init(id: UUID(), label: "Vol.11", score: 81),
        .init(id: UUID(), label: "Vol.12", score: 86),
        .init(id: UUID(), label: "Vol.13", score: 83),
        .init(id: UUID(), label: "Vol.14", score: 88),
        .init(id: UUID(), label: "Vol.15", score: 91),
        .init(id: UUID(), label: "Vol.16", score: 89)
    ]

    static let categoryScores: [CategoryScore] = [
        .init(id: UUID(), category: "カメラワーク", score: 85, icon: "camera.fill"),
        .init(id: UUID(), category: "テロップ", score: 78, icon: "textformat.size"),
        .init(id: UUID(), category: "音声", score: 91, icon: "waveform"),
        .init(id: UUID(), category: "演出", score: 82, icon: "theatermasks.fill")
    ]

    static let improvementSuggestions: [ImprovementSuggestion] = [
        .init(id: UUID(), category: "テロップ", suggestion: "1カットあたりの文字数を20文字以内に統一する", priority: .high),
        .init(id: UUID(), category: "カメラワーク", suggestion: "ゲストの感情が高まる場面で寄りショットを追加する", priority: .medium),
        .init(id: UUID(), category: "演出", suggestion: "冒頭フックの結論先出しパターンを全案件に標準適用する", priority: .high)
    ]

    static let editorSkills: [EditorSkill] = [
        .init(id: UUID(), editorName: "Editor A", strengths: ["カットテンポ", "構図"], weakPoints: ["BGM設計"], growth: 12),
        .init(id: UUID(), editorName: "Editor B", strengths: ["テロップ", "色補正"], weakPoints: ["導入フック"], growth: 8)
    ]

    static let alerts: [QualityAlert] = [
        .init(id: UUID(), level: "High", message: "最新2本で音声明瞭度が基準値を下回りました"),
        .init(id: UUID(), level: "Medium", message: "レビュー待ち案件が3件滞留中です")
    ]

    static let dashboardSummary = DashboardSummary(
        totalProjects: projects.count,
        withAssets: 3,
        avgQualityScore: 85.6,
        statusCounts: [
            "directed": 1,
            "editing": 1,
            "reviewPending": 1,
            "published": 2
        ],
        recentFeedbacks: [
            FeedbackItem(
                id: "mock-feedback-1",
                projectId: "p-satoimo-thomas",
                content: "02:18付近のテロップ情報量を減らし、1カット1メッセージに整理してください。",
                createdBy: "なおとさん",
                createdAt: "2026-03-10T13:20:00Z",
                timestamp: "02:18",
                feedbackType: "voice",
                projectTitle: "CEO対談 Vol.12",
                guestName: "さといも・トーマス",
                rawVoiceText: "ここマジで伝わりづらい。テロップ多すぎる。",
                convertedText: "02:18付近のテロップ情報量を減らし、1カット1メッセージに整理してください。",
                isSent: true
            )
        ],
        unsentFeedbackCount: 1
    )

    static let editorDirectory: [Editor] = [
        .init(
            id: "editor-pug",
            name: "パグさん",
            contactInfo: "@pug_edit",
            status: "active",
            contractType: "freelance",
            skills: .init(cutting: 4.7, color: 4.2, telop: 4.8, bgm: 4.0, cameraWork: 3.8, composition: 4.3, tempo: 4.9),
            activeProjectCount: 4,
            completedCount: 81,
            avgQualityScore: 87.4,
            createdAt: "2025-11-01T09:00:00Z"
        ),
        .init(
            id: "editor-aoi",
            name: "あおいさん",
            contactInfo: "@aoi_movie",
            status: "on_leave",
            contractType: "freelance",
            skills: .init(cutting: 4.2, color: 4.6, telop: 4.1, bgm: 4.4, cameraWork: 4.0, composition: 4.5, tempo: 3.9),
            activeProjectCount: 1,
            completedCount: 54,
            avgQualityScore: 84.1,
            createdAt: "2025-08-21T09:00:00Z"
        )
    ]

    static let trackedVideos: [TrackedVideo] = [
        .init(
            id: "track-1",
            url: "https://youtube.com/watch?v=sample1",
            title: "視聴維持率が高い不動産対談の型",
            channelName: "競合チャンネルA",
            thumbnailUrl: nil,
            analysisStatus: "completed",
            analysisResult: .init(
                overallScore: 91,
                composition: "冒頭3秒で数字と人物属性を固定",
                tempo: "4-6秒の短い尺で視点切替",
                cuttingStyle: "会話の切り返しを細かく維持",
                colorGrading: "暗部を締めた高コントラスト",
                keyTechniques: ["冒頭で結論提示", "Bロールは1.5秒以下", "テロップは2行以内"],
                summary: "テンポ優位で維持率が高い典型パターン"
            ),
            createdAt: "2026-03-11T12:00:00Z"
        )
    ]

    static let trackingInsights: [TrackingInsight] = [
        .init(
            id: "insight-1",
            category: "tempo",
            pattern: "冒頭15秒は2.5秒以内のカット切替が高維持率と相関",
            sourceCount: 12,
            confidence: 0.82,
            createdAt: "2026-03-12T08:30:00Z"
        ),
        .init(
            id: "insight-2",
            category: "cutting",
            pattern: "ゲストの感情が上がる箇所で寄りカットを挟むと保存率が改善",
            sourceCount: 8,
            confidence: 0.76,
            createdAt: "2026-03-12T08:40:00Z"
        )
    ]

    static let latestAudit = AuditReport(
        runAt: "2026-03-13T03:20:00Z",
        pipelineStatus: "warning",
        pendingVideos: 2,
        qualityAnomalies: ["音声明瞭度が基準値以下の案件が2件", "未送信フィードバックが1件残存"],
        staleProjects: ["採用密着ドキュメント"],
        overallHealth: "warning"
    )

    static let auditHistory: [AuditReport] = [
        latestAudit,
        .init(
            runAt: "2026-03-12T03:20:00Z",
            pipelineStatus: "healthy",
            pendingVideos: 1,
            qualityAnomalies: [],
            staleProjects: [],
            overallHealth: "good"
        )
    ]

    // MARK: - Vimeoタイムラインモックデータ
    // 実データのVimeo URLパターンに合わせた動画ID（例: https://vimeo.com/1145126331）
    static let sampleVimeoVideoId = "1145126331"

    static let vimeoFeedbacks: [VimeoFeedbackItem] = [
        .init(
            id: UUID(),
            timestampMark: 12,
            element: "カット割り",
            priorityRaw: "高",
            note: "冒頭フックが弱い。結論を先出しして視聴者を引き込む構成に変更してください。",
            vimeoVideoId: sampleVimeoVideoId
        ),
        .init(
            id: UUID(),
            timestampMark: 78,
            element: "テロップ",
            priorityRaw: "高",
            note: "テロップ情報量が多すぎる。1カット1メッセージに整理してください。",
            vimeoVideoId: sampleVimeoVideoId
        ),
        .init(
            id: UUID(),
            timestampMark: 138,
            element: "BGM",
            priorityRaw: "中",
            note: "BGMレベルを-3dB調整し、ナレーション明瞭度を優先してください。",
            vimeoVideoId: sampleVimeoVideoId
        ),
        .init(
            id: UUID(),
            timestampMark: 220,
            element: "カメラワーク",
            priorityRaw: "低",
            note: "Bロール差し替えでテンポ改善。インサートカットを追加するとリズムが出ます。",
            vimeoVideoId: sampleVimeoVideoId
        ),
        .init(
            id: UUID(),
            timestampMark: 301,
            element: "構図",
            priorityRaw: "中",
            note: "クロースアップが続きすぎ。引きの画を挟んでテンポに変化を出してください。",
            vimeoVideoId: sampleVimeoVideoId
        )
    ]
}
