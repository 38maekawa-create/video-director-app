# タスク指示書: 動画ナレッジページ閲覧機能の追加

## 目的
映像品質エージェントアプリ（WebアプリMVP / 将来的にはiOSアプリ）で、各対談動画の詳細画面に入った時に、動画ナレッジシステム（AI開発5）で生成された**各対談動画の閲覧ページ（HTML）**をアプリUI内に組み込んで閲覧できるようにする。

## 背景
- `~/video-knowledge-pages/` に各対談動画の閲覧ページがHTMLファイルとして存在する（約30件以上）
- 命名規則: `YYYYMMDD_YYYYMMDD撮影_ゲスト名.html`
- これらは動画ナレッジシステム（AI開発5）が文字起こし・要約・ナレッジ抽出して生成したページ
- 現在のAI開発10のWebアプリ（webapp/）にはレポート詳細画面があるが、動画ナレッジページとの連携はない
- なおとさんは「各対談動画の階層に入っていった時に、動画ナレッジページも見れるようにしたい」と指示

## 全体工程における位置づけ
- AI開発10のWebアプリMVP（webapp/）は完成済み。これは追加機能
- direction-pages（GitHub Pages公開済み31件）のレポート詳細画面に、対応する動画ナレッジページへのリンク/埋め込みを追加する
- ゲスト名でdirection-pagesとvideo-knowledge-pagesを紐付ける

## 完了条件と検証
1. レポート詳細画面（または対談動画の詳細View）に「ナレッジページを見る」ボタン/タブが追加されていること
2. タップするとvideo-knowledge-pagesの該当HTMLがアプリUI内のWebViewまたはスタイル統一したビューで表示されること
3. ゲスト名ベースで自動マッチングされていること（マッチしない場合はボタン非表示）
4. 既存の映像品質レポート画面のUIを壊さないこと

## 技術情報
- 動画ナレッジページの所在: `~/video-knowledge-pages/*.html`
- GitHub Pagesの対談レポート: `https://maekawanaoto.github.io/direction-pages/`（31件）
- WebアプリMVP: `~/AI開発10/webapp/`（HTML+CSS+JS、フレームワーク不使用）
- マッチングキー: ゲスト名（direction-pagesのファイル名 vs video-knowledge-pagesのファイル名）
- MEMBER_MASTER.json: `~/TEKO/knowledge/people/MEMBER_MASTER.json`（名寄せに使用可能）

## 注意事項
- video-knowledge-pagesのHTMLスタイルとアプリUIのスタイルが異なるため、iframe埋め込みかスタイル上書きのどちらかで対応
- 閲覧ページが存在しない対談動画もあるため、その場合は「ナレッジページ未生成」と表示
