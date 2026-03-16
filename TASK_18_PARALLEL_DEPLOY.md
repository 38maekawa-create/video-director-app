# 18本並列デプロイ — タスク指示書

> 作成: 2026-03-16
> 構成: 3垢(Claude MAX / Claude Pro / ChatGPT Pro) × 3デバイス × 2モデル/垢 = 18本
> 各デバイス: Opus 4本 + GPT 2本

## ファイル競合回避ルール（最重要）

- **api_server.py は直接編集しない**。新エンドポイントは別モジュールに切り出し、最後にルーター登録を1本が行う
- **prompts.py は担当プロンプトのみ触る**。他のプロンプト定数には触れない
- **同一Swiftファイルを2人以上が触らない**
- 新規ファイル作成は自由。既存ファイル編集は担当以外禁止

---

## Mac 1（API・バックエンド中心）

### [M1-1] MAX Opus #1: ディレクションレポート手修正API
- **目的**: なおとさん・パグさんがアプリからディレクションレポートを手修正→API保存できるようにする
- **背景**: 現在レポートはHTML生成のみで編集不可。手修正→保存→diff分析→学習の入口になる
- **全体工程**: 手修正API（ここ）→ diff分析(M1-4) → 学習DB蓄積(M1-4) → iOS UI(M2-1)
- **作成ファイル**: `src/video_direction/integrations/edit_direction_routes.py`（新規）
- **エンドポイント**:
  - `PUT /api/v1/projects/{project_id}/direction-report` — レポート内容の更新
  - `GET /api/v1/projects/{project_id}/direction-report/history` — 編集履歴
  - `GET /api/v1/projects/{project_id}/direction-report/diff` — 元生成 vs 手修正のdiff
- **DB**: `direction_edits`テーブル新規作成（project_id, original_content, edited_content, edited_by, edited_at, diff_summary）
- **完了条件**: エンドポイント3本が動作し、curlでCRUD確認済み。テストファイル `tests/test_edit_direction_api.py` 作成済み

### [M1-2] MAX Opus #2: タイトル・概要欄・サムネ手修正API
- **目的**: タイトル案・概要欄・サムネ指示書もアプリから手修正→保存できるようにする
- **背景**: ディレクションレポートと同様に、全生成物を手修正可能にする
- **全体工程**: API（ここ）→ diff分析(M1-4) → 学習DB蓄積(M1-4) → iOS UI(M2-2, M2-3)
- **作成ファイル**: `src/video_direction/integrations/edit_assets_routes.py`（新規）
- **エンドポイント**:
  - `PUT /api/v1/projects/{project_id}/title` — タイトル案の更新
  - `PUT /api/v1/projects/{project_id}/description` — 概要欄の更新
  - `PUT /api/v1/projects/{project_id}/thumbnail-instruction` — サムネ指示書の更新
  - 各エンドポイントに `GET .../history` と `GET .../diff` も付ける
- **DB**: `asset_edits`テーブル新規作成（project_id, asset_type[title/description/thumbnail], original_content, edited_content, edited_by, edited_at, diff_summary）
- **完了条件**: エンドポイント群が動作し、curlでCRUD確認済み。テスト作成済み

### [M1-3] Pro Opus #1: 手修正diff分析エンジン
- **目的**: 手修正と元生成のdiffを分析し、「何を変えたか」「どんなパターンの修正か」を構造化する
- **背景**: 修正→保存だけでは学習にならない。diff分析が学習の核心
- **全体工程**: API(M1-1,M1-2) → diff分析（ここ）→ 学習DB蓄積(M1-4)
- **作成ファイル**: `src/video_direction/analyzer/edit_diff_analyzer.py`（新規）
- **機能**:
  - `analyze_direction_diff(original, edited)` → 修正カテゴリ分類（演出変更/テロップ修正/構成変更/トーン修正等）
  - `analyze_title_diff(original, edited)` → タイトル修正パターン（フック変更/属性強調変更/引用フレーズ変更等）
  - `analyze_description_diff(original, edited)` → 概要欄修正パターン
  - `analyze_thumbnail_diff(original, edited)` → サムネ修正パターン（ゾーン配置変更/フック変更等）
  - LLM（Claude Sonnet）でdiff内容を構造化分析
- **出力形式**: `EditDiffResult(category, changes[], severity, learning_signal)`
- **完了条件**: 4種類の分析関数が動作、テスト作成済み

