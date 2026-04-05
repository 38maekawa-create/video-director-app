# タスク指示書: トリプル監査（GPT-5.4 + Codex + Claude）

## 目的
2026-03-20の大量変更（FB変換改善・品質基準注入・承認フロー・再バッチ生成）に対して、3つの独立した目で品質・整合性・セキュリティを検証する。

## 背景
- 前回Phase 5品質チェック（29件突合）で83%正解率・重大問題4件が発見された実績あり
- 今回はFB変換パイプラインのコア部分 + 承認フローのDB/API/UI + 全29件のデータ更新と変更範囲が広い
- 単一視点での検証では漏れが出るため、3つの異なるAIによるクロスチェックが必要

## 全体工程における位置づけ
T-041（再バッチ）とT-042（承認フロー）の完了後に実施。
監査PASSが実運用開始の前提条件。

## 監査対象ファイル

### Python（バックエンド）
1. `src/video_direction/tracker/editing_feedback_converter.py` — FB変換パイプライン（model変更、切り詰め撤廃、コンテンツライン注入）
2. `src/video_direction/knowledge/quality_knowledge_loader.py` — 品質基準プロンプト注入基盤（新規280行）
3. `src/video_direction/integrations/api_server.py` — 承認フローAPI 4本追加
4. `src/video_direction/analyzer/description_writer.py` — 概要欄生成（既知バグあり、T-043で修正予定）

### Swift（iOS）
5. `VideoDirectorAgent/VideoDirectorAgent/Views/FeedbackApprovalListView.swift` — 承認一覧画面（新規）
6. `VideoDirectorAgent/VideoDirectorAgent/Views/FeedbackApprovalDetailView.swift` — 承認詳細画面（新規）
7. `VideoDirectorAgent/VideoDirectorAgent/Views/VoiceFeedbackView.swift` — 既存画面の承認チェック追加
8. `VideoDirectorAgent/VideoDirectorAgent/Services/APIClient.swift` — 承認API呼び出し追加

### データ
9. `.data/video_director.db` — feedbacksテーブルのスキーマ変更 + 29件の再生成データ

### テスト
10. `tests/test_editing_feedback_converter.py` — 切り詰めテストの反転

## 監査観点（3チーム共通）

### A. コード品質
- [ ] 型安全性・エラーハンドリング
- [ ] SQLインジェクション等のセキュリティ脆弱性
- [ ] DB schemaとAPI仕様の整合性
- [ ] 既存機能との非互換・regression

### B. ロジック正当性
- [ ] FB変換: Opus呼び出しが正しく動作するか
- [ ] FB変換: 品質基準がセクション5全文（10,698文字）注入されているか
- [ ] FB変換: コンテンツライン判定（teko_member→キャリア軸, teko_realestate→不動産軸）が正しいか
- [ ] 承認フロー: approval_statusの状態遷移が正しいか
- [ ] 承認フロー: created_byと承認者の一致チェックが機能するか
- [ ] 承認フロー: 未承認FBからVimeo投稿がブロックされるか

### C. データ整合性（29件再生成後）
- [ ] 全29件の層判定が正しいか（QUALITY_JUDGMENT_GUIDE.mdと突合）
- [ ] hirai=層a, さるビール=層a, 真生=層c が修正されているか
- [ ] 概要欄の状態（既知バグあり、空上書き問題）
- [ ] quality_scoreの分布が妥当か

### D. iOS UI
- [ ] 承認画面のレイアウト・操作性
- [ ] Vimeo投稿ボタンの表示条件が正しいか
- [ ] エラー時のUI表示

## 3チーム配置

| チーム | モデル | ツール | 重点観点 |
|--------|--------|--------|----------|
| 監査A | GPT-5.4 | ChatGPT / Codexサイドバー | ロジック正当性 + セキュリティ |
| 監査B | Codex CLI | ターミナル | コード品質 + テスト実行 + データ整合性 |
| 監査C | Claude Code | ターミナル | iOS UI + 統合テスト + E2E動作確認 |

## 完了条件
1. 3チームそれぞれが独立した監査レポートを提出
2. Critical / High の問題が0件であること（Medium以下は記録して後日対応可）
3. 3チームのレポートをクロスチェックし、見解の相違があれば統合レポートで整理
4. 最終監査レポートを `docs/TRIPLE_AUDIT_20260320.md` に格納
