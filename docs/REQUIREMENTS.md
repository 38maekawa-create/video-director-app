# AI開発10 — 映像品質追求・自動ディレクションシステム 要件定義書

> 最終更新: 2026-03-10
> 承認: なおとさん（ユーザー）
> 作成: 司令塔セッション

---

## 1. システム概要

### 1-1. 目的
TEKO対談インタビュー動画の文字起こしデータを入力として、動画編集者向けの「ディレクションレポート」を自動生成するシステム。さらに映像品質のトラッキング・学習により、ディレクション精度を継続的に改善する。

### 1-2. ユーザー体験（完成形）
1. AI開発5で新規動画の文字起こしが完了する
2. AI開発10が自動でディレクションレポートを生成
3. HTMLページとしてGitHub Pagesに公開
4. スプレッドシートにURLが自動追記される
5. 編集者がURLを開いてディレクションを確認しながら編集作業を行う
6. 編集後の動画に対してFBを生成 → 品質管理
7. 人間（なおと・パグさん）のFBを蓄積 → 学習して次回以降に反映
8. 外部映像（YouTube等）をトラッキング → 分析 → ディレクションに反映

---

## 2. 全28機能リスト（確定版）

### Phase 1: コアエンジン（9機能）

| ID | 機能名 | 概要 |
|----|--------|------|
| A-1 | ゲスト層自動分類 | 文字起こしから年収・職歴・年齢を抽出 → 層a（圧倒的に強い）/ 層b（相対的強さの言語化が必要）/ 層c（自営業家系2代目3代目）を自動判定 → 判定結果に応じた見せ方テンプレート選定 |
| A-2 | 年収演出判断 | TEKO独自の年齢別早見表（20代前半:500万、20代後半:600万、30代前半:700万）に基づく自動判定。基準+100万以上→強調ON。700万以上→無条件強調。20代で700万以上→年次補足テロップ推奨 |
| A-3 | 年収以外の強さ発掘 | A-2で強調OFFの場合に実行。代替の強みを自動検出: 在籍企業のブランド力、キャリアパスの希少性、勤務形態の自由度、転職先の年収見込み。ゆりかさんパターン（週4勤務500万）、りょうすけさんパターン（前職の大手ブランド）等 |
| A-4 | 固有名詞規制 | 企業名・サービス名を自動検出 → 伏せるべきか判定 → ピー音+煽りテロップ（「誰もが知る○○業界の超大手企業」）のテンプレート自動生成。「凄すぎて出せない」演出への転換提案 |
| A-5 | ターゲット別チェックリスト | 各シーンが1層（ハイキャリア向け：焦燥感・所属欲求の喚起）/2層（2代目3代目向け：共感・安心感の喚起）のどちらに刺さるかラベリング + バランスチェック |
| NEW-1 | 演出ディレクション | テロップ強調・色変えの最適タイミング指示、引き（ワイド）・寄り（アップ）の最適タイミング指示、画角変更タイミング指示。文字起こしの内容・文脈を分析して「ここで寄る」「ここでテロップ強調」等を具体的に指示 |
| H-1 | メンバーマスター自動連動 | ~/TEKO/knowledge/people/MEMBER_MASTER.json（50名）の属性をディレクションレポートに自動参照。新メンバー追加時も自動連動 |
| J-1 | AI開発5連携 | ~/TEKO/knowledge/raw-data/video_transcripts/ からの自動取り込み。AI開発5の処理完了時のトリガー発火（ファイルウォッチ） |
| J-2 | スプシ統合 | 【インタビュー対談動画】管理タブとの双方向連携。データ取得 + ディレクションURL自動追記 |

### Phase 2: 映像品質評価 + 編集支援（9機能）

| ID | 機能名 | 概要 |
|----|--------|------|
| B-1 | 7要素品質スコアリング | カット割り（20%）、色彩（20%）、テロップ（15%）、BGM（15%）、カメラワーク（10%）、構図（10%）、テンポ（10%）を各0-100点で数値化 |
| B-2 | 品質トラッキングダッシュボード | 動画ごとの品質スコア時系列推移 + 改善率の可視化（初稿→修正1→修正2→完成版） |
| B-3 | 編集者別スキルマトリクス | 各編集者の得意/苦手を数値化 → タスクアサイン時の最適マッチング提案 + 成長推移記録 |
| C-1 | フレーム画像マルチモデル評価 | 代表フレームをClaude Opus 4.6 + GPT-5.4で独立評価。両モデル合意→「指摘」に昇格、不合意→「要検討」 |
| C-2 | テロップ自動チェック | フォント統一性・サイズ適正・配置の一貫性をOCR+LLMで検証 + 誤字脱字検出 |
| C-3 | 音声品質自動評価 | BGMと会話音声のバランス + ノイズレベル検出 + SE適切性評価 |
| E-1改 | 切り抜きカットポイント | 切り抜き動画作成のための最適カットポイント提案。どこからどこまで切り出せば単体で成立するかを指示 |
| NEW-2 | ハイライトカットポイント | ハイライト使用シーンの最適カットポイントディレクション |
| NEW-3 | 編集後動画FB | 編集済み動画に対して: 映像品質管理（B-1基準）+ 取捨選択された内容へのFB + テロップ誤字チェック |

