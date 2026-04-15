---
name: video-qc
description: TEKO対談動画の個別品質チェック+修正ワークフロー。「品質チェック」「概要欄修正」「QC」等で発火
user-invocable: true
---

# 映像エージェント 個別動画QC+修正ワークフロー

> marketing_qc.py（Pythonバッチ）の**補完**。代替ではない。
> バッチが29件一括でQCを回す一方、このWFは個別動画に対して人間の目線で品質を追い込む。
> 品質基準は `.claude/rules/quality-judgment-guide.md`（自動ロード済み）。

## 発動条件

- 「C番号XXの概要欄を修正して」
- 「〇〇さんの動画の品質チェックして」
- 「概要欄の品質を確認して」
- `/video-qc`

## Step 1: 対象動画の特定

1. ゲスト名 or C番号 or 動画IDから対象を特定
2. 以下のデータを収集:
   - ディレクションレポート（`output/reports/` or `.data/`）
   - 概要欄（description_writer.py の出力 or YouTube公開済み）
   - タイトル案（title_generator.py の出力）
   - ゲスト情報（層分類・コンテンツライン・年収区分）

## Step 2: 品質チェック（rules/品質基準に基づく）

### 概要欄チェック
- [ ] テンプレート構造に準拠しているか（YouTube APIテンプレートとの整合性）
- [ ] コンテンツライン（キャリア軸 or 不動産軸）に合った内容か
- [ ] ゲスト情報（名前・肩書き・実績）が正確か（MEMBER_MASTERと照合）
- [ ] パンチライン（4つの引き金: 共感・好奇心・パンチ力・逆説）が効いているか
- [ ] NGパターン4種に該当しないか

### タイトルチェック
- [ ] 属性を見せる2つの目的（①自分ごと化 ②圧の乗数効果）を満たすか
- [ ] 設計思想に沿っているか（QUALITY_JUDGMENT_GUIDE セクション3）

### ディレクションチェック
- [ ] 層分類が正しいか（セクション1の5段階ルール）
- [ ] 演出指示がテンプレ的・抽象的になっていないか（セクション2）
- [ ] ハイライト選定が品質基準に沿っているか（セクション5）

## Step 3: 修正（必要な場合）

1. 問題箇所を特定し、修正案を作成
2. **修正前→修正後の差分を明示**（ファイル名だけで済ませない）
3. 概要欄の修正:
   - `.data/` or `output/` 内の該当ファイルを直接修正
   - 修正理由をコメントで残す
4. 層分類の修正:
   - guest_classifier.py のロジックに問題がある場合は KNOWN_CORRECTIONS.md に追記
   - **ルールベース分類のコードを勝手にLLM化しない**（codebase-rules.md 参照）

## Step 4: 検証

1. 修正後の概要欄・タイトル・ディレクションを再チェック
2. 類似ケースの他ゲストにも同じ問題がないか確認（指摘駆動の全件チェック）
3. KNOWN_CORRECTIONS.md に修正内容を記録

## 品質基準の参照先

| 基準 | 参照先 |
|------|--------|
| 層分類ルール | rules/quality-judgment-guide.md セクション1 |
| 演出ディレクション | rules/quality-judgment-guide.md セクション2 |
| タイトル設計思想 | rules/quality-judgment-guide.md セクション3 |
| 概要欄文章生成 | rules/quality-judgment-guide.md セクション4 |
| ハイライト選定 | rules/quality-judgment-guide.md セクション5 |
| コードルール | rules/codebase-rules.md |
| ファイル命名 | rules/naming-rules.md |

## 禁止事項

- marketing_qc.py を「不要」と判断して削除・無効化すること（バッチ用。役割が違う）
- 品質基準をSKILL.md内にコピーすること（rules/のsymlinkが正本。二重管理禁止）
- ゲスト名をナレッジ確認なしで使用すること（jp#18）
- 修正報告にファイル名だけ並べること（jp#27: 修正前→修正後の差分必須）
