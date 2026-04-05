# タスク指示書: 映像エージェント実用化（4段階）

<!-- authored: T1/副官A/バティ/2026-03-15 [なおとさんとの壁打ちで確定] -->

## 目的
映像エージェント（AI開発10）を「撮影後すぐ使える実用ツール」にする。
現状はMVPとして全機能が実装済みだが、UIの完成度・データ連携に不足がありスマホ・PCでの実用に至っていない。

## 背景
- Python バックエンド: 45ファイル実装、524テストPASS、FastAPI port 8210で3週間無停止稼働中
- iOS SwiftUI: ビルド成功、TestFlight Build 7アップロード済み（処理待ち）
- Web PWA: http://100.110.206.6:8210/ でアクセス可能
- 兵隊の自律実行で一部の実装済み機能が消失した経緯あり → 既存コード削除禁止ルール適用

## 全体工程における位置づけ
P1b（生産性UP開発）の最優先タスク。これが完成すれば：
- 撮影直後にスマホでディレクションレポートを確認可能
- サムネ・タイトル・概要欄の提案をその場で確認・採用可能
- 編集前後の品質差分を可視化し、品質管理サイクルが開始できる
- CTO育成の「卒業制作」として、全工程の経験になる

## 優先順位（なおとさん確定）

### Priority 1: TestFlightアプリで実データ表示確認
- Build 7がApp Store Connect処理完了しているか確認
- iPhone実機でプロジェクト一覧が表示されるか確認
- API接続（localhost:8210 → Tailscale経由）の動作確認
- **完了条件**: iPhoneのTestFlightアプリで60件のプロジェクトが表示される

### Priority 2: YouTube素材3機能のUI完成
対象機能:
1. **サムネ生成ディレクション** — Z型4ゾーン指示書の表示・ダウンロード
   - Python: `src/video_direction/analyzer/thumbnail_designer.py` ✅実装済み
   - iOS: `YouTubeAssetsView.swift` に表示UIあり → 完成度確認・改善
   - Web: `webapp/app.js` に表示あり → 完成度確認・改善

2. **タイトル作成** — マーケティングナレッジを活かした3-5案提示
   - Python: `src/video_direction/analyzer/title_generator.py` ✅実装済み
   - iOS/Web: 上記と同じビューで表示

3. **概要欄作成** — SEO・CTAを含む概要文の生成・表示
   - Python: `src/video_direction/analyzer/description_writer.py` ✅実装済み
   - iOS/Web: 上記と同じビューで表示

- **完了条件**: 撮影後にスマホ/PCでサムネ指示書・タイトル案・概要欄が即座に確認でき、コピー可能

### Priority 3: before/after差分UIの実装
- 編集前素材と編集後動画をリンクして差分を可視化
- Python: `src/video_direction/evaluator/post_edit_feedback.py` ✅実装済み
- iOS: 差分表示UIが必要（品質スコアの変化、改善点の一覧）
- Web: 同上
- **完了条件**: 編集後動画をアップすると、編集前との品質差分が数値・グラフで見える

### Priority 4: Phase 3 映像トラッキング+学習
- YouTube映像のトラッキング・品質学習機能
- Python: `src/video_direction/tracker/` 配下に6ファイル実装済み
- iOS: `VideoTrackingView.swift` あり → 実データ連携確認
- 長期的な品質向上エンジンの基盤
- **完了条件**: トラッキング対象のYouTube映像の品質スコアが蓄積・トレンド表示される

## コード変更制約（絶対ルール）
1. **既存機能の削除・変更は絶対禁止** — 追加のみ許可。バグ修正は最小範囲で許可
2. **コード品質改善の範囲限定** — テスト追加・docstring追加・型ヒント追加のみ
3. **REQUIREMENTS.mdとの自動突合チェック** — 各Priority完了時にdocs/REQUIREMENTS.mdと実装を突合し結果を報告

## 検証方法
- 各Priority完了時にスクリーンショットで実画面確認（3サイクル検証）
- iOS: シミュレータまたはTestFlight実機で確認
- Web: http://100.110.206.6:8210/ で確認
- API: `curl http://localhost:8210/api/projects` でデータ疎通確認
- テスト: `cd ~/AI開発10 && source venv/bin/activate && python3 -m pytest -q` で全テストPASS確認