### Phase 3: 映像トラッキング + 学習（4機能）

| ID | 機能名 | 概要 |
|----|--------|------|
| NEW-4 | 映像トラッキング | YouTube等から参考映像を収集・追跡。映像品質の参考軸として。Netflix/Hulu等のストリーミングサービスからも可能な範囲で |
| NEW-5 | トラッキング映像分析 | 収集した映像の要素分解（構図・テンポ・演出技法・カット割り・色彩・音声バランス等） |
| NEW-6 | 人間FB学習 | なおとさん・パグさんのフィードバックを構造化して蓄積 → ディレクションルールに自動反映 → 精度を継続改善 |
| NEW-7 | トラッキング映像学習 | 収集・分析した外部映像のパターンを学習 → ディレクション指示に反映（「Netflix風のカット割り」等） |

### Phase 4: 管理 + インフラ（6機能）

| ID | 機能名 | 概要 |
|----|--------|------|
| NEW-8 | 編集者管理シート | 名簿管理（名前・連絡先・稼働状況・契約形態）+ スキル管理（得意分野・対応可能編集種別）+ 工程管理（案件担当・進捗・納期）+ 実績トラッキング + キャパシティ管理 |
| F-3 | 編集者引き継ぎパッケージ | 担当者交代時に過去フィードバック・修正履歴・品質基準を自動パッケージ化 |
| J-3 | 定期巡回監査 | パイプライン死活監視 + 品質異常値検出 + 未処理動画の滞留アラート |
| J-4 | Telegram/LINE通知 | レポート完成時 + 品質警告 + 編集者への自動フィードバック配信 |
| J-5 | 品質改善ループ | ディレクション→編集→評価→FB→ルール更新のPDCAサイクル自動化 |
| J-6 | マルチMac分散処理 | 映像フレーム分析等の重い処理をMac2/3に分散 + タイムアウト管理 |

---

## 3. 入力データ仕様

### 3-1. AI開発5の出力（主入力）

**保存先**: `~/TEKO/knowledge/raw-data/video_transcripts/`

**ファイル形式**: JSON

**ファイル名規則**: `{処理日}_{撮影日}撮影_{正規名}さん：{属性}.json`

**データ構造**:
```json
{
  "_metadata": {
    "source_system": "ai_dev_5",
    "source_type": "interview",
    "collected_at": "2026-02-16T00:00:00+09:00",
    "catalog_category": "video_transcripts",
    "member": "みんてぃあさん"
  },
  "full_text": "文字起こし全文",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "セグメントテキスト",
      "speaker": "Speaker 1"
    }
  ],
  "speakers": ["Speaker 1", "Speaker 2"],
  "duration_seconds": 2017.5
}
```

**補足**: `_metadata` フィールドは導入中（Phase 4B予定）。既存ファイルは未装備の可能性あり。

### 3-2. AI開発5のMarkdownナレッジファイル（補助入力）

**保存先**: `~/TEKO/knowledge/01_teko/sources/video/`

**含まれる情報**:
- メタ情報（種別・カテゴリ・話者・動画時間）
- 3行要約
- 主要トピック
- 詳細要約
- ハイライトシーン（タイムスタンプ・話者・発言・分類）
- 人物プロファイル（年齢・本業・年収・思考特徴・キー発言）
- 整形済みトランスクリプト全文（話者ラベル + タイムスタンプ付き）

**重要**: Phase 1ではこのMarkdownファイルを主入力として使う。年収・企業名・年齢・話者情報が全て整形済みで含まれている。

### 3-3. MEMBER_MASTER.json

**パス**: `~/TEKO/knowledge/people/MEMBER_MASTER.json`

