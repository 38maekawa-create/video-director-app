# 概要欄未生成11件（38%）の原因調査レポート

> **調査日**: 2026-03-20
> **調査者**: バティ（Opus 4.6）
> **対象**: Phase 5 QCレポートで「未生成」と判定された概要欄11件

---

## 1. 調査結果サマリー

**根本原因**: LLMレスポンスのJSONパース失敗により `full_text` が空文字列でDBに上書きされた。

**メカニズム**:
1. バッチ再生成（2026-03-19 23:54）で29件のE2Eパイプラインが実行された
2. 概要欄生成は `description_writer.py` の `generate_description()` が `teko_core.llm.ask()` でSonnetを呼び出す
3. LLM呼び出し自体は成功するが、レスポンスのJSONに `full_text` キーが含まれないケースがある
4. `_parse_description_response()` が `data.get("full_text", "")` で空文字列を返す
5. `upsert_youtube_assets()` の ON CONFLICT DO UPDATE で既存の概要欄が空文字列で上書きされる

**影響範囲**: 29件中12件（RYOの重複レコード含む）のdescription_originalが空文字列

---

## 2. DB上の概要欄状態（全件）

### 空文字列のレコード（12件）

| プロジェクトID | ゲスト名 | updated_at |
|---------------|---------|------------|
| p-20251213-PAY | PAYさん | 2026-03-19T12:49 |
| p-20260101-kos | kosさん | 2026-03-19T13:01 |
| p-20260215-あさかつさん | あさかつさん | 2026-03-19T13:06 |
| p-20260101-けーさん | けーさん | 2026-03-19T13:15 |
| p-20251123-てぃーひろ... | てぃーひろさん | 2026-03-19T13:43 |
| p-20260125-ひ樹京... | ひろきょうさん | 2026-03-19T13:48 |
| p-20251130-みんてぃあ | みんてぃあさん | 2026-03-19T13:53 |
| p-20260124-やーまん | やーまんさん | 2026-03-19T13:57 |
| p-20260101-メンイチ | メンイチさん | 2026-03-19T14:40 |
| p-20260125-松本 | 松本さん | 2026-03-19T14:49 |
| p-20251130-真生さん | 真生さん | 2026-03-19T14:54 |
| p-ryo | RYO（重複） | 2026-03-19T21:45 |

### 概要欄が正常に格納されているレコード（18件）

正常なレコードは154〜1097文字の概要欄テキストを保持。

---

## 3. 原因の詳細分析

### 3-1. コードパスの特定

概要欄生成の呼び出しチェーン:

```
batch_generate_directions.py
  → POST /api/v1/projects/{id}/e2e-pipeline  (api_server.py:3025)
    → Step 4.6 (api_server.py:3254-3349)
      → generate_description()  (description_writer.py:33)
        → teko_core.llm.ask(prompt, model="sonnet")  (description_writer.py:102)
        → _parse_description_response(raw)  (description_writer.py:103)
      → upsert_youtube_assets()  (api_server.py:3340)
```

### 3-2. パース失敗の原因

`_parse_description_response()` (description_writer.py:161-181) の処理:

```python
def _parse_description_response(raw: str) -> VideoDescription:
    json_match = re.search(r"\{[\s\S]*\}", raw)
    # ... JSON抽出 ...
    return VideoDescription(
        full_text=data.get("full_text", ""),  # ← キーがなければ空文字列
        ...
    )
```

プロンプト（prompts.py:282）に矛盾する指示がある:
- 282行: 「テンプレート固定部分はdescription_writer.py側で付与する。AIはハッシュタグとタイムスタンプのみ生成すればよい」
- 287行: `"full_text": "そのままコピペして使える概要欄の全文テキスト"`

LLMが282行の指示を優先した場合、`full_text`を空にするか、ハッシュタグのみを返す可能性がある。実際に一部のプロジェクトではこの現象が発生している。

### 3-3. フォールバックが機能しない理由

