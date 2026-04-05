# タスク指示書: VideoDirectorAgent Webアプリ版MVP

> 発行: 2026-03-11
> 発行者: バティ司令塔
> 実行者: 兵隊

## 1. 目的
iOSネイティブアプリ（Apple Developer Program承認待ち）の繋ぎとして、同等UIのWebアプリ（PWA）を作成する。スマホのブラウザからアクセスし、ホーム画面に追加すればアプリっぽく使える。

## 2. 背景
- iOSアプリのUI（Netflix風ダーク、黒+赤#E50914）は完成済み（BUILD SUCCEEDED）
- Apple Developer Program購入済みだが反映されていない（サポート連絡待ち）
- ネイティブアプリ配布までの繋ぎとしてWebアプリ版が必要
- direction-pagesと同じGitHub Pagesでデプロイ可能

## 3. 技術スタック
- HTML + CSS + JavaScript（フレームワークなし、シンプルに）
- PWA対応（manifest.json + service-worker.js）
- GitHub Pagesでホスティング
- レスポンシブ（スマホファースト）

## 4. デザイン仕様
既存のSwiftUIアプリと同じNetflix風UIを再現する:
- 背景: 純黒 #000000
- カード: #181818
- アクセント: #E50914（Netflix赤）
- テキスト: 白 #FFFFFF / グレー #808080
- ステータス完了: #46D369
- フォント:
  - ヒーロー/名前: セリフ体（Georgia等）、太字、字間広め
  - タイトル: イタリックセリフ体、ライトウェイト
  - ラベル: コンデンスド風、太字
  - VIDEO DIRECTORヘッダー: レタースペーシング広め、赤色

## 5. 画面仕様（3画面でMVP）

### 画面1: ホーム（プロジェクト一覧）
- ヒーローバナー（最新プロジェクト、グラデーション背景）
- 検索バー
- 横スクロールカルーセル（最近のFB / 要対応 / 全プロジェクト）
- 下部固定タブバー（中央に赤い録音ボタン）

### 画面2: レポート詳細
- ゲスト名（大きくセリフ体）+ 撮影日 + プロフィール
- タブ切替（演出 / テロップ / カメラ / 音声FB）
- 折りたたみセクション
- 下部固定「音声FBを追加」ボタン

### 画面3: 品質ダッシュボード
- 大きなスコア中央表示
- スコア推移折れ線グラフ（Canvas描画）
- カテゴリ別スコア

### タブバー
- 5タブ（ホーム/レポート/録音/履歴/品質）
- 中央の録音ボタンは大きめ赤丸
- position: fixed; bottom: 0

## 6. データ
- モックデータをJSオブジェクトとして埋め込み（MockData.jsと同等の内容）
- TEKOメンバー名を使用（さといも・トーマス、メンイチ、けー、hirai、コテ）

## 7. PWA対応
- manifest.json: name, short_name, icons, start_url, display: standalone, theme_color: #000000
- service-worker.js: 静的ファイルキャッシュ（オフライン対応）
- apple-touch-icon設定

## 8. デプロイ
- リポジトリ: ~/AI開発10/ 内に `webapp/` ディレクトリを作成
- 完成後、GitHub Pagesの設定についてはなおとさんに確認

## 9. 完了条件
1. スマホのSafariで正常に表示される
2. ホーム画面に追加でアプリ風に起動する
3. 3画面が動作する（タブ切替、カルーセルスクロール）
4. Netflix風ダークUI + セリフ体フォントが適用されている
5. レスポンシブ対応（iPhone SE〜iPhone 17 Pro Max）

## 10. 禁止事項
- React/Vue等のフレームワーク使用（シンプルなHTML/CSS/JSで）
- npm/node_modules依存
- 自動再生機能
