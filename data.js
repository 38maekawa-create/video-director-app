// モックデータ（SwiftUI MockData.swiftと同等）

const MockData = {
  // プロジェクト一覧（撮影日の新しい順）
  projects: [
    {
      id: 'p1',
      videoId: 'vd-001',
      guestName: 'さといも・トーマス',
      title: 'CEO対談 Vol.12',
      icon: 'VD',
      shootDate: '2026/03/08',
      guestAge: 34,
      guestOccupation: '不動産投資家',
      status: 'reviewPending',
      statusLabel: 'レビュー待ち',
      unreviewedCount: 3,
      qualityScore: 78,
      hasUnsentFeedback: true,
      sourceVideo: {
        title: 'CEO対談 Vol.12 素材',
        duration: '12:48',
        sourceUrl: '#source-vd-001',
        summary: '意思決定の速さと再現性を主軸にした対談素材。冒頭フックと中盤の事例整理が重要。'
      },
      editedVideo: {
        title: 'CEO対談 Vol.12 編集版',
        editedUrl: '#edited-vd-001',
        status: 'reviewPending',
        statusLabel: 'レビュー待ち',
        qualityScore: 78
      },
      feedbackSummary: {
        latestFeedback: '02:18付近の情報量整理と、05:01以降のテンポ改善が主論点。',
        evaluation: '構成は強いが、テロップ過多とBロールの弱さで没入感を落としている。',
        historyCount: 2
      },
      knowledge: {
        summary: '冒頭フックを強くし、判断基準を先出しする構成が有効。',
        transcriptAvailable: true,
        highlights: ['冒頭15秒で結論先出し', '判断基準を先出し', '中盤の事例整理が肝'],
        transcriptPreview: '意思決定の基準を最初に提示してから、具体事例に入ると視聴維持が安定する。'
      },
      vimeoReview: {
        url: '#vimeo-vd-001',
        statusLabel: 'コメント未送信あり',
        syncStatus: 'partial',
        pendingCount: 1,
        lastSyncedAt: '2026/03/11 16:20'
      },
      relay: {
        endpoint: 'http://mac-relay.local/api/vimeo/review-comments',
        authMode: 'relay_token',
        targetVideoId: 'vimeo-vd-001',
        routeStatus: 'ready'
      }
    },
    {
      id: 'p2',
      videoId: 'vd-002',
      guestName: 'メンイチ',
      title: '採用密着ドキュメント',
      icon: 'DC',
      shootDate: '2026/03/05',
      guestAge: 29,
      guestOccupation: 'Webマーケター',
      status: 'editing',
      statusLabel: '編集中',
      unreviewedCount: 1,
      qualityScore: 82,
      hasUnsentFeedback: true,
      sourceVideo: {
        title: '採用密着ドキュメント 素材',
        duration: '08:34',
        sourceUrl: '#source-vd-002',
        summary: '採用現場の空気感は良いが、音声の抜けと導入の弱さが残る。'
      },
      editedVideo: {
        title: '採用密着ドキュメント 編集版',
        editedUrl: '#edited-vd-002',
        status: 'editing',
        statusLabel: '編集中',
        qualityScore: 82
      },
      feedbackSummary: {
        latestFeedback: 'BGMを引いて、音声の明瞭度を優先したい。',
        evaluation: '素材の熱量は高い。音の整理で完成度が一段上がる。',
        historyCount: 1
      },
      knowledge: {
        summary: '採用系は感情の乗る表情カットを早めに入れると持続率が上がる。',
        transcriptAvailable: true,
        highlights: ['表情カットを早めに入れる', '導入で現場空気感を掴ませる', '音声の抜けを先に整える'],
        transcriptPreview: '採用現場の温度感は強いので、導入で空気感を見せ切ってから情報に入る方が刺さる。'
      },
      vimeoReview: {
        url: '#vimeo-vd-002',
        statusLabel: '変換レビュー待ち',
        syncStatus: 'draftOnly',
        pendingCount: 1,
        lastSyncedAt: '2026/03/11 15:40'
      },
      relay: {
        endpoint: 'http://mac-relay.local/api/vimeo/review-comments',
        authMode: 'relay_token',
        targetVideoId: 'vimeo-vd-002',
        routeStatus: 'draft'
      }
    },
    {
      id: 'p3',
      videoId: 'vd-003',
      guestName: 'けー',
      title: 'ブランドムービー 2026',
      icon: 'BM',
      shootDate: '2026/03/01',
      guestAge: 31,
      guestOccupation: 'コンサルタント',
      status: 'directed',
      statusLabel: 'ディレクション済',
      unreviewedCount: 0,
      qualityScore: 91,
      hasUnsentFeedback: false,
      sourceVideo: {
        title: 'ブランドムービー 2026 素材',
        duration: '10:02',
        sourceUrl: '#source-vd-003',
        summary: 'ブランド訴求は強い。冒頭フックの設計だけもう一段強めたい。'
      },
      editedVideo: {
        title: 'ブランドムービー 2026 編集版',
        editedUrl: '#edited-vd-003',
        status: 'directed',
        statusLabel: 'ディレクション済',
        qualityScore: 91
      },
      feedbackSummary: {
        latestFeedback: '冒頭15秒の結論先出しを入れるとさらに強い。',
        evaluation: '完成度は高い。微調整でより刺さる。',
        historyCount: 1
      },
      knowledge: {
        summary: 'ブランドムービーは情緒だけでなく、視聴者の判断材料を一つ入れると強い。',
        transcriptAvailable: true,
        highlights: ['情緒だけで押し切らない', '冒頭フックを一段強く', '判断材料を1つ差し込む'],
        transcriptPreview: '世界観訴求だけでなく、視聴者が判断できる具体要素を一つ置くとブランド理解が深まる。'
      },
      vimeoReview: {
        url: '#vimeo-vd-003',
        statusLabel: '確認済み',
        syncStatus: 'synced',
        pendingCount: 0,
        lastSyncedAt: '2026/03/11 12:03'
      },
      relay: {
        endpoint: 'http://mac-relay.local/api/vimeo/review-comments',
        authMode: 'relay_token',
        targetVideoId: 'vimeo-vd-003',
        routeStatus: 'ready'
      }
    },
    {
      id: 'p4',
      videoId: 'vd-004',
      guestName: 'hirai',
      title: 'イベントダイジェスト',
      icon: 'EV',
      shootDate: '2026/02/28',
      guestAge: 27,
      guestOccupation: '映像クリエイター',
      status: 'published',
      statusLabel: '公開',
      unreviewedCount: 0,
      qualityScore: 88,
      hasUnsentFeedback: false,
      sourceVideo: {
        title: 'イベントダイジェスト 素材',
        duration: '06:55',
        sourceUrl: '#source-vd-004',
        summary: 'イベントの熱量は十分。ハイライトの切り出し精度が良い。'
      },
      editedVideo: {
        title: 'イベントダイジェスト 編集版',
        editedUrl: '#edited-vd-004',
        status: 'published',
        statusLabel: '公開',
        qualityScore: 88
      },
      feedbackSummary: {
        latestFeedback: '大きな戻しなし。',
        evaluation: '公開ラインに十分達している。',
        historyCount: 0
      },
      knowledge: {
        summary: 'イベント系は冒頭で全体空気感を掴ませ、その後に人物寄りを差すと良い。',
        transcriptAvailable: true,
        highlights: ['冒頭で全体空気感を掴ませる', '人物寄りで感情を補う', 'ハイライトの切り出し精度を維持'],
        transcriptPreview: 'イベントダイジェストは雰囲気だけでなく、人の熱量が見える寄りカットで記憶に残る。'
      },
      vimeoReview: {
        url: '#vimeo-vd-004',
        statusLabel: '公開完了',
        syncStatus: 'synced',
        pendingCount: 0,
        lastSyncedAt: '2026/03/10 21:48'
      },
      relay: {
        endpoint: 'http://mac-relay.local/api/vimeo/review-comments',
        authMode: 'relay_token',
        targetVideoId: 'vimeo-vd-004',
        routeStatus: 'ready'
      }
    },
    {
      id: 'p5',
      videoId: 'vd-005',
      guestName: 'コテ',
      title: '不動産投資入門シリーズ #3',
      icon: 'RE',
      shootDate: '2026/02/25',
      guestAge: 38,
      guestOccupation: '不動産オーナー',
      status: 'published',
      statusLabel: '公開',
      unreviewedCount: 0,
      qualityScore: 85,
      hasUnsentFeedback: false,
      sourceVideo: {
        title: '不動産投資入門シリーズ #3 素材',
        duration: '09:11',
        sourceUrl: '#source-vd-005',
        summary: '情報密度は高い。初心者向けに整理して見せる構成が肝。'
      },
      editedVideo: {
        title: '不動産投資入門シリーズ #3 編集版',
        editedUrl: '#edited-vd-005',
        status: 'published',
        statusLabel: '公開',
        qualityScore: 85
      },
      feedbackSummary: {
        latestFeedback: '大きな修正なし。',
        evaluation: '十分見やすいが、要点先出しがあるとさらに強い。',
        historyCount: 0
      },
      knowledge: {
        summary: '入門系は章立ての可視化と、結論の先出しが理解効率を上げる。',
        transcriptAvailable: true,
        highlights: ['章立てを可視化', '結論を先出し', '初心者の理解負荷を下げる'],
        transcriptPreview: '入門動画は情報密度より理解速度が大事なので、章立てと結論先出しが効く。'
      },
      vimeoReview: {
        url: '#vimeo-vd-005',
        statusLabel: '公開完了',
        syncStatus: 'synced',
        pendingCount: 0,
        lastSyncedAt: '2026/03/10 20:52'
      },
      relay: {
        endpoint: 'http://mac-relay.local/api/vimeo/review-comments',
        authMode: 'relay_token',
        targetVideoId: 'vimeo-vd-005',
        routeStatus: 'ready'
      }
    }
  ],

  // ディレクションレポートセクション
  reportSections: [
    {
      id: 'rs1',
      title: '演出ディレクション',
      icon: 'DR',
      items: [
        '層b（実務志向）: 成果の再現性を重視',
        '刺さる訴求: プロセスと判断基準を明示',
        '冒頭15秒で「自分ごと化」できるフックを入れる'
      ]
    },
    {
      id: 'rs2',
      title: 'テロップ指示',
      icon: 'TL',
      items: [
        '年収ワードは補助的に使用。主軸は意思決定スピード',
        '金額より『改善幅』を見せる方が信頼形成に有効',
        '1カット1メッセージ厳守。情報過多にしない'
      ]
    },
    {
      id: 'rs3',
      title: 'カメラワーク',
      icon: 'CM',
      items: [
        '00:12-00:26: 冒頭フックを強化（結論先出し）',
        '02:18-02:34: Bロール差し替えでテンポ改善',
        '05:01-05:16: ゲストの表情を寄りで捉える'
      ]
    },
    {
      id: 'rs4',
      title: '音声FB履歴',
      icon: 'VO',
      items: [
        '「テロップ多すぎ」→ 1カット1メッセージに整理',
        '「BGM強い」→ ナレーション帯域を避けるEQ調整'
      ]
    }
  ],

  // FB履歴（日付グループ化対応）
  historyItems: [
    {
      id: 'h1',
      videoId: 'vd-001',
      projectTitle: 'CEO対談 Vol.12',
      guestName: 'さといも・トーマス',
      date: '2026/03/10',
      timestamp: '02:18',
      rawVoiceText: 'ここマジで伝わりづらい。テロップ多すぎる。',
      convertedText: '02:18付近のテロップ情報量を減らし、1カット1メッセージに整理してください。',
      isSent: true,
      editorStatus: '対応済み',
      reviewMode: 'transformed',
      syncState: 'synced',
      learningEffect: '次案件で平均テロップ文字数が18%改善',
      referenceExample: {
        title: '会話密度が高い対談の整理例',
        url: 'https://example.com/reference/dialogue-density',
        note: '情報を削るのではなく、1カット1論点に分解している'
      }
    },
    {
      id: 'h2',
      videoId: 'vd-001',
      projectTitle: 'CEO対談 Vol.12',
      guestName: 'さといも・トーマス',
      date: '2026/03/10',
      timestamp: '05:01',
      rawVoiceText: 'ここのBロールダサい。もっとテンポ良くして。',
      convertedText: '05:01-05:16のBロールを差し替え、カット間隔を2秒以内に短縮してください。',
      isSent: false,
      editorStatus: '未対応',
      reviewMode: 'transformed',
      syncState: 'pending_sync',
      learningEffect: '',
      referenceExample: {
        title: 'テンポ改善のBロール差し替え事例',
        url: 'https://example.com/reference/broll-rhythm',
        note: '画面情報量よりも切替速度で体感テンポを上げている'
      }
    },
    {
      id: 'h3',
      videoId: 'vd-002',
      projectTitle: '採用密着ドキュメント',
      guestName: 'メンイチ',
      date: '2026/03/09',
      timestamp: '00:44',
      rawVoiceText: 'BGMが前に出すぎて声が弱い。',
      convertedText: '00:44-01:05のBGMレベルを-3dB調整し、ナレーション明瞭度を優先してください。',
      isSent: true,
      editorStatus: '確認中',
      reviewMode: 'transformed',
      syncState: 'awaiting_editor',
      learningEffect: '同編集者の音声明瞭度スコア +7',
      referenceExample: {
        title: '会話主体コンテンツの音量設計例',
        url: 'https://example.com/reference/audio-clarity',
        note: 'BGMは感情演出に留め、言葉の理解を最優先にしている'
      }
    },
    {
      id: 'h4',
      videoId: 'vd-003',
      projectTitle: 'ブランドムービー 2026',
      guestName: 'けー',
      date: '2026/03/08',
      timestamp: '01:30',
      rawVoiceText: '冒頭のフックが弱い。もっとガツンと。',
      convertedText: '冒頭15秒に結論を先出しし、視聴者が自分ごと化できるフックを挿入してください。',
      isSent: true,
      editorStatus: '対応済み',
      reviewMode: 'transformed',
      syncState: 'synced',
      learningEffect: '冒頭離脱率が23%改善',
      referenceExample: {
        title: 'フック先出し型の冒頭構成例',
        url: 'https://example.com/reference/opening-hook',
        note: '世界観説明より先に、視聴者の利益を提示している'
      }
    }
  ],

  // 品質ダッシュボード
  qualityTrend: [
    { label: 'Vol.7', score: 62 },
    { label: 'Vol.8', score: 68 },
    { label: 'Vol.9', score: 74 },
    { label: 'Vol.10', score: 78 },
    { label: 'Vol.11', score: 81 },
    { label: 'Vol.12', score: 86 },
    { label: 'Vol.13', score: 83 },
    { label: 'Vol.14', score: 88 },
    { label: 'Vol.15', score: 91 },
    { label: 'Vol.16', score: 89 }
  ],

  categoryScores: [
    { category: 'カメラワーク', score: 85, icon: 'CM' },
    { category: 'テロップ', score: 78, icon: 'TL' },
    { category: '音声', score: 91, icon: 'AU' },
    { category: '演出', score: 82, icon: 'DR' }
  ],

  improvementSuggestions: [
    { category: 'テロップ', suggestion: '1カットあたりの文字数を20文字以内に統一する', priority: 'high' },
    { category: 'カメラワーク', suggestion: 'ゲストの感情が高まる場面で寄りショットを追加する', priority: 'medium' },
    { category: '演出', suggestion: '冒頭フックの結論先出しパターンを全案件に標準適用する', priority: 'high' }
  ],

  alerts: [
    { level: 'high', message: '最新2本で音声明瞭度が基準値を下回りました' },
    { level: 'medium', message: 'レビュー待ち案件が3件滞留中です' }
  ]
};