**50名分のメンバー情報**:
```json
{
  "canonical_name": "みんてぃあさん",
  "aliases": ["みんてぃあさん", "みんてぃあ"],
  "source_of_truth": "people/みんてぃあさん.md",
  "has_people_file": true,
  "data_locations": {
    "people_file": "people/みんてぃあさん.md",
    "video_transcripts": [...],
    "voice_transcripts": [...]
  }
}
```

各メンバーの詳細プロファイルは `~/TEKO/knowledge/people/{名前}.md` に格納。

### 3-4. ディレクションマニュアル

**パス**: `~/AI開発10/docs/teko_interview_direction_manual.md`

**含まれるルール**:
- ゲスト分類体系（層a/b/c）
- 年齢別年収早見表
- 年収以外の強さの見せ方パターン
- 固有名詞の取り扱い（自主規制音の活用）
- ターゲット別視聴後感（1層: 焦燥感、2層: 共感）

### 3-5. スプレッドシート

**スプレッドシートID**: `1bW_qb13p747xoa2yf7RHaccNVTFCMxV8a5CjGdNqI6I`

**タブ名**: `【インタビュー対談動画】管理`（gid: 600901662）

**行数**: 201行 × 65列

**主要カラム構造（Row 2がヘッダー）**:

| 列 | ヘッダー | 内容 |
|----|---------|------|
| A | コンテンツ | 種別（単独インタビュー等） |
| B | タイトル | INT001_ブンさん 等 |
| C | 素材URL | Dropboxリンク |
| D | 依頼内容 | Google Docsリンク |
| E | 動画横型 | TRUE/FALSE |
| F | 動画縦型 | TRUE/FALSE |
| G | 文字起こし | TRUE/FALSE |
| H | 文字起こし完了日 | 日付 |
| I | 誤字修正 | TRUE/FALSE |
| K | コラム化 | TRUE/FALSE |
| L | 画像リンク | Gyazoリンク |
| N | Vimeo | VimeoリンクまたはID |
| O | 担当者（横型） | 編集者名 |
| P | 依頼日（横型） | 日付 |
| Q | 優先順位 | 完納/進行中等 |
| R-V | 初稿〜納品3（横型） | 各段階のDropbox/YouTubeリンク |
| W | 備考（横型） | フリーテキスト |
| AA | 担当者（縦型） | 編集者名 |
| AF | 担当者（切り抜き） | 編集者名 |
| AU | 担当者（リール） | 編集者名 |
| BD-BK | 文字起こし修正 | カテゴリ・AiNote・修正データ・納品日 |

**AI開発10が追加する列**: ディレクションURL列を末尾に追加（新規列）

**認証**: `~/.config/maekawa/google-credentials.json`（サービスアカウント。AI開発3と同じ認証情報を共有）

---

## 4. 出力仕様

### 4-1. ディレクションHTML ページ

**出力先リポジトリ**: `~/direction-pages/`（新規作成）

**GitHub Pages URL**: `https://38maekawa-create.github.io/direction-pages/`

**ファイル名規則**: `YYYYMMDD_{ゲスト名}_direction.html`

**ページ構成（Phase 1）**:

```html
<!-- テンプレート構造 -->
<header>
  <h1>ディレクションレポート: {ゲスト名}</h1>
  <div class="meta-grid">
    <!-- ゲスト基本情報: 年齢、本業、年収、メンバー期 -->
    <!-- 動画メタ: 動画時間、撮影日、種別 -->
    <!-- 分類結果: ゲスト層（a/b/c）、年収演出判定 -->
  </div>
</header>

<section id="guest-classification">
  <!-- A-1: ゲスト層判定結果と見せ方テンプレート -->
</section>

<section id="income-direction">
  <!-- A-2: 年収演出判断 + A-3: 代替の強み -->
  <!-- テロップ指示（強調ON/OFF、補足テロップ文言） -->
</section>

<section id="proper-nouns">
  <!-- A-4: 固有名詞規制リスト -->
  <!-- 各固有名詞: 伏せる/出すの判定 + テロップ提案文 -->
</section>

<section id="direction-timeline">
  <!-- NEW-1: 演出ディレクション（タイムライン形式） -->
  <!-- [MM:SS] テロップ強調「年収○○万」→ 色変え -->
  <!-- [MM:SS] ここで寄り（アップ）→ キー発言 -->
  <!-- [MM:SS] 画角変更: ワイド→2ショット -->
</section>

<section id="target-checklist">
  <!-- A-5: ターゲット別チェックリスト -->
  <!-- 1層向けシーン一覧 + 2層向けシーン一覧 -->
</section>

<section id="highlights">
  <!-- ハイライトシーンまとめ -->
</section>

<details>
  <summary>整形済みトランスクリプト（全文）</summary>
  <!-- 全文字起こし -->
</details>
```

