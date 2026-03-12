# タスク指示書: 映像ディレクションエージェント ネイティブアプリ Phase 1

## 目的
映像ディレクションエージェント（AI開発10）をネイティブiOSアプリ化する。
なおとさん＋パグさん（編集者）の2ユーザーがスマホからYouTube素材（サムネ指示書・タイトル案・概要欄）を閲覧・編集できるようにする。

## 背景
- 現在のWebアプリ（PWA）は繋ぎ。本命はネイティブiOSアプリ
- SwiftUIプロジェクト（`VideoDirectorAgent/`）が既にビルド成功済み（MVVM構造、Netflix風ダークUI、5画面+モックデータ）
- YouTube素材3機能（サムネ指示書・タイトル案・概要欄）のPython生成パイプラインは実装済み
- **バックエンドはSupabase**（Firebase断念。GoogleコンソールのブラウザアクセスがブロックされるためGoogle系サービスは使わない）
- Supabase CLI インストール済み（v2.75.0）。ただしアクセストークン未設定（ユーザーにブラウザでトークン取得を依頼する必要あり）

## 全体工程における位置づけ
Phase 1（本タスク）→ Phase 2（YouTube素材閲覧・編集）→ Phase 3（全画面実装+音声FB）→ Phase 4（品質向上+TestFlight）

Phase 1の完了により、モックデータからリアルデータへの切り替えが完了し、2台のiPhoneで同じデータを閲覧できる状態になる。

## 設計書
`~/.claude/plans/fluffy-pondering-fiddle.md` を参照（全Phase分の設計書）。
**注意: 設計書はFirebaseベースで書かれているが、Supabaseに読み替えること。**

---

## Phase 1 実装内容

### 0. Supabase セットアップ（ユーザー操作が必要）

ユーザーに以下を依頼する:
1. https://supabase.com/dashboard にアクセス（GitHubアカウントでログイン可能、Google不要）
2. 新規プロジェクト作成（名前: `video-director-agent`、リージョン: Northeast Asia (Tokyo)、パスワード: 任意）
3. Settings → API → Access Tokens で「Generate new token」
4. トークンと、Project URL（`https://xxxxx.supabase.co`）とanon keyを共有してもらう

取得できたら:
```bash
supabase login --token <トークン>
```

### 1. Supabase テーブル設計

以下のSQLでテーブルを作成（Supabase SQL Editorまたはマイグレーション）:

```sql
-- プロジェクト
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  guest_name TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'directed',
  shoot_date TEXT,
  guest_age INTEGER,
  guest_occupation TEXT,
  quality_score INTEGER,
  has_unsent_feedback BOOLEAN DEFAULT FALSE,
  unreviewed_count INTEGER DEFAULT 0,
  direction_report_url TEXT,
  source_video JSONB,
  edited_video JSONB,
  feedback_summary JSONB,
  knowledge JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- YouTube素材
CREATE TABLE youtube_assets (
  id SERIAL PRIMARY KEY,
  project_id TEXT REFERENCES projects(id),
  thumbnail_design JSONB,
  title_proposals JSONB,
  description_original TEXT,
  description_edited TEXT,
  description_finalized_at TIMESTAMPTZ,
  description_finalized_by TEXT,
  selected_title_index INTEGER,
  edited_title TEXT,
  last_edited_by TEXT,
  generated_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id)
);

-- フィードバック
CREATE TABLE feedbacks (
  id SERIAL PRIMARY KEY,
  project_id TEXT REFERENCES projects(id),
  timestamp_mark TEXT,
  raw_voice_text TEXT,
  converted_text TEXT,
  category TEXT,
  priority TEXT DEFAULT 'medium',
  created_by TEXT,
  is_sent BOOLEAN DEFAULT FALSE,
  editor_status TEXT DEFAULT '未対応',
  learning_effect TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS（Row Level Security）有効化
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE youtube_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedbacks ENABLE ROW LEVEL SECURITY;

-- 全ユーザーに読み書き許可（2ユーザーだけなので簡易設定）
CREATE POLICY "Allow all" ON projects FOR ALL USING (true);
CREATE POLICY "Allow all" ON youtube_assets FOR ALL USING (true);
CREATE POLICY "Allow all" ON feedbacks FOR ALL USING (true);
```

### 2. Swift側の修正・追加

#### 2-1. SPMで Supabase Swift SDK を追加
XcodeプロジェクトにSPM依存を追加:
- `https://github.com/supabase/supabase-swift` → Supabase パッケージ

#### 2-2. Models/Models.swift — YouTube素材モデル追加 + Codable準拠

`VideoProject` を `Codable` 準拠に変更し、以下のモデルを追加:

```swift
struct YouTubeAssets: Codable {
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
}

struct TitleCandidate: Codable, Identifiable {
    var id: String { title }
    var title: String
    var targetSegment: String
    var appealType: String
    var rationale: String
}
```

#### 2-3. Services/SupabaseManager.swift — 新規作成

