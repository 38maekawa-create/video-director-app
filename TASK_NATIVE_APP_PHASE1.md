# タスク指示書: 映像ディレクションエージェント ネイティブアプリ Phase 1

## 目的
映像ディレクションエージェント（AI開発10）をネイティブiOSアプリ化する。
なおとさん＋パグさん（編集者）の2ユーザーがスマホからYouTube素材（サムネ指示書・タイトル案・概要欄）を閲覧・編集できるようにする。

## 背景
- 現在のWebアプリ（PWA）は繋ぎ。本命はネイティブiOSアプリ
- SwiftUIプロジェクト（`VideoDirectorAgent/`）が既にビルド成功済み（MVVM構造、Netflix風ダークUI、5画面+モックデータ）
- YouTube素材3機能（サムネ指示書・タイトル案・概要欄）のPython生成パイプラインは実装済み
- **バックエンドはMac常駐 FastAPI + SQLite**（外部サービス不要、ブラウザ操作不要で全て完結）

## 全体工程における位置づけ
Phase 1（本タスク）→ Phase 2（リアルタイム同期+編集強化）→ Phase 3（全画面実装+音声FB）→ Phase 4（品質向上+TestFlight）

Phase 1の完了により、モックデータからリアルデータへの切り替えが完了し、iPhoneからAPIサーバー経由でデータを閲覧・編集できる状態になる。

---

## 既に完了している作業（バティ副官Aが実施済み）

### ✅ APIサーバー + SQLiteデータベース（完成・動作確認済み）
- **APIサーバー**: `src/video_direction/integrations/api_server.py`（FastAPI、ポート8210）
- **データベース**: `~/AI開発10/.data/video_director.db`（SQLite、WALモード）
- **テストデータ**: Izuさんのプロジェクト+YouTube素材1件投入済み
- **launchd設定**: `com.maekawa.video-direction-api.plist`（自動起動用）

### ✅ APIエンドポイント一覧（全て疎通確認済み）
| メソッド | パス | 用途 |
|---------|------|------|
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/projects` | プロジェクト一覧 |
| GET | `/api/projects/{id}` | プロジェクト詳細 |
| POST | `/api/projects` | プロジェクト作成 |
| PUT | `/api/projects/{id}` | プロジェクト更新 |
| GET | `/api/projects/{id}/youtube-assets` | YouTube素材取得 |
| PUT | `/api/projects/{id}/youtube-assets` | YouTube素材UPSERT |
| PATCH | `/api/projects/{id}/youtube-assets/description` | 概要欄編集保存 |
| PATCH | `/api/projects/{id}/youtube-assets/title` | タイトル選択保存 |
| GET | `/api/projects/{id}/feedbacks` | FB一覧 |
| GET | `/api/feedbacks` | 全FB一覧 |

### ✅ サーバー起動方法
```bash
cd ~/AI開発10 && source venv/bin/activate && uvicorn src.video_direction.integrations.api_server:app --host 0.0.0.0 --port 8210
```

---

## Codex CLIがやるべき作業

### 1. Swift側の修正・追加

#### 1-1. SPM依存追加
XcodeプロジェクトのPackage.swift（またはXcode GUI設定）は不要。
標準のURLSessionでAPIサーバーと通信する（外部SDK不要）。

#### 1-2. Models/Models.swift — YouTube素材モデル追加 + Codable準拠

既存の `VideoProject` を `Codable` 準拠に変更。以下のモデルを追加:

```swift
// YouTube素材モデル
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
}

struct ThumbnailDesign: Codable {
    var overallConcept: String
    var fontSuggestion: String
    var backgroundSuggestion: String
    var zones: [ThumbnailZone]
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
```

CodingKeysは snake_case ↔ camelCase 変換に対応すること（JSONDecoder.keyDecodingStrategy = .convertFromSnakeCase）。

#### 1-3. Services/APIClient.swift — 新規作成

```swift
class APIClient: ObservableObject {
    static let shared = APIClient()
    // ローカルネットワーク内のMac APIサーバー
    private let baseURL = "http://mac-mini-m4.local:8210"
    // フォールバック
    private let fallbackURL = "http://localhost:8210"

