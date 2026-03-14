# タスク: 映像エージェント実用化

## 目的
映像ディレクションシステムを実用レベルに引き上げる

## やること（優先順位順）
1. FB学習ループ実装: src/video_direction/tracker/feedback_learner.py の結果を direction_generator.py に反映させる仕組みを作る
2. スプシマッチング精度改善: 15/30→25/30以上。ゲスト名正規化改善、部分一致ロジック追加
3. Vimeo API実投稿: scripts/post_vimeo_review_comments.py の --dry-run を外して本番投稿可能に。リトライロジック追加

## 完了条件
- 既存テストが壊れないこと
- 修正後にテスト実行して確認
