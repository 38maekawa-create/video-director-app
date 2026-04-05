# タスク指示書: AI開発10 Phase 1 コアエンジン実装

> 発行: 2026-03-10
> 発行者: 司令塔セッション
> 実行者: 兵隊（Claude Code CLI）
> 監査: Codex + GPT-5.4

---

## 1. 目的

TEKO対談インタビュー動画の文字起こしデータから、動画編集者向けのディレクションレポートを自動生成するコアエンジンを実装する。文字起こしを入れたらHTMLページが出て、スプレッドシートにURLが入る — この一気通貫を動作させる。

## 2. 背景

- AI開発5（動画ナレッジシステム）が文字起こし→分析→ナレッジ化まで完了している
- 現状、動画編集者へのディレクションは手動で行われている
- ディレクションマニュアル（teko_interview_direction_manual.md）のルール体系を自動適用する
- video-knowledge-pagesと同じ仕組みでdirection-pagesを公開し、スプシ連携する

## 3. 全体工程における位置づけ

- 全28機能のうちPhase 1の9機能を実装する
- Phase 1が完了すると「文字起こし → ディレクションレポート → スプシURL追記」の一気通貫が動く
- Phase 2以降は映像品質評価・トラッキング・学習機能を追加する
- Phase 1の完了がなければPhase 2以降に進めない（基盤となるため）

## 4. 実装する9機能

| ID | 機能名 | モジュール |
|----|--------|-----------|
| A-1 | ゲスト層自動分類 | analyzer/guest_classifier.py |
| A-2 | 年収演出判断 | analyzer/income_evaluator.py |
| A-3 | 年収以外の強さ発掘 | analyzer/income_evaluator.py（A-2と同一モジュール） |
| A-4 | 固有名詞規制 | analyzer/proper_noun_filter.py |
| A-5 | ターゲット別チェックリスト | analyzer/target_labeler.py |
| NEW-1 | 演出ディレクション | analyzer/direction_generator.py |
| H-1 | メンバーマスター連動 | integrations/member_master.py |
| J-1 | AI開発5連携 | integrations/ai_dev5_connector.py |
| J-2 | スプシ統合 | integrations/sheets_manager.py |

## 5. 実装手順

### Step 1: 環境セットアップ
1. venv作成 + requirements.txt のパッケージインストール
2. `.env` にAPIキーを設定（`~/.config/maekawa/api-keys.env` から読み込む）
3. `direction-pages/` リポジトリをローカルに作成 + GitHubリポジトリ作成（`38maekawa-create/direction-pages`）
4. `src/video_direction/__init__.py` + 各サブパッケージの`__init__.py`作成

### Step 2: 入力パーサー（J-1 + H-1）
1. `integrations/ai_dev5_connector.py`: `~/TEKO/knowledge/01_teko/sources/video/` のMarkdownファイルを読み込み、構造化データに変換
   - メタ情報（種別・カテゴリ・話者・動画時間）
   - 人物プロファイル（年齢・本業・年収・企業名）
   - ハイライトシーン（タイムスタンプ・発言）
   - 整形済みトランスクリプト全文
2. `integrations/member_master.py`: MEMBER_MASTER.json読み込み + メンバー属性の自動参照

### Step 3: 分析エンジン（A-1〜A-5 + NEW-1）
1. `analyzer/guest_classifier.py`: ゲスト分類ロジック（REQUIREMENTS.md セクション5-1のロジック実装）
2. `analyzer/income_evaluator.py`: 年収演出判断 + 代替強み検出（セクション5-2）
3. `analyzer/proper_noun_filter.py`: 固有名詞検出・判定・テロップ生成（セクション5-3）
4. `analyzer/target_labeler.py`: 各シーンの1層/2層ラベリング
5. `analyzer/direction_generator.py`: 演出ディレクション生成（テロップ・画角・色変えタイミング）（セクション5-4）
   - LLM（Claude Sonnet推奨）を使って文脈分析 → タイムライン形式の指示を生成

### Step 4: レポート生成（出力）
1. `reporter/html_generator.py`: 分析結果をHTMLページに組み立て
   - video-knowledge-pagesのCSS設計を踏襲
   - REQUIREMENTS.md セクション4-1のテンプレート構造に従う
2. `reporter/publisher.py`: direction-pages/への保存 + index.html更新 + git push
   - AI開発5の`publish_html.py`をパターン参考

### Step 5: スプシ連携（J-2）
1. `integrations/sheets_manager.py`: gspreadでスプシ接続 + ディレクションURL書き込み
   - AI開発5の`google_sheets.py`をパターン参考
   - スプレッドシートID: `1bW_qb13p747xoa2yf7RHaccNVTFCMxV8a5CjGdNqI6I`
   - タブ名: `【インタビュー対談動画】管理`
   - B列（タイトル）でマッチング → 末尾新列にURL書き込み

### Step 6: メインエントリーポイント
1. `main.py`: 全体オーケストレーション
   - 引数: 処理対象ファイルパス or 全件一括処理
   - パイプライン: パース → 分析 → レポート生成 → 公開 → スプシ更新

### Step 7: テスト
1. 各モジュールのユニットテスト（pytest）
2. 統合テスト: 実データ3件で一気通貫テスト
3. 生成HTMLのブラウザ表示確認（スクリーンショット検証）

## 6. 完了条件

- [ ] 実データ3件以上でディレクションHTMLが正常生成される
- [ ] ゲスト分類（層a/b/c）が手動判定と一致する
- [ ] 年収演出判断が早見表ルールと一致する
- [ ] 固有名詞が正しく検出・判定され、テロップ提案が生成される
- [ ] 演出ディレクションがタイムスタンプ付きで出力される
- [ ] direction-pages/index.html に一覧が表示される
- [ ] スプレッドシートにURLが正しく追記される
- [ ] 全テストがパスする

## 7. 検証方法

### 自走修正3サイクル
1回目: 全機能の動作確認 + コードエラー + データ整合性
2回目: 分類判断の妥当性 + 網羅性 + 除外判断の正当性
3回目: ユーザー視点「この結果を見て納得できるか」

### 監査パス条件
- Codex（GPT-5.3/5.4）による独立監査 → パス
- GPT-5.4によるセカンドオピニオン監査 → パス
- 両者パスで完了。不合格なら差し戻して修正。

## 8. 参照ドキュメント

- `~/AI開発10/docs/REQUIREMENTS.md` — 全要件定義（必読）
- `~/AI開発10/docs/teko_interview_direction_manual.md` — ディレクションルール体系（必読）
- `~/AI開発10/config.yaml` — システム設定
- `~/AI開発5/src/video_knowledge/pipeline/publish_html.py` — HTMLテンプレートパターン参考
- `~/AI開発5/src/video_knowledge/pipeline/google_sheets.py` — スプシ連携パターン参考
- `~/video-knowledge-pages/` — 出力HTMLの参考（CSS設計・index.html）

## 9. 禁止事項

- ディレクションマニュアルのルールを勝手に改変しない
- マーケティング判断を独自に行わない（ルールに従うだけ）
- 固有名詞の判定で「出す」側に安易に倒さない（迷ったら伏せる）
- スプレッドシートの既存データを上書き・削除しない（新列への追記のみ）