```swift
import Supabase

class SupabaseManager: ObservableObject {
    static let shared = SupabaseManager()

    private let client = SupabaseClient(
        supabaseURL: URL(string: "YOUR_SUPABASE_URL")!,  // ユーザーから取得後に差し替え
        supabaseKey: "YOUR_ANON_KEY"                       // ユーザーから取得後に差し替え
    )

    // プロジェクト一覧取得
    func fetchProjects() async throws -> [VideoProject] { ... }

    // リアルタイムリスナー（Supabase Realtime）
    func observeYouTubeAssets(projectId: String, onChange: @escaping (YouTubeAssets) -> Void) { ... }

    // YouTube素材の更新
    func updateYouTubeAssets(projectId: String, assets: YouTubeAssets) async throws { ... }

    // タイトル選択の保存
    func selectTitle(projectId: String, index: Int, editedTitle: String?) async throws { ... }

    // 概要欄編集の保存
    func updateDescription(projectId: String, edited: String, by: String) async throws { ... }
}
```

#### 2-4. ViewModels/ProjectListViewModel.swift — Supabase接続に差し替え

MockData.projects → SupabaseManager.shared.fetchProjects() に差し替え。
Supabaseからデータが取れない場合はフォールバックとしてMockDataを使用。

#### 2-5. Views/DirectionReportView.swift — タブ拡張

現在のタブ `["演出", "テロップ", "カメラ", "音声FB"]` を以下に拡張:
`["概要", "ディレクション", "YouTube素材", "素材", "編集後", "FB・評価", "ナレッジ"]`

「YouTube素材」タブでは `YouTubeAssetsView` を表示。

#### 2-6. Views/YouTubeAssetsView.swift — 新規作成

3セクション構成:
1. **サムネイル指示書**: Z型4ゾーンを2×2グリッドで表示（閲覧のみ）
2. **タイトル案**: カード選択（ラジオ）+ インライン編集
3. **概要欄**: TextEditor + コピーボタン + リセットボタン + 確定ボタン

Netflix風ダークUIで統一（AppTheme準拠）。

### 3. Python側の修正・追加

#### 3-1. supabase_syncer.py — 新規作成

パス: `src/video_direction/integrations/supabase_syncer.py`
参照パターン: `src/video_direction/integrations/sheets_manager.py`

```bash
# venv内にsupabase Pythonクライアントをインストール
source ~/AI開発10/venv/bin/activate && pip install supabase
```

```python
from supabase import create_client

class SupabaseSyncer:
    def __init__(self):
        # SUPABASE_URL, SUPABASE_KEY を環境変数 or ~/.config/maekawa/api-keys.env から取得
        ...

    def sync_project(self, video_data, classification, income_eval,
                     thumbnail_design, title_proposals, video_description,
                     direction_url: str) -> bool:
        """プロジェクトデータをSupabaseに同期"""
        ...

    def sync_youtube_assets(self, project_id: str,
                           thumbnail_design, title_proposals, video_description) -> bool:
        """YouTube素材のみをSupabaseに同期"""
        ...
```

#### 3-2. main.py — Supabase書き込みステップ追加

`process_single_file()` の Step 5（スプシ連携）の後に Step 6 として追加:
```python
# Step 6: Supabase同期
try:
    from .integrations.supabase_syncer import SupabaseSyncer
    syncer = SupabaseSyncer()
    syncer.sync_project(...)
    print(f"  📊 Supabase同期完了")
except Exception as e:
    print(f"  ⚠️ Supabase同期スキップ: {e}")
```

### 4. MockData拡張（開発用）

MockData.swift にYouTube素材のサンプルデータを追加（Supabase未接続でもUIが確認できるように）。

---

## 完了条件と検証

1. **Supabase接続**: テーブル作成完了、Pythonからデータ読み書きできる
2. **Swift ビルド成功**: Xcodeで `VideoDirectorAgent.xcodeproj` がビルドエラーなし
3. **YouTube素材タブ表示**: シミュレータでレポート詳細画面に「YouTube素材」タブが表示され、モックデータのサムネ指示書・タイトル案・概要欄が閲覧できる
4. **Python supabase_syncer**: `python -c "from src.video_direction.integrations.supabase_syncer import SupabaseSyncer; print('OK')"` が成功
5. **既存テスト**: `source venv/bin/activate && python -m pytest tests/ -v` で250件全パス（後方互換性）

## 注意事項

- **Google管理コンソールのブラウザ自動操作は禁止**（CLAUDE.mdルール）。Firebase/GCP Console等をブラウザで自動操作しないこと
- **既存のNetflix風デザイン**: AppTheme（Models.swift内）のカラーパレット・フォントスタイルを厳守。新規UIも統一する
- **Supabaseのアクセス情報**: ユーザーにブラウザでSupabase Dashboardにアクセスしてもらい、Project URL・anon key・Access Tokenを取得する必要がある
- **既にインストール済み**: Supabase CLI v2.75.0、firebase-admin（venv内）