**CSS設計**: `video-knowledge-pages` のCSS設計を踏襲（インラインCSS、max-width: 820px、レスポンシブ対応）

**index.html**: 全ディレクションレポートの一覧ページ（日付降順）。video-knowledge-pagesと同じパターン。

### 4-2. スプレッドシートへの書き込み

【インタビュー対談動画】管理タブの末尾に新列「ディレクションURL」を追加。

タイトル列（B列）のINT番号+ゲスト名でマッチングし、対応する行にURLを書き込む。

---

## 5. ディレクションルール体系（Phase 1のコアロジック）

### 5-1. ゲスト分類ロジック（A-1）

```
入力: 文字起こしから抽出した{年収, 職歴, 年齢, 家系背景}

IF 自営業家系・2代目・3代目の言及あり:
    → 層c（自営業家系）
    → 見せ方: 強さ + ストーリー（葛藤・変化）に重き
ELIF 年収1000万以上 OR 有名企業管理職 OR 士業（監査法人等）:
    → 層a（圧倒的に強い）
    → 見せ方: 強さ・ハイキャリアさを前面に
ELSE:
    → 層b（相対的強さの言語化が必要）
    → 見せ方: 年収以外の文脈で強さを言語化
```

### 5-2. 年収演出判断ロジック（A-2）

```
早見表:
  20代前半〜中盤: 500万
  20代後半: 600万
  30代前半: 700万

IF 年収 >= 700万:
    → 無条件で強調ON
    IF 年齢が20代 AND 年収 >= 700万:
        → テロップで年次・年齢の補足推奨
ELIF 年収 >= 早見表基準 + 100万:
    → 強調ON（文脈付きテロップ推奨）
ELIF 年収 <= 早見表基準:
    → 強調OFF → A-3（代替の強み）を実行
```

### 5-3. 固有名詞判定ロジック（A-4）

```
1. 文字起こし全文から企業名・サービス名を抽出
2. 各固有名詞について:
   - ゲスト本人が開示OKとしている場合 → 出す
   - 「前置きで開示不能と言っている」場合 → 伏せる
   - 判断が難しい場合 → 伏せる（安全側に倒す）
3. 伏せる場合のテロップテンプレート:
   - 「誰もが知る{業界}の超大手企業」
   - 「{業界}トップクラスの{企業種別}」
   - 「年商{規模}規模の{企業種別}」
```

### 5-4. 演出ディレクション基本原則（NEW-1）

```
テロップ強調タイミング:
  - 年収・実績の数字が出た瞬間
  - キー発言（パンチライン）
  - 話題の転換点

画角変更タイミング:
  - キー発言時: ワイド → 寄り（アップ）
  - 笑い・リアクション時: 寄り → ワイド（2ショット）
  - 新しい話題の開始時: 画角リセット

色変えタイミング:
  - 強調テロップ出現時
  - ゲスト層a/bの強さ強調シーン
```

---

## 6. 技術スタック

### 6-1. 共通
- Python 3.11+
- gspread（Google Sheets連携）
- google-auth（サービスアカウント認証）

### 6-2. Phase 1
- anthropic SDK（Claude Sonnet/Opus による分析）
- openai SDK（GPT-5.4による分析 — Phase 2のC-1で使用）
- Jinja2 or 自前HTMLテンプレート（direction-pages生成）
- GitPython or subprocess（GitHub Pagesへの自動push）

### 6-3. Phase 2以降
- opencv-python（フレーム抽出 — C-1）
- Pillow（画像処理）
- pytesseract or easyocr（テロップOCR — C-2）
- ffmpeg（音声分析 — C-3）

### 6-4. 認証・API
- Google Sheets: `~/.config/maekawa/google-credentials.json`
- Anthropic API: `~/.config/maekawa/api-keys.env` → ANTHROPIC_API_KEY
- OpenAI API: `~/.config/maekawa/api-keys.env` → OPENAI_API_KEY
- GitHub: `gh` CLI（GitHub Pages push用）

---

## 7. ディレクトリ構造（更新版）