### [M1-4] Pro Opus #2: 学習DB蓄積ロジック拡張
- **目的**: diff分析結果を既存の学習エンジン（FeedbackLearner/VideoLearner）に統合し、次回生成に反映する
- **背景**: 既存のFeedbackLearnerはフィードバックパターンのみ学習。手修正パターンも学習対象に加える
- **全体工程**: diff分析(M1-3) → 学習DB蓄積（ここ）→ 次回生成で反映（direction_generator既存ロジック活用）
- **編集ファイル**: `src/video_direction/tracker/feedback_learner.py`（拡張）
- **作成ファイル**: `src/video_direction/tracker/edit_learner.py`（新規）
- **機能**:
  - `EditLearner` クラス: FeedbackLearnerと同じインターフェース（ingest, get_active_rules, get_insights）
  - `ingest_edit(project_id, asset_type, diff_result)` → パターン抽出・蓄積
  - confidence計算: 同じ修正パターンが3回以上 → ルール化（confidence = frequency / 3.0）
  - 永続化: `.data/learning/edit_patterns.json`, `.data/learning/edit_rules.json`
- **direction_generatorとの統合**: `get_active_rules()` でedit_rulesも返し、ディレクション生成時に反映
- **完了条件**: EditLearnerが動作、テスト作成、feedback_learnerとの統合確認

### [M1-5] GPT #1: タイトルプロンプト改修
- **目的**: TEKOチャンネルの実運用パターンに合わせてタイトル生成プロンプトを修正する
- **背景**: 現プロンプトは「名前は出さない」「30文字前後」だが、実際のTEKOは実名+さん表記、60-80文字
- **全体工程**: プロンプト改修（ここ）→ バッチ再生成(M3-4)で検証
- **編集ファイル**:
  - `src/video_direction/knowledge/prompts.py` の `TITLE_GENERATION_PROMPT`（L81-133のみ。他のプロンプトには触れないこと）
  - `src/video_direction/analyzer/title_generator.py` の `_fallback_titles()`（L127-169）
- **改修内容**:
  - 構造テンプレート: `年収[金額][年代][職業]「[パンチライン]」[名前]さんが語る[テーマ]とは？【TEKO独占インタビュー】`
  - 実名+さん表記に変更（モザイク動画でもYouTubeタイトルでは実名掲載）
  - 長さ制限を60-80文字に変更
  - 引用フレーズ（本人の肉声・パンチライン）の抽出指示を追加
  - 【TEKO独占インタビュー】固定タグ
- **NGリスト（変更禁止）**: THUMBNAIL_DESIGN_PROMPT, DESCRIPTION_GENERATION_PROMPT には触れない
- **完了条件**: プロンプト改修済み、title_generatorフォールバック更新済み

### [M1-6] GPT #2: 概要欄プロンプト改修
- **目的**: TEKOチャンネルの実運用パターンに合わせて概要欄生成プロンプトを修正する
- **背景**: 現プロンプトはタイムスタンプ・ハッシュタグを含むが、TEKOは一切使っていない。CTA配置順序も逆
- **全体工程**: プロンプト改修（ここ）→ バッチ再生成(M3-4)で検証
- **編集ファイル**:
  - `src/video_direction/knowledge/prompts.py` の `DESCRIPTION_GENERATION_PROMPT`（L136-190のみ。他のプロンプトには触れないこと）
  - `src/video_direction/analyzer/description_writer.py` の `_fallback_description()`（L114-185）
- **改修内容**:
  - CTA冒頭配置: 「チャンネル登録はこちらから▼」を最先頭に
  - ブランド紹介: 「【TEKO公式メディア】」+ メディア説明文
  - LINE公式CTA: 「【運営者：プロパー八重洲とLINEで繋がりませんか？】」
  - タイムスタンプ削除（TEKO未使用）
  - ハッシュタグ削除（TEKO未使用）
  - Instagram/X/TikTokリンク削除（LINE専構成）
  - ゲスト実名+さん表記で記載
- **NGリスト（変更禁止）**: TITLE_GENERATION_PROMPT, THUMBNAIL_DESIGN_PROMPT には触れない
- **完了条件**: プロンプト改修済み、description_writerフォールバック更新済み

---

## Mac 2（iOS・フロントエンド + 分析プロンプト強化）

