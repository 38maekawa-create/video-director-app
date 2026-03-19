from __future__ import annotations
"""NEW-1: 演出ディレクション生成

テロップ強調・色変え・画角変更のタイミング指示をタイムライン形式で生成する。
LLM（Claude Sonnet）を使って文脈分析 → タイムライン形式の指示を生成。
FB学習ループ: FeedbackLearnerのルールを自動反映してディレクション品質を向上させる。
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from ..integrations.ai_dev5_connector import VideoData, HighlightScene
from .guest_classifier import ClassificationResult
from .income_evaluator import IncomeEvaluation

if TYPE_CHECKING:
    from ..tracker.feedback_learner import FeedbackLearner, LearningRule
    from ..tracker.video_learner import VideoLearner, VideoLearningRule
    from ..tracker.edit_learner import EditLearner, EditLearningRule


@dataclass
class DirectionEntry:
    """演出ディレクションの1エントリ"""
    timestamp: str  # "MM:SS"
    direction_type: str  # "telop" / "camera" / "color" / "composite"
    instruction: str  # 具体的な演出指示
    reason: str  # この演出をする理由
    priority: str  # "high" / "medium" / "low"


@dataclass
class DirectionTimeline:
    """演出ディレクション全体"""
    entries: list = field(default_factory=list)  # List[DirectionEntry]
    llm_analysis: str = ""  # LLMによる追加分析（あれば）
    applied_rules: list = field(default_factory=list)  # 適用されたFB学習ルール


def generate_directions(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    feedback_learner=None,
    video_learner=None,
    edit_learner=None,
    project_category: str | None = None,
) -> DirectionTimeline:
    """ルールベースで演出ディレクションを生成する

    Args:
        video_data: 動画データ
        classification: ゲスト分類結果
        income_eval: 年収演出判断結果
        feedback_learner: FeedbackLearnerインスタンス（FB学習ルール反映用、Noneなら無視）
        video_learner: VideoLearnerインスタンス（映像トラッキング学習ルール反映用、Noneなら無視）
        edit_learner: EditLearnerインスタンス（手修正学習ルール反映用、Noneなら無視）
        project_category: プロジェクトカテゴリ（teko_member / teko_realestate / None）
            カテゴリに応じてディレクションのトーン・演出指示を分岐する（将来拡張ポイント）

    将来拡張:
        project_category == "teko_realestate" の場合:
            - 不動産データ（物件価格・利回り等）の数字テロップを優先的に強調
            - 投資実績・CF関連のパンチラインを重視
            - テロップカラーをゴールド系に統一
        project_category == "teko_member" の場合:
            - ゲストの人柄・ストーリー寄りの演出
            - 転職・年収アップのストーリーラインを強調
            - テロップカラーをブランドカラー系に統一
    """
    entries = []

    for highlight in video_data.highlights:
        highlight_entries = _generate_for_highlight(
            highlight, classification, income_eval
        )
        entries.extend(highlight_entries)

    # FB学習ルールの適用
    applied_rules = []
    if feedback_learner is not None:
        fb_entries, applied_rules = _apply_learned_rules(
            video_data, classification, income_eval, feedback_learner
        )
        entries.extend(fb_entries)

    # 映像トラッキング学習ルールの適用（FBと同じ仕組み）
    if video_learner is not None:
        vl_entries, vl_applied = _apply_learned_rules(
            video_data, classification, income_eval, video_learner
        )
        entries.extend(vl_entries)
        applied_rules.extend(vl_applied)

    # 手修正学習ルールの適用（FBと同じ仕組み。手修正由来は[手修正学習]タグ付き）
    if edit_learner is not None:
        el_entries, el_applied = _apply_learned_rules(
            video_data, classification, income_eval, edit_learner
        )
        entries.extend(el_entries)
        applied_rules.extend(el_applied)

    # タイムスタンプ順にソート
    entries.sort(key=lambda e: _timestamp_to_seconds(e.timestamp))

    # LLM分析を試行（APIキーがなければスキップ。FB学習ルール+映像学習ルール+手修正学習ルールをプロンプトに注入）
    llm_analysis = ""
    try:
        llm_analysis = _llm_analyze(
            video_data, classification, income_eval,
            feedback_learner=feedback_learner, video_learner=video_learner,
            edit_learner=edit_learner,
        )
    except Exception:
        pass

    return DirectionTimeline(entries=entries, llm_analysis=llm_analysis, applied_rules=applied_rules)


def _generate_for_highlight(
    highlight: HighlightScene,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
) -> list[DirectionEntry]:
    """ハイライトシーンから演出指示を生成"""
    entries = []
    ts = highlight.timestamp
    text = highlight.text
    category = highlight.category

    # テロップ強調タイミング
    if category == "実績数字":
        # 年収・実績の数字が出た瞬間 → テロップ強調
        numbers = re.findall(r"\d+万|年収\d+|月利?\d+万|月収?\d+万", text)
        if numbers:
            entries.append(DirectionEntry(
                timestamp=ts,
                direction_type="telop",
                instruction=f"テロップ強調: 「{numbers[0]}」を大きく表示、色変え（赤orゴールド）",
                reason=f"実績数字の出現（{', '.join(numbers)}）",
                priority="high",
            ))
            # 色変えも同時
            entries.append(DirectionEntry(
                timestamp=ts,
                direction_type="color",
                instruction="色変え: テロップ出現に合わせて画面演出（フラッシュ or 背景色変更）",
                reason="強調テロップ出現時の色変え",
                priority="medium",
            ))

    if category == "パンチライン":
        # キー発言 → テロップ強調 + 寄り
        # テキストから短いパンチラインを抽出
        punch = _extract_punchline(text)
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="telop",
            instruction=f"テロップ強調: 「{punch}」（パンチライン）",
            reason="キー発言の強調",
            priority="high",
        ))
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="camera",
            instruction="画角変更: ワイド → 寄り（アップ）でキー発言を際立たせる",
            reason="パンチライン発言時の寄り",
            priority="high",
        ))

    if category == "属性紹介":
        # 属性紹介 → テロップで属性情報表示
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="telop",
            instruction=f"属性テロップ: ゲストの肩書き・属性情報を表示",
            reason="ゲスト属性の視覚的提示",
            priority="medium",
        ))

    if category == "TEKO価値":
        # TEKO価値の証言 → 2ショットで信頼感演出
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="camera",
            instruction="画角: 2ショット（ワイド）で対話の空気感を見せる",
            reason="TEKO価値の証言は対話の雰囲気が重要",
            priority="medium",
        ))

    if category == "メッセージ":
        # 締めメッセージ → 寄りで説得力
        entries.append(DirectionEntry(
            timestamp=ts,
            direction_type="camera",
            instruction="画角変更: 寄り（アップ）で視聴者への直接メッセージ感",
            reason="視聴者への直接メッセージ",
            priority="medium",
        ))

    # 層a/bの強さ強調シーン → 色変え
    if classification.tier in ("a", "b") and category in ("実績数字", "パンチライン"):
        if not any(e.direction_type == "color" for e in entries):
            entries.append(DirectionEntry(
                timestamp=ts,
                direction_type="color",
                instruction=f"色変え: {classification.tier_label}の強さ強調シーン",
                reason=f"ゲスト{classification.tier_label}の強さ演出",
                priority="medium",
            ))

    return entries


def _extract_punchline(text: str) -> str:
    """長いテキストからパンチラインを抽出（50文字以内に短縮）"""
    if len(text) <= 50:
        return text
    # 。で分割して最初の文を取得
    sentences = text.split("。")
    if sentences and len(sentences[0]) <= 50:
        return sentences[0]
    # 先頭50文字 + ...
    return text[:47] + "..."


def _timestamp_to_seconds(ts: str) -> int:
    """タイムスタンプを秒数に変換（不正フォーマットは0を返す）"""
    try:
        parts = ts.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, IndexError):
        pass
    return 0


def _apply_learned_rules(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    feedback_learner: "FeedbackLearner",
) -> tuple[list[DirectionEntry], list]:
    """FB学習ルールに基づく追加ディレクションを生成

    FeedbackLearnerから有効なルールを取得し、各ハイライトシーンに
    該当するルールがあれば追加の演出指示を生成する。

    Returns:
        (追加エントリ一覧, 適用されたルールのリスト)
    """
    entries = []
    applied_rules = []

    active_rules = feedback_learner.get_active_rules()
    if not active_rules:
        return entries, applied_rules

    # カテゴリ → ディレクションタイプのマッピング
    category_to_direction = {
        "cutting": "composite",
        "color": "color",
        "telop": "telop",
        "bgm": "composite",
        "camera": "camera",
        "composition": "camera",
        "tempo": "composite",
        "general": "composite",
    }

    for rule in active_rules:
        rule_applied = False
        direction_type = category_to_direction.get(rule.category, "composite")

        for highlight in video_data.highlights:
            # ルールのカテゴリとハイライトの内容を照合
            if _rule_matches_highlight(rule, highlight):
                entries.append(DirectionEntry(
                    timestamp=highlight.timestamp,
                    direction_type=direction_type,
                    instruction=f"[FB学習] {rule.rule_text}",
                    reason=f"FB学習ルール適用（{rule.id}、優先度: {rule.priority}）",
                    priority=rule.priority,
                ))
                rule_applied = True

        if rule_applied:
            applied_rules.append({
                "rule_id": rule.id,
                "rule_text": rule.rule_text,
                "category": rule.category,
                "priority": rule.priority,
            })
            # ルールの適用回数を更新
            rule.applied_count += 1

    # ルール適用回数を永続化
    if applied_rules:
        try:
            feedback_learner._save()
        except Exception:
            pass

    return entries, applied_rules


def _rule_matches_highlight(rule: "LearningRule", highlight: HighlightScene) -> bool:
    """ルールがハイライトシーンに適用可能か判定

    ルールのカテゴリとハイライトのカテゴリ・テキスト内容を照合する。

    Args:
        rule: 適用候補の学習ルール
        highlight: 対象ハイライトシーン

    Returns:
        ルールが適用可能な場合True
    """
    rule_text_lower = rule.rule_text.lower()
    highlight_text_lower = (highlight.text or "").lower()
    highlight_category_lower = (highlight.category or "").lower()

    # ルールのカテゴリに関連するキーワードがハイライトに含まれるか
    category_keywords = {
        "cutting": ["カット", "切り", "繋ぎ", "トランジション"],
        "color": ["色", "カラー", "明る", "暗"],
        "telop": ["テロップ", "字幕", "テキスト", "文字"],
        "bgm": ["bgm", "音楽", "se", "効果音"],
        "camera": ["カメラ", "アングル", "画角", "ズーム"],
        "composition": ["構図", "レイアウト", "配置"],
        "tempo": ["テンポ", "リズム", "スピード", "間"],
    }

    # カテゴリマッチ: ルールのカテゴリに関連するハイライトカテゴリ
    category_map = {
        "cutting": ["パンチライン", "実績数字"],
        "color": ["実績数字", "パンチライン"],
        "telop": ["実績数字", "パンチライン", "属性紹介"],
        "bgm": ["メッセージ", "TEKO価値"],
        "camera": ["パンチライン", "TEKO価値", "メッセージ"],
        "composition": ["属性紹介", "TEKO価値"],
        "tempo": ["パンチライン", "メッセージ"],
    }

    matching_categories = category_map.get(rule.category, [])
    if highlight.category in matching_categories:
        return True

    # テキストベースのマッチング: ルールテキスト内のキーワードがハイライトに含まれるか
    keywords = category_keywords.get(rule.category, [])
    for kw in keywords:
        if kw.lower() in highlight_text_lower:
            return True

    return False


def _llm_analyze(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    feedback_learner=None,
    video_learner=None,
    edit_learner=None,
) -> str:
    """LLM（teko_core.llm経由 — MAX定額内）による追加分析。FB学習ルール+映像学習ルールがあればプロンプトに注入する"""

    # ハイライトシーンのサマリー
    highlights_text = "\n".join([
        f"[{h.timestamp}] {h.speaker}: {h.text} ({h.category})"
        for h in video_data.highlights[:15]
    ])

    # FB学習ルールがあればLLMプロンプトに注入
    learned_rules_text = ""
    if feedback_learner is not None:
        try:
            active_rules = feedback_learner.get_active_rules()
            if active_rules:
                rules_lines = [f"- [{r.category}] {r.rule_text} (優先度: {r.priority})" for r in active_rules[:10]]
                learned_rules_text = "\n\n過去のフィードバックから学習した演出ルール（これらを優先的に反映すること）:\n" + "\n".join(rules_lines)
        except Exception:
            pass

    # 映像トラッキング学習インサイトもLLMプロンプトに注入
    video_insights_text = ""
    if video_learner is not None:
        try:
            insights = video_learner.get_insights_for_direction()
            if insights:
                video_insights_text = "\n\n外部映像トラッキングから学習した演出パターン（参考にすること）:\n" + "\n".join(f"- {i}" for i in insights[:10])
        except Exception:
            pass

    # 手修正学習ルールもLLMプロンプトに注入
    edit_rules_text = ""
    if edit_learner is not None:
        try:
            edit_rules = edit_learner.get_active_rules()
            if edit_rules:
                edit_lines = [f"- [{r.category}] {r.rule_text} (優先度: {r.priority})" for r in edit_rules[:10]]
                edit_rules_text = "\n\n手修正から学習した演出ルール（最優先で反映すること。手修正は直接的な品質改善指示である）:\n" + "\n".join(edit_lines)
        except Exception:
            pass

    # タイムラインコンテキストの構築
    total_duration = video_data.duration if video_data.duration else "不明"
    highlight_count = len(video_data.highlights)

    # ハイライトのタイムスタンプを秒数に変換
    timestamps_sec = []
    for h in video_data.highlights:
        parts = h.timestamp.replace("[", "").replace("]", "").split(":")
        try:
            if len(parts) == 2:
                timestamps_sec.append(int(parts[0]) * 60 + int(parts[1]))
            elif len(parts) == 3:
                timestamps_sec.append(int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]))
        except (ValueError, IndexError):
            pass

    # ハイライト密度分析（3件以上で判定）
    highlight_density = "不明"
    if len(timestamps_sec) >= 3:
        mid = max(timestamps_sec) / 2
        first_half = sum(1 for t in timestamps_sec if t <= mid)
        second_half = sum(1 for t in timestamps_sec if t > mid)
        if first_half > second_half * 1.5:
            highlight_density = "前半密集型（前半にハイライトが集中）"
        elif second_half > first_half * 1.5:
            highlight_density = "後半盛り上がり型（後半にハイライトが集中）"
        else:
            highlight_density = "均等分散型（全体にバランスよく分布）"

    # ハイライト間ギャップの検出
    gap_warnings = []
    if len(timestamps_sec) >= 2:
        sorted_ts = sorted(timestamps_sec)
        for i in range(1, len(sorted_ts)):
            gap = sorted_ts[i] - sorted_ts[i - 1]
            if gap > 300:  # 5分以上のギャップ
                gap_min = gap // 60
                gap_warnings.append(f"  - [{sorted_ts[i-1]//60:02d}:{sorted_ts[i-1]%60:02d}]〜[{sorted_ts[i]//60:02d}:{sorted_ts[i]%60:02d}] に約{gap_min}分のギャップあり → つなぎ演出を検討")

    gap_text = ""
    if gap_warnings:
        gap_text = "\n\nハイライト間の大きなギャップ（つなぎ演出が必要な箇所）:\n" + "\n".join(gap_warnings)

    # ゲストの代替の強み情報
    alt_strengths_text = ""
    if income_eval.alternative_strengths:
        strengths_lines = [f"  - {s.category}: {s.description}" for s in income_eval.alternative_strengths]
        alt_strengths_text = "\n- 代替の強み:\n" + "\n".join(strengths_lines)

    # ゲストプロフィール情報
    guest_profile_text = ""
    if video_data.guest_summary:
        guest_profile_text = f"\n- ゲスト概要: {video_data.guest_summary}"
    if video_data.profiles:
        for p in video_data.profiles[:3]:
            name = getattr(p, "name", "")
            role = getattr(p, "role", "")
            desc = getattr(p, "description", "")
            if name and name != "前川":
                guest_profile_text += f"\n- ゲストプロフィール: {name} / {role} / {desc}"

    # 層別の訴求軸指示
    tier_direction = {
        "a": """【層a演出方針 — 誰が見ても圧倒的に強い層】
