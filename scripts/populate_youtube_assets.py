#!/usr/bin/env python3
"""YouTube素材データをDBに一括投入するスクリプト

各プロジェクトのゲスト情報（名前・年齢・職業）から
サムネイル指示書・タイトル案・概要欄テンプレートを生成し、
APIサーバーのPUT /api/projects/{id}/youtube-assets に投入する。
"""

import json
import re
import sys
import urllib.request
import urllib.error
from typing import Any

API_BASE = "http://localhost:8210"


def fetch_projects() -> list[dict]:
    """APIからプロジェクト一覧を取得"""
    req = urllib.request.Request(f"{API_BASE}/api/projects")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def generate_thumbnail_design(project: dict) -> dict:
    """ゲスト情報からZ型サムネイル指示書を生成"""
    name = project.get("guest_name", "ゲスト")
    age = project.get("guest_age")
    occupation = project.get("guest_occupation", "")

    # 年齢帯の表現
    age_label = ""
    if age:
        if age < 30:
            age_label = f"{age}歳・20代"
        elif age < 40:
            age_label = f"{age}歳・30代"
        elif age < 50:
            age_label = f"{age}歳・40代"
        else:
            age_label = f"{age}歳"

    # 職業から短いキーワードを抽出
    occ_short = _extract_occupation_short(occupation)

    # 年収情報の抽出（タイトルやIDから）
    income_info = _extract_income_from_id(project.get("id", ""), project.get("title", ""))

    # フックテキスト生成
    if income_info:
        hook_text = f"{age_label} {occ_short}\n年収{income_info}"
    elif age_label:
        hook_text = f"{age_label} {occ_short}"
    else:
        hook_text = f"{name}の不動産投資ストーリー"

    return {
        "overall_concept": f"{name}さんの対談動画 — {occ_short}が不動産投資を選んだ理由",
        "font_suggestion": "ヒラギノ角ゴ Pro W6 / Noto Sans JP Bold — 視認性重視",
        "background_suggestion": "ダークグラデーション（#1a1a2e → #16213e）+ ゲスト写真右配置",
        "top_left": {
            "role": "フック（数字 or パンチライン）",
            "content": hook_text,
            "color_suggestion": "白文字 + 黄色アクセント（年収部分）",
            "notes": "Z型の起点。最も目を引くゾーン。文字サイズ最大"
        },
        "top_right": {
            "role": "人物シルエット＋属性",
            "content": f"{name}さん（{age_label}）" if age_label else f"{name}さん",
            "color_suggestion": "写真 + 白テキストオーバーレイ",
            "notes": "ゲスト写真を配置。名前と属性を重ねる"
        },
        "diagonal": {
            "role": "コンテンツ要素（対談のテーマ）",
            "content": _generate_diagonal_content(occupation, income_info),
            "color_suggestion": "薄い青系バッジ",
            "notes": "Z型の対角線。視線誘導の中継点"
        },
        "bottom_right": {
            "role": "ベネフィット（視聴者への約束）",
            "content": "不動産投資のリアルが分かる",
            "color_suggestion": "赤 or オレンジのCTAカラー",
            "notes": "Z型の終点。次のアクション（再生）を促す"
        }
    }