### [M2-1] MAX Opus #1: iOS ディレクションレポート手修正UI
- **目的**: DirectionReportViewにテキスト編集機能を追加し、ユーザーがレポート内容を手修正→API保存できるようにする
- **背景**: 現在WebViewで表示のみ。編集可能なUIが必要
- **全体工程**: API(M1-1)が先行 → iOS UI（ここ）
- **作成ファイル**: `VideoDirectorAgent/Views/DirectionEditView.swift`（新規）
- **作成ファイル**: `VideoDirectorAgent/ViewModels/DirectionEditViewModel.swift`（新規）
- **機能**:
  - レポート表示 → 「編集」ボタン → テキスト編集モード
  - セクションごとの編集（演出ディレクション、テロップ、BGM等）
  - 保存ボタン → PUT /api/v1/projects/{id}/direction-report → 成功表示
  - diff表示（元生成 vs 手修正）
  - 編集者名の入力（なおとさん/パグさん）
- **APIClient拡張**: M2-4が担当。ここではViewModelからの呼び出しのみ
- **完了条件**: 編集→保存→diff表示の一連フローが動作

### [M2-2] MAX Opus #2: iOS タイトル・概要欄手修正UI
- **目的**: タイトル案と概要欄をアプリから編集→保存できるUIを作る
- **背景**: ディレクションレポートと同様に、全生成物を手修正可能にする
- **全体工程**: API(M1-2)が先行 → iOS UI（ここ）
- **作成ファイル**: `VideoDirectorAgent/Views/TitleDescriptionEditView.swift`（新規）
- **作成ファイル**: `VideoDirectorAgent/ViewModels/TitleDescriptionEditViewModel.swift`（新規）
- **機能**:
  - タイトル案表示 → インライン編集 → 保存
  - 概要欄表示 → テキストエリア編集 → 保存
  - 現在のタイトル・概要欄と手修正版のdiff表示
  - 複数タイトル案の中から選択して編集も可能
- **完了条件**: タイトル・概要欄の編集→保存→diff表示が動作

### [M2-3] Pro Opus #1: iOS サムネ指示書手修正UI
- **目的**: サムネ指示書（Z型4ゾーン構成）をアプリから編集→保存できるUIを作る
- **背景**: サムネ指示書はZ理論に基づく構造化データ。ゾーンごとの編集UIが必要
- **全体工程**: API(M1-2)が先行 → iOS UI（ここ）
- **作成ファイル**: `VideoDirectorAgent/Views/ThumbnailEditView.swift`（新規）
- **作成ファイル**: `VideoDirectorAgent/ViewModels/ThumbnailEditViewModel.swift`（新規）
- **機能**:
  - Z型4ゾーン（左上フック/右上人物/斜め降下コンテンツ/右下ベネフィット）をカード表示
  - 各ゾーンをタップ → 編集モード（テキスト・画像指示・フォント指示）
  - 全体コンセプト・フォント提案・背景提案の編集
  - 保存 → API → diff表示
- **完了条件**: 4ゾーンの編集→保存→diff表示が動作

### [M2-4] Pro Opus #2: iOS APIClient拡張 + 修正学習可視化
- **目的**: 新エンドポイント対応のAPIClient拡張 + FeedbackHistoryに修正学習の可視化を追加
- **背景**: M1-1,M1-2で作られるAPIにiOSから接続する必要がある。また修正が学習に反映されている様子を可視化する
- **編集ファイル**: `VideoDirectorAgent/Services/APIClient.swift`（新規メソッド追加のみ）
- **編集ファイル**: `VideoDirectorAgent/Views/FeedbackHistoryView.swift`（学習可視化セクション追加）
- **機能**:
  - APIClient: `updateDirectionReport()`, `updateTitle()`, `updateDescription()`, `updateThumbnailInstruction()`, `fetchEditHistory()`, `fetchEditDiff()`
  - FeedbackHistoryView: 「学習効果」セクション追加 — 修正パターンの蓄積数・ルール化数・次回生成への反映予定
- **完了条件**: 全APIメソッドが動作、学習可視化が表示される

### [M2-5] GPT #1: トラッキング分析プロンプト強化（direction_generator）
- **目的**: ディレクション生成の演出・映像分析粒度を強化する
- **背景**: 現プロンプトは「一般的な映像編集原則」に基づいており、TEKO対談の層別・属性別のディレクション判断パターンが不足
- **編集ファイル**: `src/video_direction/analyzer/direction_generator.py`（L400-425のLLMプロンプト部分のみ）
- **改修内容**:
  - ゲスト層別（tier a/b/c）の訴求軸分岐ロジック追加
  - ゲストの「強さの根拠」（企業ブランド/年収/転職実績/副業成功等）ごとの強調ポイント明示
  - ハイライト密度スコア（密集/散在）の分析指示
  - タイムラインコンテキスト（全体尺、ハイライト間のギャップ）の注入
  - 過去FB学習ルール活用時の「なぜこのゲストにこのルールが有効か」の演出ロジック明示
