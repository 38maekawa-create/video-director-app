# TASK_BEFORE_AFTER_INTEGRATION.md

## 目的
映像エージェントの各動画固有ページで、以下を一体で扱えるようにする。

- 編集前素材
- ディレクションレポート
- 編集後動画
- 編集後のFB / 評価
- 素材動画ナレッジページの要約 / 全文文字起こし

目標は、1本の動画案件について **before / after / direction / feedback / knowledge** を同一画面で追える状態にすること。

## 現在の前提
- Web UI の正本は GitHub Pages が配信する **リポジトリルート**
- 現在の詳細ページは `renderReport()` と `renderKnowledgePage()` を持ち、タブUIで拡張可能
- 素材ナレッジページは `knowledge-pages/` と `knowledge-pages-map.js` で参照可能

## 実装方針

### 1. 動画案件の共通ID導入
各案件に、編集前後を結びつける共通キーを持たせる。

候補:
- `videoId`
- `sourceVideoId`
- `editedVideoId`

最小要件:
- 一覧データの各 project に `videoId` を追加
- 素材 / 編集後 / FB / ナレッジ が同じ `videoId` で引けるようにする

### 2. データ構造拡張
`data.js` の project 単位で、最低限以下を持てる構造へ広げる。

- `sourceVideo`
  - title
  - guestName
  - shootDate
  - sourceUrl
  - summary
- `editedVideo`
  - title
  - editedUrl
  - status
  - qualityScore
- `directionReport`
  - sections
- `feedbackSummary`
  - latestFeedback
  - evaluation
  - historyCount
- `knowledge`
  - knowledgePageFile
  - summary
  - transcriptAvailable

### 3. 詳細ページタブ拡張
現在の詳細ページを、以下の情報構造へ寄せる。

- `概要`
- `ディレクション`
- `素材`
- `編集後`
- `FB / 評価`
- `全文 / 要約`

最低ライン:
- 素材タブ
- 編集後タブ
- FB / 評価タブ
- ナレッジタブ強化

### 4. before / after の見せ方
同一案件の中で、編集前後の関係が一目で分かるUIを入れる。

候補:
- 2カラムカード比較
- 縦並びの「素材 → 編集後」フロー表示
- 差分ポイントの強調表示

v1 では以下で十分:
- 素材カード
- 編集後カード
- それぞれの状態 / URL / 評価 / 主要メモ

### 5. ナレッジページ統合
素材の閲覧ページにある
- 要約
- 全文文字起こし
- 補足情報
を、このアプリの詳細ページ内で見られるようにする。

実装候補:
- 既存 iframe 埋め込みを継続
- iframe だけでなく、summary / transcript 抜粋表示枠を追加

v1 では:
- 既存 knowledge iframe を残す
- その上に summary セクションを追加
- transcript は全文ページへの導線を強化

### 6. 一覧トップからの遷移改善
トップ一覧から詳細へ入ったときに、
「この案件は編集前素材・編集後動画・FBが揃っているか」
が分かるようにする。

候補:
- before / after バッジ
- FB件数
- ナレッジ有無

## 実装順

### Phase A: データモデル
- `data.js` に `videoId` と before / after / feedback / knowledge を追加

### Phase B: 詳細ページUI
- `renderReport()` を拡張
- タブ構成を増やす
- 素材 / 編集後 / FB の各セクションを追加

### Phase C: ナレッジ統合強化
- 既存 `renderKnowledgePage()` を拡張
- 要約表示枠を追加
- 全文への導線を明示

### Phase D: 一覧UI強化
- トップカードに before / after / knowledge / FB 状態を追加

## v1の完成条件
- 各案件に before / after が紐づく
- 詳細ページで素材 / 編集後 / FB / ナレッジが見られる
- ナレッジページへ自然に到達できる
- 一覧から情報の揃い具合が分かる

## 注意
- 正本は必ずリポジトリルートの配信ファイルにする
- `webapp/` 側だけを修正しない
- before / after の紐付け規則は曖昧にせず、`videoId` で固定する