def generate_title_proposals(project: dict) -> dict:
    """ゲスト情報からタイトル案を生成"""
    name = project.get("guest_name", "ゲスト")
    age = project.get("guest_age")
    occupation = project.get("guest_occupation", "")
    occ_short = _extract_occupation_short(occupation)
    income_info = _extract_income_from_id(project.get("id", ""), project.get("title", ""))

    candidates = []

    # パターン1: 数字系（年収フック）
    if income_info:
        candidates.append({
            "title": f"年収{income_info}の{occ_short}が不動産投資を始めた理由【{name}さん対談】",
            "target_segment": "同年代・同業種のサラリーマン投資家",
            "appeal_type": "数字系",
            "rationale": "年収という具体的数字でターゲット層の共感と好奇心を喚起"
        })

    # パターン2: ストーリー系
    if age:
        candidates.append({
            "title": f"【{age}歳】{occ_short}が語る「会社員×不動産投資」のリアル",
            "target_segment": "本業を持ちながら投資を検討している層",
            "appeal_type": "ストーリー系",
            "rationale": "リアルなストーリーへの期待感を醸成"
        })

    # パターン3: 問いかけ系
    candidates.append({
        "title": f"なぜ{occ_short}は不動産投資を選んだのか？{name}さんの決断",
        "target_segment": "投資手法を比較検討中の層",
        "appeal_type": "問いかけ系",
        "rationale": "「なぜ」で視聴者の知的好奇心を刺激"
    })

    # パターン4: 権威系（専門職の場合）
    if _is_professional(occupation):
        candidates.append({
            "title": f"{occ_short}が見抜いた不動産投資の本質【プロの視点】",
            "target_segment": "高年収専門職層",
            "appeal_type": "権威系",
            "rationale": "専門性を活かした権威付け"
        })

    # パターン5: 汎用
    candidates.append({
        "title": f"{name}さん対談 — {occ_short}の不動産投資ジャーニー【TEKO】",
        "target_segment": "TEKOチャンネル視聴者全般",
        "appeal_type": "ブランド系",
        "rationale": "チャンネルブランドと紐付けた信頼訴求"
    })

    return {
        "candidates": candidates,
        "recommended_index": 0,
        "generation_method": "rule_based_v1"
    }


def generate_video_description(project: dict) -> str:
    """ゲスト情報からYouTube概要欄テキストを生成"""
    name = project.get("guest_name", "ゲスト")
    age = project.get("guest_age")
    occupation = project.get("guest_occupation", "")
    occ_short = _extract_occupation_short(occupation)
    shoot_date = project.get("shoot_date", "")

    age_str = f"{age}歳" if age else ""

    lines = []

    # 冒頭フック
    if age and occupation:
        lines.append(f"{age_str}、{occ_short}の{name}さんが語る不動産投資のリアル。")
    else:
        lines.append(f"{name}さんが語る不動産投資のリアル。")

    lines.append(f"本業を持ちながら不動産投資に挑戦する{name}さんの考え方や決断の背景に迫ります。")
    lines.append("")

    # ゲストプロフィール
    lines.append("▼ ゲストプロフィール")
    lines.append(f"・名前: {name}さん")
    if age:
        lines.append(f"・年齢: {age_str}")
    if occupation:
        lines.append(f"・職業: {occupation}")
    lines.append("")

    # チャプター（プレースホルダー）
    lines.append("▼ チャプター")
    lines.append("0:00 オープニング・自己紹介")
    lines.append("※ 編集完了後にタイムスタンプを追加")
    lines.append("")

    # CTA
    lines.append("▼ TEKOについて")
    lines.append("不動産投資コミュニティ「TEKO」の対談シリーズです。")
    lines.append("メンバーのリアルな声をお届けしています。")
    lines.append("")

    # ハッシュタグ
    lines.append("#不動産投資 #TEKO #対談 #サラリーマン投資家")
    if occ_short:
        lines.append(f"#{occ_short.replace(' ', '')}")

    return "\n".join(lines)


# --- ヘルパー関数 ---

def _extract_occupation_short(occupation: str) -> str:
    """職業から短いキーワードを抽出"""
    if not occupation:
        return "会社員"

    # 主要キーワードのマッピング
    keywords = [
        ("公認会計士", "公認会計士"),
        ("薬剤師", "薬剤師"),
        ("理学療法士", "理学療法士"),
        ("MR", "製薬MR"),
        ("医薬情報", "製薬MR"),
        ("コンサルティング", "ITコンサルタント"),
        ("コンサルタント", "ITコンサルタント"),
        ("フリーランス", "フリーランスITコンサル"),
        ("不動産デベロッパー", "不動産デベロッパー"),
        ("化学メーカー", "化学メーカー勤務"),
        ("製薬", "製薬企業勤務"),
        ("半導体", "半導体メーカー営業"),
        ("GAFA", "GAFA管理職"),
        ("外資系IT", "外資IT企業"),
        ("IT関係", "IT企業勤務"),
        ("IT企業", "IT企業勤務"),
        ("管理職", "大手企業管理職"),
        ("営業", "営業職"),
        ("製造業", "製造業勤務"),
        ("施工管理", "不動産施工管理"),
        ("空調設備", "設備保守フリーランス"),
        ("SIer", "SIerプロダクトマネージャー"),
        ("監査法人", "監査法人勤務"),
        ("飲料メーカー", "大手飲料メーカー勤務"),
        ("通信", "通信企業営業"),
        ("インフラ企業", "インフラ企業勤務"),
        ("会計", "会計アドバイザー"),
    ]

    for keyword, label in keywords:
        if keyword in occupation:
            return label

    # デフォルト: 最初の主要名詞を抽出
    return occupation[:20] if len(occupation) > 20 else occupation


