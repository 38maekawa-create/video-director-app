# タスク: 音声FB→Vimeo連携のUI組み込み

<!-- authored: T1/副官A/バティ/2026-03-16 [なおとさん指示: 空きモデルに次タスク投入] -->

## 目的
先ほど完成した音声FB→Vimeoレビュー連携のロジック層（ViewModel/APIClient/Models）を、
実際のiOS UIに組み込んで、ユーザーが操作できるようにする。

## 背景
- VoiceFeedbackViewModel.swift に `sendToVimeoReview(dryRun:)` メソッド追加済み
- APIClient.swift に `postVimeoReviewComments()` メソッド追加済み
- Models.swift に VimeoPostReviewRequest 等のモデル追加済み
- **UIへの組み込みが未実施**（ボタン・入力フィールド・結果表示）

## やること

### 1. VoiceFeedbackView.swift にVimeo投稿UIを追加
- Vimeo動画ID入力フィールド（テキストフィールド）
- 「Vimeoに投稿」ボタン（dry-runモード）
- 投稿結果の表示（成功/失敗、投稿予定コメント一覧）
- 投稿中のローディング表示

### 2. 品質ダッシュボードの実データ連動準備
- DashboardViewModel.swift で品質スコアAPIからのデータ取得を確認
- 実データが存在する場合に表示されるよう接続確認
- 品質トラッキングデータの表示改善

### 3. ビルド確認
- xcodebuild BUILD SUCCEEDED を確認

## 完了条件
- VoiceFeedbackViewにVimeo投稿UIが表示される
- ビルド成功
- PROGRESS.md更新

## 絶対ルール
- 既存コードの削除禁止
- AppThemeに従う
