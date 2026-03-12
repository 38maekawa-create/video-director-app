# タスク指示書: 映像ディレクションエージェント ネイティブアプリ Phase 1

## 目的
映像ディレクションエージェント（AI開発10）をネイティブiOSアプリ化する。
なおとさん＋パグさん（編集者）の2ユーザーがスマホからYouTube素材（サムネ指示書・タイトル案・概要欄）を閲覧・編集できるようにする。

## 背景
- 現在のWebアプリ（PWA）は繋ぎ。本命はネイティブiOSアプリ
- SwiftUIプロジェクト（`VideoDirectorAgent/`）が既にビルド成功済み（MVVM構造、Netflix風ダークUI、5画面+モックデータ）
- YouTube素材3機能（サムネ指示書・タイトル案・概要欄）のPython生成パイプラインは実装済み
- 2ユーザー間のリアルタイム同期にFirebase Realtime Databaseを使用
- Firebase CLIはインストール済み（`npm install -g firebase-tools` 完了）

## 全体工程における位置づけ
Phase 1（本タスク）→ Phase 2（YouTube素材閲覧・編集）→ Phase 3（全画面実装+音声FB）→ Phase 4（品質向上+TestFlight）

Phase 1の完了により、モックデータからリアルデータへの切り替えが完了し、2台のiPhoneで同じデータを閲覧できる状態になる。

## 詳細計画
`~/.claude/plans/fluffy-pondering-fiddle.md` を参照（全Phase分の設計書）

---

## Phase 1 実装内容

### 1. Firebase初期セットアップ

Firebase CLIでプロジェクト作成・設定する（GCPコンソールのブラウザアクセスはブロックされる可能性があるため、CLIベースで行う）。

```bash
firebase login  # ブラウザ認証
firebase projects:create video-director-agent --display-name "Video Director Agent"
firebase init database  # Realtime Database初期化
```

セキュリティルール（`database.rules.json`）:
```json
{
  "rules": {
    "projects": {
      ".read": "auth != null",
      ".write": "auth != null"
    },
    "feedbacks": {
      ".read": "auth != null",
      ".write": "auth != null"
    }
  }
}
```

### 2. Swift側の修正・追加

#### 2-1. SPMでFirebase SDKを追加
XcodeプロジェクトにSPM依存を追加:
- `https://github.com/firebase/firebase-ios-sdk` → FirebaseDatabase, FirebaseAuth

#### 2-2. Models/Models.swift — YouTube素材モデル追加 + Codable準拠

`VideoProject` に以下を追加:
```swift
// YouTube素材
struct YouTubeAssets: Codable {
    var thumbnailDesign: ThumbnailDesign?
    var titleProposals: TitleProposals?
    var description: VideoDescriptionData?
    var generatedAt: String?
}

struct ThumbnailDesign: Codable {
    var overallConcept: String
    var fontSuggestion: String
    var backgroundSuggestion: String
    var zones: [ThumbnailZone]
}

struct ThumbnailZone: Codable, Identifiable {
    var id: String { role }
    var role: String        // "フック", "人物+属性", "コンテンツ要素", "ベネフィット"
    var content: String
    var colorSuggestion: String
    var notes: String
}

struct TitleProposals: Codable {
    var candidates: [TitleCandidate]
    var recommendedIndex: Int
    var selectedIndex: Int?      // ユーザー選択
    var editedTitle: String?     // ユーザー編集
}

struct TitleCandidate: Codable, Identifiable {
    var id: String { title }
    var title: String
    var targetSegment: String
    var appealType: String
    var rationale: String
}

struct VideoDescriptionData: Codable {
    var original: String        // AI生成版
    var edited: String?         // ユーザー編集版
    var finalizedAt: String?
    var finalizedBy: String?    // "naoto" or "pag"
}
```

既存の `VideoProject` を `Codable` 準拠に変更し、`youtubeAssets: YouTubeAssets?` フィールドを追加。

#### 2-3. Services/FirebaseManager.swift — 新規作成

```swift
import FirebaseDatabase

class FirebaseManager: ObservableObject {
    static let shared = FirebaseManager()
    private let ref = Database.database().reference()

    // プロジェクト一覧のリアルタイムリスナー
    func observeProjects(completion: @escaping ([VideoProject]) -> Void) { ... }

    // YouTube素材の更新
    func updateYouTubeAssets(projectId: String, assets: YouTubeAssets) { ... }

    // タイトル選択の保存
    func selectTitle(projectId: String, index: Int, editedTitle: String?) { ... }

    // 概要欄編集の保存
    func updateDescription(projectId: String, edited: String, by: String) { ... }
}
```

#### 2-4. ViewModels/ProjectListViewModel.swift — Firebase接続に差し替え