```
~/AI開発10/
├── src/
│   └── video_direction/
│       ├── __init__.py
│       ├── main.py                    # エントリーポイント
│       ├── analyzer/
│       │   ├── __init__.py
│       │   ├── transcript_parser.py   # AI開発5出力のパーサー
│       │   ├── guest_classifier.py    # A-1: ゲスト層分類
│       │   ├── income_evaluator.py    # A-2/A-3: 年収演出判断
│       │   ├── proper_noun_filter.py  # A-4: 固有名詞規制
│       │   ├── target_labeler.py      # A-5: ターゲットラベリング
│       │   └── direction_generator.py # NEW-1: 演出ディレクション
│       ├── reporter/
│       │   ├── __init__.py
│       │   ├── html_generator.py      # HTMLレポート生成
│       │   ├── template.py            # HTMLテンプレート
│       │   └── publisher.py           # GitHub Pages公開
│       ├── integrations/
│       │   ├── __init__.py
│       │   ├── sheets_manager.py      # J-2: スプシ連携
│       │   ├── ai_dev5_connector.py   # J-1: AI開発5連携
│       │   └── member_master.py       # H-1: メンバーマスター
│       ├── tracker/                   # Phase 2以降
│       ├── knowledge/                 # Phase 2以降
│       └── editor_manager/            # Phase 4: NEW-8
├── tests/
│   ├── test_guest_classifier.py
│   ├── test_income_evaluator.py
│   ├── test_proper_noun_filter.py
│   └── ...
├── config.yaml
├── requirements.txt
├── docs/
│   ├── REQUIREMENTS.md               # この文書
│   ├── ANTICIPATED_FEATURES.md        # 機能一覧（更新版）
│   └── teko_interview_direction_manual.md  # ディレクションマニュアル
├── CLAUDE.md
├── PROGRESS.md
└── .env                               # API keys（gitignore）

~/direction-pages/                      # 新規リポジトリ（GitHub Pages）
├── index.html
├── YYYYMMDD_{ゲスト名}_direction.html
└── .gitignore
```

---

## 8. Phase 1 完了条件

### 8-1. 機能要件
- [ ] video_transcripts/ のMarkdownファイルを入力 → 9機能を適用 → ディレクションHTMLが生成される
- [ ] 生成されたHTMLがdirection-pages/に保存され、index.htmlが自動更新される
- [ ] GitHub Pagesにpush → URLでアクセス可能
- [ ] スプレッドシートの対応行にディレクションURLが自動追記される
- [ ] MEMBER_MASTER.jsonのメンバー情報がレポートに正しく反映される

### 8-2. 品質要件
- [ ] 少なくとも3件の実データで正常にレポート生成できる
- [ ] ゲスト分類（層a/b/c）が手動判定と一致する
- [ ] 年収演出判断が早見表ルールと一致する
- [ ] 固有名詞が正しく検出・判定される
- [ ] 演出ディレクション（テロップ・画角・色変え）がタイムスタンプ付きで出力される

### 8-3. テスト要件
- [ ] 各モジュールのユニットテスト（pytest）
- [ ] 統合テスト（実データ3件での一気通貫テスト）
- [ ] 生成HTMLのブラウザ表示確認

### 8-4. 監査パス条件
- [ ] Codex（GPT-5.3/5.4）による監査パス
- [ ] GPT-5.4によるセカンドオピニオン監査パス
- [ ] 両者のパスが出るまで差し戻し・修正を繰り返す

---

## 9. 参照先まとめ

| リソース | パス |
|---------|------|
| AI開発5ナレッジ出力 | ~/TEKO/knowledge/01_teko/sources/video/ |
| AI開発5生トランスクリプト | ~/TEKO/knowledge/raw-data/video_transcripts/ |
| メンバーマスター | ~/TEKO/knowledge/people/MEMBER_MASTER.json |
| メンバー詳細プロファイル | ~/TEKO/knowledge/people/{名前}.md |
| ディレクションマニュアル | ~/AI開発10/docs/teko_interview_direction_manual.md |
| video-knowledge-pages（テンプレート参考） | ~/video-knowledge-pages/ |
| voice-knowledge-pages（テンプレート参考） | ~/voice-knowledge-pages/ |
| AI開発5 publish_html.py（パターン参考） | ~/AI開発5/src/video_knowledge/pipeline/publish_html.py |
| AI開発5 google_sheets.py（パターン参考） | ~/AI開発5/src/video_knowledge/pipeline/google_sheets.py |
| Google認証情報 | ~/.config/maekawa/google-credentials.json |
| APIキー | ~/.config/maekawa/api-keys.env |
| スプレッドシートID | 1bW_qb13p747xoa2yf7RHaccNVTFCMxV8a5CjGdNqI6I |
| スプシタブ名 | 【インタビュー対談動画】管理（gid: 600901662） |
| GitHub Pagesオーナー | 38maekawa-create |
