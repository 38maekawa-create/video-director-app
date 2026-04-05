# タスク: 映像トラッキング機能の実用化

<!-- authored: T1/副官A/バティ/2026-03-16 [なおとさん指示: 空きモデルに次タスク投入] -->

## 目的
映像トラッキング機能（YouTube/Netflix等の外部映像分析）の骨組みを実用レベルに引き上げる。

## 背景
- tracker/ 配下に video_learner.py, feedback_learner.py 等が存在するが骨組みレベル
- feedback_learner → direction_generator の接続は今回完了済み
- video_learner.py はデータなしの状態
- frame_evaluator.py はUI未連携

## やること

### 1. video_learner.py の実用化
- 外部映像（YouTube/Netflix等）の分析結果を蓄積する仕組みを強化
- 学習パターンの出力フォーマットを feedback_learner と統一
- direction_generator への接続（feedback_learnerと同様の仕組み）

### 2. frame_evaluator.py のAPI連携
- api_server.py にフレーム評価エンドポイントを追加
- `/api/v1/projects/{id}/frame-evaluation` でフレーム画像の品質評価結果を返す

### 3. 映像トラッキングダッシュボードUI（iOS）
- 既存の品質ダッシュボードに映像トラッキングセクションを追加
- トラッキング対象の映像一覧表示
- 分析結果のサマリー表示

### 4. テスト追加
- video_learner の学習ロジックテスト
- frame_evaluator APIエンドポイントテスト

## 完了条件
- video_learner が direction_generator に接続される
- frame_evaluator のAPIエンドポイントが動作する
- テスト全PASS
- PROGRESS.md更新

## 絶対ルール
- 既存コードの削除禁止
- AppThemeに従う