- この人の「強さ」「ハイキャリアさ」を前面に押し出す。キャリアの中で最も強い部分にフォーカスした演出
- 権威性・専門性・ブランド力を視覚化する。元○○のキャプション、年収テロップの大表示
- テロップは洗練されたデザイン。過度な派手さよりも"格"を演出する
- 発言の重みを活かす: 間を長めに取り、視聴者に考えさせる編集
- ターゲット別視聴後感: 1層（ハイキャリア）→「この基準が当たり前の世界があるのか」「この人たちの仲間に入りたい」（ポジティブな焦燥感と所属欲求）""",
        "b": """【層b演出方針 — 相対的な強さの言語化が必要な層】
- 年収以外の文脈で「強さ」を言語化する: 在籍企業のブランド力、キャリアパスの希少性、勤務形態の自由度、転職先の年収見込み、副業実績
- Before/After構成を意識: 過去の苦労→現在の成功を対比させるカット編集
- テロップは感情に訴える言葉を大きく、数字は補助的に使う
- 固有名詞の伏せ方を演出に転換: ピー音 + 「誰もが知る○○業界の超大手」で権威性を増す
- ターゲット別視聴後感: 2層→「自分と同じ悩みを持つ人がここで解決策を見つけている」（共感とコミュニティへの安心感）""",
        "c": """【層c演出方針 — 自営業家系（2代目・3代目）サラリーマン層】
