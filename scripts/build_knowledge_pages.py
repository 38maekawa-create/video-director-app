#!/usr/bin/env python3
"""
動画ナレッジページをルート配信ディレクトリの knowledge-pages/ にコピーし、
マッピングデータ（knowledge-pages-map.js）を生成するビルドスクリプト。

対象: ~/video-knowledge-pages/ 内のTEKO対談動画HTML（ファイル名に「撮影」を含むもの）
マッチングキー: ゲスト名（ファイル名から抽出、「さん」サフィックス除去）
"""

import os
import re
import shutil
import json
from pathlib import Path
from typing import Optional

# パス設定
SOURCE_DIR = Path.home() / "video-knowledge-pages"
APP_ROOT = Path(__file__).resolve().parent.parent
DEST_DIR = APP_ROOT / "knowledge-pages"
OUTPUT_JS = APP_ROOT / "knowledge-pages-map.js"


def extract_guest_name(filename: str) -> Optional[str]:
    """ファイル名からゲスト名を抽出する。
    パターン: YYYYMMDD_YYYYMMDD撮影_ゲスト名さん*.html
    """
    # 「撮影_」の後ろからゲスト名部分を取得
    match = re.search(r'撮影_(.+?)\.html$', filename)
    if not match:
        return None

    raw = match.group(1)

    # 「さん」の後の属性情報を除去（例: hiraiさん30代中盤... → hirai）
    # ゲスト名は「さん」の前まで
    san_match = re.match(r'^(.+?)さん', raw)
    if san_match:
        return san_match.group(1)

    # 「さん」がない場合はそのまま（例: 真生さん → 真生、ただし実際は真生さん30代...）
    return raw


def find_best_file(guest_name: str, files_by_guest: dict) -> Optional[str]:
    """同一ゲストの複数ファイルから最適なものを選択する。
    - fix_ 付きを優先（修正版）
    - _clean 付きを優先（クリーン版）
    - 日付が新しいものを優先
    """
    candidates = files_by_guest.get(guest_name, [])
    if not candidates:
        return None

    # 優先度スコアリング
    def priority(filename):
        score = 0
        if 'fix_' in filename:
            score += 100
        if '_clean' in filename:
            score += 50
        # 日付（先頭8桁）が新しいほど優先
        date_match = re.match(r'^(\d{8})', filename)
        if date_match:
            score += int(date_match.group(1)) / 100000000  # 0〜1の範囲で加算
        return score

    candidates.sort(key=priority, reverse=True)
    return candidates[0]


def build():
    """メインビルド処理。"""
    # 出力先ディレクトリ作成
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # TEKO対談動画のHTMLを収集（「撮影」を含むもの）
    source_files = [
        f.name for f in SOURCE_DIR.glob("*.html")
        if '撮影' in f.name
    ]

    # ゲスト名ごとにファイルをグループ化
    files_by_guest = {}
    for filename in source_files:
        guest = extract_guest_name(filename)
        if guest:
            if guest not in files_by_guest:
                files_by_guest[guest] = []
            files_by_guest[guest].append(filename)

    # 各ゲストの最適ファイルを選択してコピー
    mapping = {}  # ゲスト名 → コピー先ファイル名
    copied_count = 0

    for guest_name, candidates in sorted(files_by_guest.items()):
        best_file = find_best_file(guest_name, files_by_guest)
        if not best_file:
            continue

        # コピー先ファイル名（安全な名前に変換）
        dest_filename = best_file
        src_path = SOURCE_DIR / best_file
        dest_path = DEST_DIR / dest_filename

        # コピー実行
        shutil.copy2(src_path, dest_path)
        copied_count += 1

        # マッピング登録（ゲスト名の複数バリエーションを登録）
        mapping[guest_name] = dest_filename
        # 大文字小文字バリエーション
        mapping[guest_name.lower()] = dest_filename
        if guest_name != guest_name.upper():
            mapping[guest_name.upper()] = dest_filename

    # マッピングJSファイル生成
    js_content = f"""// 動画ナレッジページマッピング（自動生成）
// 生成元: scripts/build_knowledge_pages.py
// ゲスト名（小文字正規化）→ HTMLファイル名

const KnowledgePageMap = {json.dumps(mapping, ensure_ascii=False, indent=2)};

/**
 * ゲスト名からナレッジページのファイルパスを検索する。
 * マッチしない場合はnullを返す。
 * @param {{string}} guestName - プロジェクトのゲスト名
 * @returns {{string|null}} - マッチしたHTMLファイル名またはnull
 */
function findKnowledgePage(guestName) {{
  if (!guestName) return null;

  // 正規化: 小文字化、敬称除去、記号除去
  const normalized = guestName
    .toLowerCase()
    .replace(/さん$/, '')
    .replace(/氏$/, '')
    .replace(/[・\\.\\s]/g, '');

  // 完全一致
  if (KnowledgePageMap[normalized]) return KnowledgePageMap[normalized];

  // 部分一致（マップのキーがゲスト名を含む、またはその逆）
  for (const [key, file] of Object.entries(KnowledgePageMap)) {{
    const keyNorm = key.toLowerCase();
    if (keyNorm.includes(normalized) || normalized.includes(keyNorm)) {{
      return file;
    }}
  }}

  return null;
}}
"""

    with open(OUTPUT_JS, 'w', encoding='utf-8') as f:
        f.write(js_content)

    print(f"ビルド完了:")
    print(f"  対談動画HTML: {len(source_files)}件検出")
    print(f"  ゲスト数: {len(files_by_guest)}名")
    print(f"  コピー済み: {copied_count}件 → {DEST_DIR}")
    print(f"  マッピングJS: {OUTPUT_JS}")
    print()
    print("ゲスト名マッピング:")
    for guest, filename in sorted(files_by_guest.items()):
        best = find_best_file(guest, files_by_guest)
        print(f"  {guest} → {best}")


if __name__ == '__main__':
    build()