`generate_description()` は LLM失敗時に `_fallback_description()` を呼ぶ（テンプレートベースの概要欄を返す）。しかし:

- **LLM呼び出し自体は成功している**（api-server.logにLLM失敗ログなし）
- パース結果として `VideoDescription(full_text="")` が返る
- この戻り値は正常なオブジェクトなのでフォールバックパスに入らない
- 結果として空文字列がそのままDBに書き込まれる

### 3-4. ON CONFLICT DO UPDATEによる上書き問題

`upsert_youtube_assets()` (api_server.py:738-766) のUPSERT文:

```sql
ON CONFLICT(project_id) DO UPDATE SET
  description_original=excluded.description_original,
  ...
```

バッチ再生成前に概要欄が存在していた場合でも、再生成で空文字列が返ると**既存の正常な概要欄が空で上書きされる**。

### 3-5. 成功と失敗の分布パターン

バッチ処理順で見ると、成功と失敗が交互に現れる（連続した失敗は最大4件: てぃーひろ→ひろきょう→みんてぃあ→やーまん）。これはLLMの出力フォーマットが不安定であることを示す。APIクレジット不足による一括失敗ではない。

---

## 4. 副次的発見

### 4-1. 重複プロジェクトレコード
DB上に重複が3件ある:
- PAY / PAYさん（p-pay / p-20251213-PAY）
- RYO / RYOさん（p-ryo / p-20260124-RYO）
- hiraiさん × 2（p-20251123-hiraiさん / 別ID — youtube_assetsのみ）

### 4-2. api-server.logにAPIクレジット不足エラー（94件）
バッチ再生成以前の過去のリクエストで大量のAnthropicクレジット不足エラーが発生している。ただし03-19のバッチ実行時はLLM呼び出し自体は成功している。

---

## 5. 修正案

### 修正案A: _parse_description_responseのバリデーション追加（推奨）

description_writer.py の `_parse_description_response()` に `full_text` 空チェックを追加し、空ならフォールバックに回す:

```python
def generate_description(...) -> VideoDescription:
    try:
        raw = ask(prompt, model="sonnet", max_tokens=3000, timeout=120)
        result = _parse_description_response(raw)
        # full_textが空ならフォールバックへ
        if not result.full_text or len(result.full_text) < 50:
            print(f"  ⚠️ 概要欄パース結果が空または短すぎる（{len(result.full_text)}文字）。フォールバックへ")
            return _fallback_description(video_data, classification, income_eval)
        return result
    except Exception as e:
        ...
```

### 修正案B: プロンプトの矛盾を解消

prompts.py の DESCRIPTION_GENERATION_PROMPT の矛盾する指示を修正:
- 282行の「AIはハッシュタグとタイムスタンプのみ生成すればよい」を削除
- または `full_text` にテンプレート全文を含めるよう明確に指示

### 修正案C: upsert時の空文字列ガード

api_server.py の upsert_youtube_assets呼び出し前に空チェック:

```python
description_original=yt_description.full_text if (yt_description and yt_description.full_text) else None,
```

Noneの場合、ON CONFLICT DO UPDATEで `description_original=NULL` になるが、既存の正常値は保護されない。保護するには:

```sql
description_original=CASE WHEN excluded.description_original IS NOT NULL
    AND length(excluded.description_original) > 0
    THEN excluded.description_original
    ELSE youtube_assets.description_original END
```

### 推奨: A + B + C の3つ全てを適用

- A: パース結果のバリデーション（即効性あり）
- B: プロンプトの矛盾解消（根本対策）
- C: DB上書き防止（防御的プログラミング）

---

## 6. 再生成の手順

修正後、以下のコマンドで未生成11件のみ概要欄を再生成可能:

```bash
# APIサーバー起動状態で
python3 scripts/batch_generate_directions.py --execute --project-id <対象ID>
```

または概要欄のみの再生成スクリプトを新規作成（タイトル・サムネは既に正常なので再生成不要）。
