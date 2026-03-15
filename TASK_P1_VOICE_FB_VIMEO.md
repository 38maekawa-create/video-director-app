# タスク: 音声FB→Vimeoレビューコメント連携の完成

<!-- authored: T1/副官A/バティ/2026-03-16 [なおとさん指示: P1一気にやりきる] -->

## 目的
音声フィードバックの録音→STT変換→Vimeoタイムコードコメントとして投稿する一気通貫フローを完成させる。

## 背景
- iOS側: VoiceFeedbackViewModel.swift で音声録音→STT→変換フロー実装済み
- Python側: post_vimeo_review_comments.py で Vimeo APIコメント投稿実装済み（dry-run/本番切替、リトライ、優先度フォーマット）
- VIMEO_ACCESS_TOKEN設定済み（疎通確認OK）
- 足りないのは「STT結果→APIサーバー→Vimeoコメント投稿」の接続部分

## 全体工程における位置づけ
P1。iPhone上で音声FBを録音→自動でVimeoのタイムコード上にコメントとして投稿される実用フロー。
これが完成すれば、撮影現場でディレクターが声でFBするだけで、Vimeo上にレビューが自動的に残る。

## やること

### 1. APIサーバーにVimeoコメント投稿エンドポイント追加
- `src/video_direction/integrations/api_server.py` に `/api/v1/vimeo/post-review` エンドポイントを追加
- リクエスト: `{ vimeo_video_id, comments: [{ timecode, text, priority }] }`
- 内部で `post_vimeo_review_comments.py` のロジックを呼び出す
- dry-runモードをクエリパラメータで切替可能に

### 2. iOS側のVimeo投稿フロー接続
- VoiceFeedbackViewModel.swift にVimeoコメント投稿メソッドを追加
- STT結果 + タイムスタンプを構造化して上記APIエンドポイントに送信
- 投稿成功/失敗のフィードバック表示

### 3. タイムコードマッピングの実装
- 音声FBの timestamp_mark を Vimeo動画のタイムコードに変換するロジック
- `VIMEO_TIMECODE_MODE=embed_text` の場合はコメント本文にタイムコードを埋め込む

### 4. テスト追加
- APIエンドポイントのユニットテスト
- タイムコードマッピングのテスト
- dry-runモードでの統合テスト

## 完了条件
- APIエンドポイントが動作する
- dry-runモードでVimeo APIへの疎通が確認できる
- テスト追加して全PASS
- PROGRESS.md更新

## 絶対ルール
- 既存コードの削除禁止。追加・修正のみ
- 本番Vimeo投稿は実行しない（dry-runまで）
- VIMEO_ACCESS_TOKEN は環境変数/api-keys.envから読み込む（ハードコード禁止）
