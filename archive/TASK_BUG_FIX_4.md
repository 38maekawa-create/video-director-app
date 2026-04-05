# タスク指示書: Codex監査で発見された実バグ4件の修正

## 目的
Codexトリプル監査で発見された実バグ4件を修正し、映像エージェントの実運用開始ラインに到達させる。

## 背景
2026-03-21のCodexトリプル監査（TRIPLE_AUDIT_CODEX_REPORT.md）でFAIL判定。
FAILの大半はcheckout差分問題（承認フロー等のコミットが未反映）だが、以下の4件は実バグとして確認済み。

## 全体工程における位置づけ
映像エージェント実運用開始ラインのフェーズA-1。
この4件が直らないと、A-2（概要欄再生成）以降に進めない。
完了すると、概要欄修正→品質突合→タイミング3実装→再監査→TestFlightの流れに入れる。

## 修正対象

### 修正1: Critical — `instruction` vs `note` 契約不一致
**問題**: バックエンドのFB変換APIが `instruction` キーで返すが、iOS側の `StructuredFeedbackItem` は `note` キーを期待している。FB変換のデコードが壊れる。

**対象ファイル**:
- `src/video_direction/integrations/api_server.py` — 2586行目付近、3664行目付近の `"instruction"` キー
- `VideoDirectorAgent/VideoDirectorAgent/Models/Models.swift` — 355行目、363行目の `StructuredFeedbackItem`

**修正方針**: バックエンド側を `note` に統一する（iOS側に合わせる）。
- api_server.pyの `"instruction"` を `"note"` に変更
- 既存の `"note"` キー（2857行目等の別用途）と混同しないよう注意

**注意**: Models.swiftの1440行目に `instruction` を `decodeIfPresent` で受ける互換コードがある。バックエンド側を `note` に統一した後、この互換コードは不要になるが、削除は任意（後方互換として残してもOK）。

### 修正2: High — `description_writer.py` few-shot 300文字切り詰め
**問題**: 概要欄生成時のfew-shot例を300文字で切り詰めている。品質を殺す。

**対象ファイル**: `src/video_direction/analyzer/description_writer.py` — 49-51行目

**修正方針**: 300文字制限を撤廃する。全文をfew-shotに使う。
```python
# 修正前
truncated = desc[:300] + ("..." if len(desc) > 300 else "")
# 修正後
truncated = desc  # 全文使用
```

変数名 `truncated` は `example_desc` 等にリネームしてもよい。

### 修正3: High — `description_writer.py` フォールバックが不動産固定
**問題**: `_fallback_description()` の自己紹介文が不動産事業の固定テキスト。不動産以外のゲストで意味的に誤った概要欄が生成される。

**対象ファイル**: `src/video_direction/analyzer/description_writer.py` — 184行目以降の `_fallback_description()`、250-258行目付近

**修正方針**: フォールバックテキストを汎用化する。
- ゲストの `category`（`teko_member` / `teko_realestate` / その他）に応じてフォールバック文を分岐する
- `teko_realestate` の場合は現在のテキストを維持
- `teko_member` やその他の場合は不動産固有表現を除いた汎用版を使う
- 引数 `classification` に category 情報があるはずなので、それを参照する

### 修正4: High — `api_server.py` 例外握りつぶし
**問題**: FB変換パスで `except (ImportError, Exception): pass` が使われており、障害が不可視になる。

**対象ファイル**: `src/video_direction/integrations/api_server.py` — convert関連の例外処理箇所

**修正方針**:
- `pass` を `logger.exception("FB変換でエラー発生")` に置換
- フォールバック処理自体は維持（サービス継続のため）
- ただし例外情報をログに残すことで、運用監視・デバッグを可能にする

## 完了条件と検証
1. 4件全ての修正が完了していること
2. `./venv/bin/pytest -q` で既存テストが全PASS（新規テスト追加は任意）
3. api_server.pyの構文チェック: `python3 -c "import ast; ast.parse(open('src/video_direction/integrations/api_server.py').read())"`
4. description_writer.pyの構文チェック: 同上
5. 修正内容のサマリーをこのファイル末尾に追記すること

---

## 修正完了サマリー（2026-03-21）

### 修正1: Critical — `instruction` vs `note` 契約不一致 → 完了
- `api_server.py` 2590行, 3668行: フォールバック辞書の `"instruction"` → `"note"` に変更
- `api_server.py` 3511行: Vimeoコメント構築時の `entry["instruction"]` → `entry["note"]` に変更
- `feedback_converter.py` 517行: LLMプロンプトのJSONスキーマも `"instruction"` → `"note"` に統一
- テストファイル（test_api_phase3_4.py, test_e2e_api.py）のassertionも `"note"` に更新

### 修正2: High — few-shot 300文字切り詰め → 完了
- `description_writer.py` 49-51行: `desc[:300]` の切り詰めを撤廃、全文をfew-shotに使用
- 変数名を `truncated` → `example_desc` にリネーム

### 修正3: High — フォールバック不動産固定 → 完了
- `description_writer.py` `_fallback_description()`: `video_data.category` に応じて運営者紹介文を分岐
  - `teko_realestate`: 不動産投資に言及した従来版テンプレートを維持
  - `teko_member` / その他: 不動産固有表現（「不動産投資」「不動産賃貸業」等）を除去した汎用版を使用
- ハッシュタグも不動産カテゴリのみ `#不動産投資` を含むよう分岐

### 修正4: High — 例外握りつぶし → 完了
- `api_server.py` 2575行, 2579行, 3657行: `except Exception: pass` → `logger.exception(...)` に変更
- フォールバック処理自体は維持しつつ、例外情報がログに残るように改善
