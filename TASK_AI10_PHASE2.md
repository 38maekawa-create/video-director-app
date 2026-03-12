# タスク: AI開発10 映像システム Phase 2 — 実環境テスト + Phase 2計画立案

## 目的
Phase 1（コアエンジン9機能実装・監査完了）を実環境で検証し、Phase 2の計画を立案する。

## 背景
- Phase 1で9機能を実装、53テスト全パス、30件のゲストデータで自走修正3サイクル完了
- 未完了: GitHub Pages公開のE2Eテスト、スプシ連携のE2Eテスト、direction-pages/リポジトリ作成
- PROGRESS.md に詳細あり

## 全体工程における位置づけ
- Phase 1 完了 → [本タスク] 実環境テスト → Phase 2 計画立案 → Phase 2 実装

## 作業内容

### 1. 実環境テスト
- direction-pages/ GitHubリポジトリを作成（存在しない場合）
- publisher.py で実際にGitHub Pages公開をテスト
- sheets_manager.py で実際にスプレッドシートへの書き込みをテスト
- 結果をVERIFICATION_REPORTに追記

### 2. Phase 2 計画立案
- docs/REQUIREMENTS.md の全28機能から、Phase 2の対象機能を選定
- TASK_PHASE2.md を作成
- 優先順位: ユーザーが実際に使うワークフロー（バッチ処理、新ゲスト登録フロー）から着手

### 3. Python環境更新
- Python 3.10+への更新（EOL警告の解消）

## 完了条件
1. GitHub Pages公開のE2Eテスト成功
2. スプシ連携のE2Eテスト成功
3. TASK_PHASE2.md 作成完了
4. PROGRESS.md 更新