MockData.projects → FirebaseManager.shared.observeProjects() に差し替え。
Firebaseからデータが取れない場合はフォールバックとしてMockDataを使用（開発中の安全策）。

#### 2-5. Views/DirectionReportView.swift — タブ拡張

現在のタブ `["演出", "テロップ", "カメラ", "音声FB"]` を以下に拡張:
`["概要", "ディレクション", "YouTube素材", "素材", "編集後", "FB・評価", "ナレッジ"]`

「YouTube素材」タブでは `YouTubeAssetsView` を表示。

#### 2-6. Views/YouTubeAssetsView.swift — 新規作成（Phase 2のメイン画面）

3セクション構成:
1. **サムネイル指示書**: Z型4ゾーンを2×2グリッドで表示（閲覧のみ）
2. **タイトル案**: カード選択（ラジオ）+ インライン編集
3. **概要欄**: TextEditor + コピーボタン + リセットボタン + 確定ボタン

Netflix風ダークUIで統一（AppTheme準拠）。

### 3. Python側の修正・追加

#### 3-1. firebase_syncer.py — 新規作成

パス: `src/video_direction/integrations/firebase_syncer.py`
参照パターン: `src/video_direction/integrations/sheets_manager.py`

```python
import firebase_admin
from firebase_admin import credentials, db

class FirebaseSyncer:
    def __init__(self):
        # ~/.config/maekawa/google-credentials.json のサービスアカウントを使用
        # （既にteko-threads-autoプロジェクト用に存在）
        # ※Firebase Realtime DatabaseのURLは設定ファイルから取得
        ...

    def sync_project(self, video_data, classification, income_eval,
                     thumbnail_design, title_proposals, video_description,
                     direction_url: str) -> bool:
        """プロジェクトデータをFirebaseに同期"""
        ...

    def sync_youtube_assets(self, project_id: str,
                           thumbnail_design, title_proposals, video_description) -> bool:
        """YouTube素材のみをFirebaseに同期"""
        ...
```

#### 3-2. main.py — Firebase書き込みステップ追加

`process_single_file()` の Step 5（スプシ連携）の後に Step 6 として追加:
```python
# Step 6: Firebase同期
try:
    from .integrations.firebase_syncer import FirebaseSyncer
    firebase = FirebaseSyncer()
    firebase.sync_project(...)
    print(f"  🔥 Firebase同期完了")
except Exception as e:
    print(f"  ⚠️ Firebase同期スキップ: {e}")
```

### 4. MockData拡張（開発用）

MockData.swift にYouTube素材のサンプルデータを追加:
```swift
static let sampleYouTubeAssets = YouTubeAssets(
    thumbnailDesign: ThumbnailDesign(
        overallConcept: "年収3000万×元アクセンチュアの知的なイメージ",
        fontSuggestion: "ゴシック太字",
        backgroundSuggestion: "ダークブルーグラデーション",
        zones: [
            ThumbnailZone(role: "フック", content: "年収3000万の真実", ...),
            ThumbnailZone(role: "人物+属性", content: "30代・元アクセンチュア", ...),
            ...
        ]
    ),
    titleProposals: TitleProposals(
        candidates: [
            TitleCandidate(title: "年収3000万30代元アクセンチュア...", ...),
            ...
        ],
        recommendedIndex: 0
    ),
    description: VideoDescriptionData(
        original: "チャンネル登録はこちらから▼\n...",
        edited: nil
    )
)
```

---

## 完了条件と検証

1. **Firebase接続**: `firebase projects:list` でプロジェクトが表示される
2. **Swift ビルド成功**: Xcodeで `VideoDirectorAgent.xcodeproj` がビルドエラーなし
3. **YouTube素材タブ表示**: シミュレータでレポート詳細画面に「YouTube素材」タブが表示され、モックデータのサムネ指示書・タイトル案・概要欄が閲覧できる
4. **Python firebase_syncer**: `python -c "from src.video_direction.integrations.firebase_syncer import FirebaseSyncer; print('OK')"` が成功
5. **既存テスト**: `python -m pytest tests/ -v` で250件全パス（後方互換性）

## 注意事項

- **GCPコンソールブロック問題**: Google Cloud Console、Firebase Console がブラウザからブロックされる可能性あり。Firebase CLIでの操作を優先する
- **既存のサービスアカウント**: `~/.config/maekawa/google-credentials.json` にteko-threads-auto用のサービスアカウントが既存。Firebaseプロジェクトが同じGCPプロジェクト内であれば流用可能
- **GEMINI_API_KEY**: `~/teko-content-pipeline/.env` にGemini用APIキー（AIza形式）があるが、これはFirebase Realtime DBとは別物。Firebase Admin SDKはサービスアカウントで認証する
- **既存のNetflix風デザイン**: AppTheme（Models.swift内）のカラーパレット・フォントスタイルを厳守。新規UIも統一する