- **NGリスト**: _apply_learned_rules()等のロジック部分は触らない。LLMプロンプト文字列のみ改修
- **完了条件**: プロンプト改修済み、手動テストで出力品質改善を確認

### [M2-6] GPT #2: FB変換プロンプト強化（feedback_converter）
- **目的**: フィードバック変換の専門性をTEKO対談向けに強化する
- **背景**: 現在の変換ガイドは一般的な映像用語。TEKO対談の「綺麗さ」「テンポ」「色彩」基準が未定義
- **編集ファイル**: `src/video_direction/analyzer/feedback_converter.py`（カテゴリテンプレート部分のみ）
- **改修内容**:
  - TEKO対談向け「綺麗さ」の定義（肌色重視/背景統一/全体ニュアンス）
  - ゲスト層別の色彩・照明コンセプト差異の明示（tier a: 高級感・落ち着き / tier c: 親しみやすさ・エネルギー）
  - 「もっと〇〇して」系のあいまいFBをTEKO対談文脈で具体化するルール
- **NGリスト**: LLM呼び出しロジックは触らない。テンプレート・変換ガイド文字列のみ改修
- **完了条件**: 変換ガイド改修済み、手動テストで変換品質改善を確認

---

## Mac 3（サムネ強化・Vimeo・統合テスト）

### [M3-1] MAX Opus #1: サムネZ理論プロンプト強化
- **目的**: 青木さんのZ理論ナレッジをより深く反映し、サムネ指示書の品質を上げる
- **背景**: 既にZ理論プロンプトは統合済みだが、視認時間0.2秒制約・非言語要素戦略・層別フック戦略が弱い
- **ナレッジソース**:
  - `~/TEKO/knowledge/external-knowledge/2026.02.15_YouTube動画制作におけるサムネイル設計とクリエイティブディレクションの実践知.md`（639行）
  - `~/TEKO/knowledge/people/青木.md`
- **編集ファイル**:
  - `src/video_direction/knowledge/prompts.py` の `THUMBNAIL_DESIGN_PROMPT`（他のプロンプトには触れないこと）
  - `src/video_direction/analyzer/thumbnail_designer.py`（LLMプロンプト構築部分）
- **改修内容**:
  - 視認時間0.2秒制約の明記（「0.2秒で左上が勝負を決める」）
  - 非言語要素（ロゴ、アイコン、映像カット）の提案を明示的に指示
  - 層別フック戦略: tier a（数字+権威性）、tier b（ストーリー+共感）、tier c（行動のきっかけ+等身大感）
  - サキちゃん動画の成功パターンを参考例として注入
  - 「文字詰め込み禁止」の明記（非言語で伝える原則）
- **NGリスト**: TITLE_GENERATION_PROMPT, DESCRIPTION_GENERATION_PROMPT には触れない
- **完了条件**: プロンプト改修済み、手動テストで指示書品質改善を確認

### [M3-2] MAX Opus #2: Vimeoマッチング改善
- **目的**: Vimeo未マッチメンバーの表記揺れ対応を改善する
- **背景**: 14名マッチ/15名未マッチ。大半はVimeo上に動画未アップだが、表記揺れで見つからないケースもある
- **編集ファイル**: `scripts/sync_vimeo_edited_videos.py`
- **改修内容**:
  - `extras`辞書の拡充（複合名の分割: 「さといも・トーマス」→「さといも」「トーマス」）
  - ひらがな/カタカナ/ローマ字の相互変換マッチング追加
  - Vimeo API取得時のステータスフィルタ緩和（draft, transcodingも表示）
  - マッチング結果の詳細レポート出力（マッチ理由・未マッチ理由を一覧表示）
  - Vimeo上の全動画タイトル一覧をダンプする`--list-all`オプション追加
- **完了条件**: スクリプト改修済み、マッチ率改善レポート出力