- 強さに加えて、自営業家系の背景やご本人の葛藤や経歴にも重きを置く
- TEKOを通じてどう変化したかという「ストーリー」を中心に構成
- 等身大感・行動のきっかけ・「自分もできそう」を演出する
- 具体的な行動ステップや意思決定の瞬間にフォーカスする
- BGMは明るく前向き。挑戦・一歩踏み出す感を演出する""",
    }
    tier_text = tier_direction.get(classification.tier, tier_direction["b"])

    # 強さの根拠に基づく演出ポイント
    strength_direction = """
【ゲストの「強さの根拠」ごとの演出指示】
以下のパターンに該当する場合、対応する演出を必ず検討すること:
- 企業ブランド（元アクセンチュア、元ゴールドマン等）→ 社名をテロップで大きく表示。ロゴ風デザインで権威性を視覚化。初登場時に「元○○」を画面下部にキャプション表示
- 年収実績が強調対象の場合 → 数字を画面の30%以上のサイズでテロップ表示。パンチライン化して視聴者の目を引く。数字が出る瞬間にSE（効果音）を入れる
- 転職・キャリアチェンジの場合 → Before/After構成を意識した編集。過去の状況と現在を交互にカットで見せる。色温度を寒色（過去）→暖色（現在）に変化させる
- 副業・複業成功の場合 → 本業との二面性をカット切り替えで演出。「昼は○○、夜は○○」的な対比構成。テロップで二つの顔を並列表示"""

    prompt = f"""以下はTEKO対談インタビュー動画のハイライトシーンです。
