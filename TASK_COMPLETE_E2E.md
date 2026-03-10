# タスク指示書: AI開発10 完走（E2Eテスト + Phase4計画）

## 目的
映像ディレクションシステムの実環境E2Eテストを完了し、Phase4計画を立案する。
Phase3まで全142テストパス済み。残りは実環境での動作確認とリポジトリ整備。

## 背景
Phase1（コアエンジン9機能）→ Phase2（品質スコアリング+テロップ+フレーム+音声+ダッシュボード+スキルマトリクス）→ Phase3（統合パイプライン+CLI+ウォッチャー）が完走済み。
実環境テストとリポジトリ作成で本番運用可能な状態にする。

## 全体工程における位置づけ
Phase3完了 → **このタスク（E2Eテスト+リポ作成+Phase4計画）** → Phase4実装（将来）
完了すると、映像ディレクションシステムが本番運用開始できる状態になる。

## 作業内容（優先順位順）

### 1. direction-pages/ GitHubリポジトリ作成
- `gh repo create maekawa-naoto/direction-pages --public --clone` で作成
- GitHub Pages設定（mainブランチ、/docs or /）
- 注意: Mac3ではgh authが切れている可能性あり。Mac1で実行すること

### 2. GitHub Pages公開 E2Eテスト
- 実データ（~/TEKO/knowledge/01_teko/video/ の30件）でHTMLレポート生成
- publisher.pyで direction-pages/ に公開
- 実際にブラウザアクセスできることを確認

### 3. スプシ連携 E2Eテスト
- sheets_manager.pyを実行し、Google Sheetsに正常に書き込めることを確認
- スプレッドシートの構造を確認し、必要に応じて調整
- Google認証: ~/.config/maekawa/google-credentials.json

### 4. Phase 4 計画立案
- PROGRESS.mdの未完了タスク・既知課題を踏まえてPhase4設計書を作成
- opencv/ffmpeg実連携（フレーム抽出・音声分析の実装）
- C-1/C-2/C-3の実装計画
- docs/PHASE4_PLAN.md に出力

## 完了条件
1. direction-pages/ リポジトリが存在し、GitHub Pagesが有効
2. 実データのHTMLレポートがGitHub Pagesで閲覧可能
3. Google Sheetsにデータ書き込み成功
4. Phase4計画書が docs/PHASE4_PLAN.md に存在
5. PROGRESS.mdが最新状態に更新されている

## 検証方法
- GitHub Pagesの公開URLにcurlでアクセスしHTTP 200を確認
- Google Sheetsのデータ件数をAPI経由で確認
- 全テスト（pytest）がパスすること