### [M3-3] Pro Opus #1: E2Eパイプライン拡張（手修正フロー統合）
- **目的**: E2Eパイプラインに手修正学習フローを統合し、修正→分析→学習→再生成の自動ループを構築する
- **背景**: 現E2EはFB→ディレクション生成→Vimeo投稿まで。手修正学習を加えて自己成長ループにする
- **編集ファイル**: `src/video_direction/integrations/api_server.py`（E2Eパイプラインセクションのみ。L2800-2950付近）
- **改修内容**:
  - E2Eパイプラインに「手修正学習ステップ」を追加（editがある場合はdiff分析→学習DB蓄積を挟む）
  - EditLearner(M1-4)のget_active_rules()をディレクション生成時に参照
  - パイプライン結果に「適用された修正学習ルール」を含める
- **完了条件**: E2Eパイプラインが手修正学習ルールを反映して生成できる

### [M3-4] Pro Opus #2: 修正プロンプトで29件バッチ再生成
- **目的**: プロンプト改修（M1-5, M1-6, M2-5, M2-6, M3-1）完了後に全29件を再生成し、品質改善を検証する
- **背景**: 全プロンプト改修後のアウトプット品質を全件で確認する。比較検証が目的
- **前提**: M1-5, M1-6, M2-5, M2-6, M3-1 の全完了後に実行（依存タスク）
- **使用スクリプト**: `scripts/batch_generate_directions.py --execute`
- **追加作業**:
  - 改修前（現在の29件）と改修後の出力を比較
  - タイトル案・概要欄・サムネ指示書の品質変化レポート
  - 問題があるプロジェクトの特定と報告
- **完了条件**: 29件再生成完了、品質比較レポート出力

### [M3-5] GPT #1: テスト作成（新エンドポイント群）
- **目的**: M1-1, M1-2, M1-3, M1-4 で作成される新機能のテストを作成する
- **前提**: M1-1〜M1-4 の完了後に実行（依存タスク）
- **作成ファイル**:
  - `tests/test_edit_direction_routes.py` — ディレクションレポート手修正APIテスト
  - `tests/test_edit_assets_routes.py` — タイトル・概要欄・サムネ手修正APIテスト
  - `tests/test_edit_diff_analyzer.py` — diff分析エンジンテスト
  - `tests/test_edit_learner.py` — 学習DB蓄積テスト
- **テスト方針**: 正常系 + エラー系 + 境界値。学習ルール生成の閾値テスト含む
- **完了条件**: 全テスト作成済み、pytest通過

### [M3-6] GPT #2: ルーター統合 + PROGRESS.md更新
- **目的**: M1-1, M1-2 で作成された別モジュールのルーターをapi_server.pyに登録し、全体を統合する
- **前提**: M1-1, M1-2 の完了後に実行（依存タスク）
- **編集ファイル**: `src/video_direction/integrations/api_server.py`（importとルーター登録のみ）
- **追加作業**:
  - `edit_direction_routes`と`edit_assets_routes`のルーター登録
  - EditLearnerのインポートとインスタンス化
  - PROGRESS.md の更新（全18タスクの完了状況を記録）
  - 全体の動作確認（APIサーバー起動→全エンドポイント疎通テスト）
- **完了条件**: APIサーバー起動、全新規エンドポイント疎通確認、PROGRESS.md更新

---

## 依存関係マップ

```
独立タスク（即時着手可能）:
  M1-1, M1-2, M1-3        API新規作成（並列OK）
  M1-5, M1-6              プロンプト改修（並列OK）
  M2-5, M2-6              プロンプト改修（並列OK）
  M3-1                    サムネプロンプト強化
  M3-2                    Vimeoマッチング改善

依存タスク:
  M1-4 ← M1-3            （diff分析エンジンが先）
  M2-1 ← M1-1            （API先行）
  M2-2 ← M1-2            （API先行）
  M2-3 ← M1-2            （API先行）
  M2-4 ← M1-1, M1-2      （API先行）
  M3-3 ← M1-4            （学習DB先行）
  M3-4 ← M1-5,M1-6,M2-5,M2-6,M3-1（全プロンプト改修後）
  M3-5 ← M1-1〜M1-4      （機能実装後）
  M3-6 ← M1-1, M1-2      （ルーター作成後）
```

## 即時着手可能: 12本 / 依存待ち: 6本

**Wave 1（即時着手 — 12本）**: M1-1, M1-2, M1-3, M1-5, M1-6, M2-5, M2-6, M3-1, M3-2 + iOS UI設計(M2-1〜M2-3はAPI仕様を先に読んで設計だけ先行)
**Wave 2（Wave 1完了後 — 6本）**: M1-4, M2-4, M3-3, M3-4, M3-5, M3-6