動画編集者向けに、追加の演出ディレクション提案を5〜8個生成してください。

## 動画メタ情報
- タイトル: {video_data.title}
- 全体尺: {total_duration}
- ハイライト数: {highlight_count}個
- ハイライト密度: {highlight_density}

## ゲスト情報
- ゲスト分類: {classification.tier_label}
- 分類理由: {classification.reason}
- 見せ方テンプレート: {classification.presentation_template}
- 年収演出判断: {income_eval.emphasis_reason}
- テロップ提案: {income_eval.telop_suggestion}{guest_profile_text}{alt_strengths_text}

## 層別演出方針（この方針に必ず従うこと）
{tier_text}
{strength_direction}

## ハイライトシーン
{highlights_text}{gap_text}{learned_rules_text}{video_insights_text}{edit_rules_text}

## 出力フォーマット
以下のフォーマットで、具体的なタイムスタンプと演出指示を出してください:
[MM:SS] 演出タイプ（テロップ/カット割り/色彩/BGM/テンポ/画角）: 具体的な指示内容

## 演出・映像技法の具体性基準
各ディレクションには以下のレベルの具体性を持たせること:
- カット割り: 「ゲストのアップ→引きのカット切り替え」「2ショット→ゲスト単独に切り替え」等、具体的なカメラワークを指定
- 色彩: 「パンチライン出現時にフラッシュ効果」「重要発言で色温度を暖色に変化」「Before区間は寒色系フィルター」等
- テロップ: 「年収数字は画面の30%以上のサイズで」「引用や名言は手書き風フォント」「企業名はロゴ風デザインで」等
- BGM: 「ここでBGMのトーンをマイナー→メジャーに切り替え」「静寂→盛り上がりの緩急をつける」「SE（効果音）で数字出現を強調」等
- テンポ: 「ここは間を2秒取って重みを出す」「ここはテンポよく0.5秒カットで畳み掛ける」「沈黙を活かして余韻を残す」等