def _extract_income_from_id(project_id: str, title: str) -> str:
    """プロジェクトIDやタイトルから年収情報を抽出"""
    text = project_id + " " + title

    # パターン: 年収XXXX万 or 年収XXX万
    match = re.search(r'年収(\d{3,4})万', text)
    if match:
        return f"{match.group(1)}万円"

    # パターン: 年収約XXX万
    match = re.search(r'年収約?(\d{3,4})万', text)
    if match:
        return f"{match.group(1)}万円"

    return ""


def _generate_diagonal_content(occupation: str, income_info: str) -> str:
    """対角線コンテンツ（テーマ）を生成"""
    if "引退" in (occupation or ""):
        return "サラリーマン引退→不動産投資家への転身"
    if "フリーランス" in (occupation or ""):
        return "フリーランス×不動産投資の相乗効果"
    if income_info:
        return f"高年収会社員の資産形成戦略"
    return "本業×不動産投資の両立法"


def _is_professional(occupation: str) -> bool:
    """専門職かどうかを判定"""
    pro_keywords = ["会計士", "薬剤師", "理学療法士", "MR", "コンサル", "管理職", "デベロッパー"]
    return any(kw in (occupation or "") for kw in pro_keywords)


def put_youtube_assets(project_id: str, data: dict) -> dict:
    """APIにYouTube素材を投入"""
    url = f"{API_BASE}/api/projects/{urllib.parse.quote(project_id, safe='')}/youtube-assets"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": str(e), "detail": error_body, "project_id": project_id}


def main():
    import urllib.parse

    print("=== YouTube素材データ一括投入スクリプト ===\n")

    # 1. プロジェクト一覧取得
    projects = fetch_projects()
    print(f"プロジェクト数: {len(projects)}")

    # 2. 既存YouTube素材の確認
    existing_count = 0
    for p in projects:
        try:
            url = f"{API_BASE}/api/projects/{urllib.parse.quote(p['id'], safe='')}/youtube-assets"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as resp:
                existing_count += 1
        except urllib.error.HTTPError:
            pass
    print(f"既存YouTube素材: {existing_count}件")

    # 3. 各プロジェクトにYouTube素材を生成・投入
    success = 0
    errors = []

    for i, project in enumerate(projects, 1):
        pid = project["id"]

        # サムネイル指示書
        thumbnail = generate_thumbnail_design(project)

        # タイトル案
        titles = generate_title_proposals(project)

        # 概要欄
        description = generate_video_description(project)

        # API投入
        payload = {
            "thumbnail_design": thumbnail,
            "title_proposals": titles,
            "description_original": description,
        }

        result = put_youtube_assets(pid, payload)

        if "error" in result:
            errors.append({"id": pid, "error": result})
            status = "ERROR"
        else:
            success += 1
            status = "OK"

        name = project.get("guest_name", "?")
        title_count = len(titles.get("candidates", []))
        print(f"  [{i:02d}/{len(projects)}] {status} | {name} | タイトル案{title_count}件 | {pid[:50]}")

    # 4. 結果サマリー
    print(f"\n=== 完了 ===")
    print(f"  成功: {success}/{len(projects)}")
    print(f"  エラー: {len(errors)}")

    if errors:
        print("\nエラー詳細:")
        for e in errors:
            print(f"  - {e['id']}: {e['error']}")

    # 5. 検証: APIから件数確認
    try:
        url = f"{API_BASE}/api/dashboard/summary"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            summary = json.loads(resp.read().decode())
            print(f"\nダッシュボードサマリー:")
            print(f"  プロジェクト数: {summary.get('total_projects', '?')}")
            print(f"  YouTube素材数: {summary.get('with_youtube_assets', '?')}")
    except Exception as ex:
        print(f"\nサマリー取得エラー: {ex}")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
