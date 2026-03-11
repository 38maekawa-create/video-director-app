# 映像エージェント Web UI 正本ルール

## 結論
- GitHub Pages が配信する **リポジトリルート** を Web UI の正本とする

## 正本に含むもの
- `index.html`
- `app.js`
- `data.js`
- `styles.css`
- `manifest.json`
- `service-worker.js`
- `knowledge-pages-map.js`
- `knowledge-pages/`

## 運用ルール
- 今後の UI 修正・機能追加は、必ずルート配下の配信ファイルに対して行う
- `webapp/` 配下は過去の作業コピーとして扱い、正本にしない
- ナレッジページ生成スクリプトも、ルート配下の `knowledge-pages/` と `knowledge-pages-map.js` を更新対象にする

## 再発防止
- 修正前に「配信される場所」と「編集する場所」が一致しているか確認する
- UI が壊れた時は、まずルート配下と `webapp/` 配下の二重管理が起きていないか確認する