## 注意事項
- ディレクションマニュアルの原則に従うこと
- 年収以外の強さ（企業ブランド・勤務形態・キャリアパス等）も積極的に活用すること
- 固有名詞の扱いに注意（迷ったら伏せる）
- ハイライト間のギャップが大きい箇所には「つなぎ演出」（ダイジェストカット、ナレーション挿入、チャプタータイトル等）を提案すること
- 過去のFB学習ルールが注入されている場合、それらを優先的に反映し、どのルールを適用したか明示すること
- 映像トラッキングインサイトがある場合、外部映像で成功している演出パターンを積極的に取り入れること
"""

    from teko_core.llm import ask
    return ask(prompt, model="sonnet", max_tokens=2000, timeout=120)


def get_learning_context(feedback_learner: "FeedbackLearner" = None, video_learner: "VideoLearner" = None, edit_learner: "EditLearner" = None) -> dict:
    """FB学習ルール+映像学習ルールのコンテキストを取得する

    ディレクション生成の前に学習状況を確認したり、
    APIレスポンスで学習ルールの適用状況を返すために使用する。

    Args:
        feedback_learner: FeedbackLearnerインスタンス（Noneなら空を返す）
        video_learner: VideoLearnerインスタンス（Noneなら映像学習部分は空）
        edit_learner: EditLearnerインスタンス（Noneなら手修正学習部分は空）

    Returns:
        dict: {
            "active_rules": [...],  # 有効なルール一覧（FB+映像+手修正統合）
            "insights": {...},      # 学習状況サマリー
            "has_rules": bool,      # ルールがあるかどうか
            "video_learning": {...},  # 映像学習状況
            "edit_learning": {...},   # 手修正学習状況
        }
    """
    all_rules = []
    insights = {}
    video_learning = {}

    # FB学習ルール
    if feedback_learner is not None:
        try:
            fb_rules = feedback_learner.get_active_rules()
            insights = feedback_learner.get_insights()
            all_rules.extend([
                {
                    "id": r.id,
                    "rule_text": r.rule_text,
                    "category": r.category,
                    "priority": r.priority,
                    "applied_count": r.applied_count,
                    "source": "feedback",
                }
                for r in fb_rules
            ])
        except Exception:
            pass

    # 映像トラッキング学習ルール
    if video_learner is not None:
        try:
            vl_rules = video_learner.get_active_rules()
            video_learning = video_learner.get_insights()
            all_rules.extend([
                {
                    "id": r.id,
                    "rule_text": r.rule_text,
                    "category": r.category,
                    "priority": r.priority,
                    "applied_count": r.applied_count,
                    "source": "video_tracking",
                }
                for r in vl_rules
            ])
        except Exception:
            pass

    # 手修正学習ルール
    edit_learning = {}
    if edit_learner is not None:
        try:
            el_rules = edit_learner.get_active_rules()
            edit_learning = edit_learner.get_insights()
            all_rules.extend([
                {
                    "id": r.id,
                    "rule_text": r.rule_text,
                    "category": r.category,
                    "priority": r.priority,
                    "applied_count": r.applied_count,
                    "source": "edit",
                }
                for r in el_rules
            ])
        except Exception:
            pass

    return {
        "active_rules": all_rules,
        "insights": insights,
        "has_rules": len(all_rules) > 0,
        "video_learning": video_learning,
        "edit_learning": edit_learning,
    }
