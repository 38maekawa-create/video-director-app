# タスク指示書: 概要欄未生成11件(38%)の原因調査

## 目的
Phase 5品質チェックで29件中11件（38%）の概要欄が「未生成」だった原因を特定し、修正する。

## 背景
- Phase 5 QCレポート（docs/PHASE5_QC_REPORT.md）で概要欄が「未生成」の件が11件
- 概要欄があるのは: RYOさん(部分), アンディさん, くますけさん(部分), ロキさん, hiraiさん の5件のみ
- 残り24件が未生成 or 部分的 → 生成パイプラインに問題がある可能性

## 全体工程における位置づけ
ディレクションレポートの品質向上。概要欄はYouTubeのSEOに直結する重要要素。
原因特定→修正→再バッチ生成（TASK_BATCH_REGEN.mdと統合可能）。

## 調査手順
1. 概要欄生成のコードパスを特定
```bash
cd ~/AI開発10
grep -r "description\|概要欄" src/video_direction/ --include="*.py" -l
```

2. DB上の概要欄の状態を確認
```python
import sqlite3
conn = sqlite3.connect('.data/video_director.db')
rows = conn.execute("SELECT id, guest_name, description IS NOT NULL, length(description) FROM projects").fetchall()
for r in rows:
    print(f'{r[1]}: has_desc={r[2]}, len={r[3]}')
```

3. バッチ生成ログで概要欄生成のスキップ/エラーを確認

4. 概要欄生成が呼ばれる条件（YouTube URLの有無等）を特定

## 完了条件と検証
1. 未生成の原因が特定できていること
2. 修正案が明確であること（コード修正 or 設定変更 or データ補完）
3. 調査結果をdocs/DESCRIPTION_INVESTIGATION.mdに記録
