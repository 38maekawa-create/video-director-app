# タスク: Vimeoレビュータイムライン表示

<!-- authored: T1/副官A/バティ/2026-03-16 [なおとさん指示: P1一気にやりきる] -->

## 目的
Vimeo動画のタイムライン上にフィードバックポイントを可視化し、動画再生と同期してFBを表示する。

## 背景
- feedbacks テーブルに timestamp_mark カラム存在（タイムコード保存設計済み）
- FeedbackHistoryView.swift でフィードバック一覧表示は完成
- Vimeoプレイヤーとの連携（再生同期・タイムラインUI）は未実装
- iOS側でWebViewを使ったVimeoプレイヤー表示が必要

## 全体工程における位置づけ
P1。ディレクターがiPhoneで動画を再生しながら、各タイムコードに紐づくFBを確認できる。
音声FB→Vimeo投稿と組み合わせると、投稿したFBを動画上で確認する双方向フローが完成。

## やること

### 1. VimeoプレイヤーWebView実装（iOS）
- `VimeoPlayerView.swift` を新規作成
- WKWebView で Vimeo iframe プレイヤーを表示
- Vimeo Player.js SDK の postMessage API で再生制御（play/pause/seekTo/getCurrentTime）
- JavaScript→Swift のメッセージングでcurrentTime を取得

### 2. タイムラインFBオーバーレイ（iOS）
- `VimeoTimelineView.swift` を新規作成
- 動画の再生時間に対応するタイムライン上にFBポイントをマーカー表示
- マーカータップでFB詳細をポップアップ表示
- 再生位置に応じて該当FBをハイライト

### 3. APIエンドポイント
- `/api/v1/projects/{id}/feedbacks-with-timecodes` エンドポイント追加
- timestamp_mark でソートされたフィードバック一覧を返す
- Vimeo動画IDも含めて返す

### 4. DirectionReportViewへの統合
- プロジェクト詳細画面のタブに「レビュー」タブを追加
- VimeoプレイヤーとタイムラインFBを統合表示

### 5. テスト追加
- APIエンドポイントのユニットテスト
- タイムコードフィルタリングのテスト

## 完了条件
- VimeoプレイヤーがiOSアプリ内で表示・再生できる
- タイムライン上にFBマーカーが表示される
- xcodebuild BUILD SUCCEEDED
- テスト追加して全PASS
- PROGRESS.md更新

## 絶対ルール
- 既存コードの削除禁止。追加・修正のみ
- AppThemeの色・フォント定義に従う
- 新ファイル追加時は project.pbxproj への登録を忘れない
- WKWebView使用時は適切なATS設定を確認
