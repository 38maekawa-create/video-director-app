// モックデータ（SwiftUI MockData.swiftと同等）

const MockData = {
  // プロジェクト一覧（撮影日の新しい順）
  projects: [
    {
      id: 'p1',
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
      hasUnsentFeedback: true
    },
    {
      id: 'p2',
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
      hasUnsentFeedback: true
    },
    {
      id: 'p3',
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
      hasUnsentFeedback: false
    },
    {
      id: 'p4',
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
      hasUnsentFeedback: false
    },
    {
      id: 'p5',
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
      hasUnsentFeedback: false
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
      projectTitle: 'CEO対談 Vol.12',
      guestName: 'さといも・トーマス',
      date: '2026/03/10',
      timestamp: '02:18',
      rawVoiceText: 'ここマジで伝わりづらい。テロップ多すぎる。',
      convertedText: '02:18付近のテロップ情報量を減らし、1カット1メッセージに整理してください。',
      isSent: true,
      editorStatus: '対応済み',
      learningEffect: '次案件で平均テロップ文字数が18%改善'
    },
    {
      id: 'h2',
      projectTitle: 'CEO対談 Vol.12',
      guestName: 'さといも・トーマス',
      date: '2026/03/10',
      timestamp: '05:01',
      rawVoiceText: 'ここのBロールダサい。もっとテンポ良くして。',
      convertedText: '05:01-05:16のBロールを差し替え、カット間隔を2秒以内に短縮してください。',
      isSent: false,
      editorStatus: '未対応',
      learningEffect: ''
    },
    {
      id: 'h3',
      projectTitle: '採用密着ドキュメント',
      guestName: 'メンイチ',
      date: '2026/03/09',
      timestamp: '00:44',
      rawVoiceText: 'BGMが前に出すぎて声が弱い。',
      convertedText: '00:44-01:05のBGMレベルを-3dB調整し、ナレーション明瞭度を優先してください。',
      isSent: true,
      editorStatus: '確認中',
      learningEffect: '同編集者の音声明瞭度スコア +7'
    },
    {
      id: 'h4',
      projectTitle: 'ブランドムービー 2026',
      guestName: 'けー',
      date: '2026/03/08',
      timestamp: '01:30',
      rawVoiceText: '冒頭のフックが弱い。もっとガツンと。',
      convertedText: '冒頭15秒に結論を先出しし、視聴者が自分ごと化できるフックを挿入してください。',
      isSent: true,
      editorStatus: '対応済み',
      learningEffect: '冒頭離脱率が23%改善'
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
