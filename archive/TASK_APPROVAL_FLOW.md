# タスク指示書: FB変換結果の承認フロー実装

## 目的
音声FBのLLM変換結果を、FB投稿者本人（なおとさん or パグさん）が事前承認してからVimeoレビューコメントに投稿する仕組みを作る。編集者に届く前に品質を担保するゲート。

## 背景
- FB変換パイプラインの品質改善（Opus化・全文注入・コンテンツライン）が完了し、変換品質は大幅に向上
- しかし100%の精度は保証できないため、人間の承認ステップを挟む
- なおとさんとの壁打ちで「事前承認制」「1コメント1テーマ」「FB投稿者本人が承認」で確定（2026-03-20）

## 全体工程における位置づけ
「3つのタイミングで効くナレッジ活用」設計のタイミング①（FB変換の具体化）の運用フロー部分。
これが完了すると、FB変換→承認→Vimeo投稿の一気通貫フローが完成し、実運用に入れる。

## 設計（確定済み）

### フロー
```
音声FB → STT → LLM変換 → 「承認待ち」で保存
                              ↓
         アプリの承認画面で一覧表示
                              ↓
         承認 → Vimeo投稿可能に
         修正 → テキスト手直し → Vimeo投稿可能に
         却下 → 終了（投稿不可）
```

### 承認ルール
- FB投稿者本人（created_by）のみが承認権限を持つ
- 1コメント1テーマ（複合FBの分解は不要）
- 承認後はVimeo投稿ボタンが有効になる（既存のVimeo投稿UIをそのまま活用）

### DB変更（feedbacksテーブル）
```sql
ALTER TABLE feedbacks ADD COLUMN approval_status TEXT DEFAULT 'pending';
-- 値: 'pending' / 'approved' / 'modified' / 'rejected'

ALTER TABLE feedbacks ADD COLUMN approved_at TEXT;
-- 承認日時

ALTER TABLE feedbacks ADD COLUMN modified_text TEXT;
-- 修正時のテキスト（承認時はNULL、修正時はここに入る）

ALTER TABLE feedbacks ADD COLUMN approved_by TEXT;
-- 承認者（created_byと一致するはず）
```

### APIエンドポイント追加
```
GET  /api/v1/feedbacks/pending        — 承認待ちFB一覧
PUT  /api/v1/feedbacks/{id}/approve   — 承認（approval_status='approved'）
PUT  /api/v1/feedbacks/{id}/modify    — 修正承認（body: modified_text）
PUT  /api/v1/feedbacks/{id}/reject    — 却下
```

### iOS UI追加
1. **承認待ちFB一覧画面** — タブ or ダッシュボードから遷移
   - 各FBカードに: ゲスト名、FBカテゴリ、元FB要約、変換結果プレビュー
   - 未承認件数バッジ
2. **FB詳細承認画面**
   - 元の音声FBテキスト（before）
   - LLM変換結果（after）
   - 3ボタン: 承認 / 修正 / 却下
   - 修正時: テキストエディタが開く
3. **Vimeo投稿の制御**
   - 既存のVimeo投稿セクションは `approval_status == 'approved' || 'modified'` の場合のみ表示
   - modified の場合は `modified_text` を投稿テキストとして使用

### 既存コードの変更点
- `api_server.py`: 上記4エンドポイント追加
- `VoiceFeedbackView.swift`: Vimeo投稿セクションの表示条件に承認チェック追加
- 新規SwiftUI View: `FeedbackApprovalListView.swift`, `FeedbackApprovalDetailView.swift`

## 完了条件と検証
1. 音声FBを入れてLLM変換後、approval_status='pending'で保存されること
2. 承認待ち一覧画面にpendingのFBが表示されること
3. 承認→Vimeo投稿ボタンが表示されること
4. 修正→modified_textが保存され、Vimeo投稿時にmodified_textが使われること
5. 却下→Vimeo投稿ボタンが表示されないこと
6. 未承認のFBではVimeo投稿ボタンが表示されないこと
