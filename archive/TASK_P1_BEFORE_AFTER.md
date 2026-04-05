# タスク: Before/After連携 iOS UI + APIエンドポイント完成

<!-- authored: T1/副官A/バティ/2026-03-16 [なおとさん指示: P1一気にやりきる] -->

## 目的
編集前後の動画フィードバック（Before/After差分）をiOSアプリで確認・操作できるようにする。

## 背景
- Python側: `post_edit_feedback.py` で編集後フィードバック生成が完成（quality_score, content_feedback, telop_check, total_issues）
- iOS側: VoiceFeedbackView.swift に beforeAfterSection のUI骨格あり
- FeedbackHistoryView.swift に「音声」「変換後」の2段表示あり
- 足りないのは: APIエンドポイント、品質スコアUI、テロップチェック結果表示、修正提案の構造化UI

## 全体工程における位置づけ
P1。編集者に渡した動画が戻ってきた後に、元のディレクションとの差分を確認できる。
「指示した内容が反映されているか」をiPhoneで即座にチェックできる実用フロー。

## やること

### 1. APIエンドポイント追加
- `api_server.py` に `/api/v1/projects/{id}/edit-feedback` エンドポイント追加
- `post_edit_feedback.py` の `EditFeedbackGenerator` を呼び出す
- レスポンス: quality_score, grade, content_feedback[], telop_check, highlight_check

### 2. iOS側のBefore/After表示改善
- DirectionReportView または専用の EditFeedbackView を作成
- 表示内容:
  - 品質スコア（A/B/C/D/F グレード）をビジュアル表示
  - content_feedback 配列を severity（high/medium/low）で色分け表示
  - テロップチェック結果（エラー数・警告数）
  - 修正提案の構造化リスト
- AppThemeに合わせたNetflix風デザイン

### 3. APIClient.swift に fetchEditFeedback メソッド追加
- APIClient.shared 経由でエンドポイントを呼び出す
- Decodable モデル定義

### 4. テスト追加
- APIエンドポイントのユニットテスト
- EditFeedbackGenerator の統合テスト

## 完了条件
- APIエンドポイントが動作する
- iOS UIで品質スコア・修正提案が表示される
- xcodebuild BUILD SUCCEEDED
- テスト追加して全PASS
- PROGRESS.md更新

## 絶対ルール
- 既存コードの削除禁止。追加・修正のみ
- AppThemeの色・フォント定義に従う
- 新ファイル追加時は project.pbxproj への登録を忘れない