    func fetchProjects() async throws -> [VideoProject] { ... }
    func fetchYouTubeAssets(projectId: String) async throws -> YouTubeAssets { ... }
    func updateDescription(projectId: String, edited: String, by: String) async throws { ... }
    func selectTitle(projectId: String, index: Int, editedTitle: String?, by: String) async throws { ... }
}
```

**注意**: iOSアプリからローカルネットワークのHTTPサーバーにアクセスするため、Info.plist に以下を追加:
```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
</dict>
```

#### 1-4. ViewModels/ProjectListViewModel.swift — API接続に差し替え

MockData.projects → APIClient.shared.fetchProjects() に差し替え。
APIからデータが取れない場合はフォールバックとしてMockDataを使用。

#### 1-5. Views/DirectionReportView.swift — タブ拡張

現在のタブ `["演出", "テロップ", "カメラ", "音声FB"]` を以下に拡張:
`["概要", "ディレクション", "YouTube素材", "素材", "編集後", "FB・評価", "ナレッジ"]`

「YouTube素材」タブでは `YouTubeAssetsView` を表示。

#### 1-6. Views/YouTubeAssetsView.swift — 新規作成（★ Phase 1のメイン成果物）

3セクション構成:

**セクション1: サムネイル指示書（閲覧のみ）**
- Z型4ゾーンを2×2グリッドで表示
- 各ゾーンに role（フック/人物+属性/コンテンツ要素/ベネフィット）を表示
- ゾーンごとに色分け（color_suggestion をbackground colorに使用）
- overall_concept、font_suggestion、background_suggestion を上部に表示

**セクション2: タイトル案（選択+編集）**
- カード形式で3-5案を縦並び表示
- recommended_index の案にゴールドバッジ「推奨」を付ける
- ラジオボタン選択
- 選択した案をインライン編集可能（TextField）
- 「このタイトルで確定」ボタン → API PATCH呼び出し

**セクション3: 概要欄（編集+コピー）**
- TextEditor でフルテキスト編集
- descriptionOriginal をデフォルト表示、edited があればそちらを表示
- 「コピー」ボタン（UIPasteboard → YouTube Studio貼り付け用）
- 「リセット」ボタン（AI生成版に戻す）
- 「確定保存」ボタン → API PATCH呼び出し
- lastEditedBy + updatedAt を表示（「パグさんが3分前に編集」）

Netflix風ダークUIで統一（AppTheme準拠）。

#### 1-7. MockData.swift — YouTube素材サンプルデータ追加

API未接続でもUIが確認できるように、MockDataにサンプルのYouTubeAssetsを追加。
APIサーバーのテストデータ（Izuさん）と同じ内容でOK。

### 2. Python側: main.py にAPI同期ステップ追加

`process_single_file()` の Step 5（スプシ連携）の後に Step 6 として追加:
```python
# Step 6: APIサーバーのSQLiteに同期
try:
    import urllib.request
    import json as json_module
    api_base = "http://localhost:8210"
    # プロジェクト作成/更新
    project_data = { ... }  # video_dataから構築
    req = urllib.request.Request(
        f"{api_base}/api/projects",
        data=json_module.dumps(project_data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code == 409:  # 既存 → PUT で更新
            req.full_url = f"{api_base}/api/projects/{project_id}"
            req.method = "PUT"
            urllib.request.urlopen(req)

    # YouTube素材同期
    if thumbnail_design or title_proposals or video_description:
        assets_data = { ... }  # 生成結果から構築
        req = urllib.request.Request(
            f"{api_base}/api/projects/{project_id}/youtube-assets",
            data=json_module.dumps(assets_data).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT"
        )
        urllib.request.urlopen(req)
    print(f"  📊 APIサーバー同期完了")
except Exception as e:
    print(f"  ⚠️ APIサーバー同期スキップ: {e}")
```

### 3. 既存プロジェクトデータの一括投入スクリプト

既存の30件程度のプロジェクト（video_transcriptsからのマークダウンファイル）をAPIサーバーに一括投入するスクリプトを作成:
`scripts/seed_api_data.py`

---

## 完了条件と検証

1. **Swift ビルド成功**: Xcodeで `VideoDirectorAgent.xcodeproj` がビルドエラーなし
2. **YouTube素材タブ表示**: シミュレータでレポート詳細画面に「YouTube素材」タブが表示され、サムネ指示書（4ゾーングリッド）・タイトル案（3カード）・概要欄（テキストエディタ）が閲覧できる
3. **APIクライアント動作**: シミュレータからAPIサーバー（localhost:8210）にアクセスしてデータが取得できる
4. **タイトル選択**: タイトル案を選択→確定でAPIに保存される
5. **概要欄編集**: テキスト編集→確定でAPIに保存される。コピーボタンでクリップボードにコピーされる
6. **既存テスト**: `source venv/bin/activate && python -m pytest tests/ -v` で250件全パス（後方互換性）

## 注意事項

- **Google管理コンソールのブラウザ自動操作は禁止**（CLAUDE.mdルール）
- **既存のNetflix風デザイン**: AppTheme（Models.swift内）のカラーパレット・フォントスタイルを厳守。新規UIも統一する
- **APIサーバーは既に動作確認済み**。Codex CLIが改めてサーバーを作り直す必要はない
- **サーバー起動**: `cd ~/AI開発10 && source venv/bin/activate && uvicorn src.video_direction.integrations.api_server:app --host 0.0.0.0 --port 8210`
- **テストデータ確認**: `curl -s http://localhost:8210/api/projects/p-izu/youtube-assets | python3 -m json.tool`

## 既存ファイルパス

```
Swift側（拡張ベース）:
  ~/AI開発10/VideoDirectorAgent/VideoDirectorAgent/
    ├── Models/Models.swift                    ← YouTube素材モデル追加 + Codable準拠
    ├── Models/MockData.swift                  ← YouTube素材サンプル追加
    ├── Views/DirectionReportView.swift        ← タブ拡張（4→7）
    ├── Views/YouTubeAssetsView.swift          ← 新規作成（★メイン成果物）
    ├── Views/RootTabView.swift                ← 変更なし
    ├── Views/ProjectListView.swift            ← API接続
    ├── ViewModels/ProjectListViewModel.swift   ← APIクライアント化
    └── Services/APIClient.swift               ← 新規作成

Python側（既に完成済み + 追加）:
  ~/AI開発10/src/video_direction/
    ├── main.py                                ← API同期ステップ追加
    └── integrations/
        ├── api_server.py                      ← ✅ 完成済み（触らない）
        └── sheets_manager.py                  ← 参照パターン
```
