# タスク: YouTube素材3機能 iOS UI完成

<!-- authored: T1/副官A/バティ/2026-03-15 [なおとさん指示: 映像エージェント実用化] -->

## 目的
映像エージェントiOSアプリのYouTube素材機能（サムネ指示書・タイトル案・概要欄）を実用レベルに完成させる。

## 背景
- iOS UI全体はBuild 17でなおとさん承認済み（ホーム・詳細・全プロジェクト一覧）
- YouTube素材機能はPython側で実装済み（thumbnail_designer.py, title_generator.py, description_generator.py）
- iOS側に `YouTubeAssetsView.swift` が存在するが、表示品質・コピー機能が未完成
- APIクライアント `APIClient.swift` で baseURL は `http://100.110.206.6:8210`

## 全体工程における位置づけ
P2。基本UIが完了した上での追加機能。
撮影後にiPhoneでサムネ指示書・タイトル案・概要欄を確認・コピーできれば、
編集者への指示出しがその場で完結する。

## やること

### 1. YouTubeAssetsView.swift の改善
- サムネ指示書（Z型4ゾーン）の表示を見やすく改善
- タイトル案3-5件の表示 + クリップボードコピーボタン
- 概要欄テキストの表示 + クリップボードコピーボタン
- AppThemeに合わせたNetflix風デザイン

### 2. API連携確認
- YouTubeAssetsViewModelのbaseURLがlocalhost:8210ハードコードの場合 → APIClient.shared経由に修正
- エラーハンドリング（API接続失敗時の表示）

### 3. DirectionReportViewからの遷移
- 各プロジェクトの詳細画面からYouTube素材タブへの遷移が正常に動作するか確認

## 完了条件
- サムネ指示書・タイトル案・概要欄が見やすく表示される
- コピーボタンでクリップボードにコピーできる
- APIClient.shared経由でAPI接続
- ビルド成功（xcodebuild BUILD SUCCEEDED）
- PROGRESS.md更新

## 絶対ルール
- 既存コードの削除禁止。追加・修正のみ
- AppThemeの色・フォント定義に従う
- 新ファイル追加時は project.pbxproj への登録を忘れない
