from __future__ import annotations
"""HTMLレポート生成 — ディレクションレポートをHTMLに組み立てる"""

import html
from datetime import datetime
from .template import CSS_STYLE
from ..integrations.ai_dev5_connector import VideoData
from ..analyzer.guest_classifier import ClassificationResult
from ..analyzer.income_evaluator import IncomeEvaluation
from ..analyzer.proper_noun_filter import ProperNounEntry
from ..analyzer.target_labeler import TargetLabelResult
from ..analyzer.direction_generator import DirectionTimeline


def generate_direction_html(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    proper_nouns: list[ProperNounEntry],
    target_result: TargetLabelResult,
    direction_timeline: DirectionTimeline,
) -> str:
    """ディレクションレポートのHTMLを生成する"""
    guest_name = _get_guest_name(video_data)
    profile = video_data.profiles[0] if video_data.profiles else None

    sections = [
        _build_header(video_data, guest_name, profile, classification, income_eval),
        _build_guest_classification(classification),
        _build_income_direction(income_eval),
        _build_proper_nouns(proper_nouns),
        _build_direction_timeline(direction_timeline),
        _build_target_checklist(target_result),
        _build_highlights(video_data),
        _build_transcript(video_data),
        _build_footer(),
    ]

    body = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ディレクションレポート: {_esc(guest_name)}</title>
<style>{CSS_STYLE}</style>
</head>
<body>
<div class="container">
{body}
</div>
</body>
</html>"""


def _build_header(video_data, guest_name, profile, classification, income_eval):
    """ヘッダーセクション"""
    meta_items = []

    if profile:
        meta_items.append(("年齢", profile.age or "不明"))
        meta_items.append(("本業", profile.occupation or "不明"))
        meta_items.append(("年収", profile.income or "不明"))

    meta_items.append(("動画時間", video_data.duration or "不明"))
    meta_items.append(("種別", video_data.video_type or "不明"))

    # 分類結果
    tier_class = f"tier-{classification.tier}"
    meta_items.append(("ゲスト層", f'<span class="tier-badge {tier_class}">{classification.tier_label}</span>'))

    emphasis_class = "emphasis-on" if income_eval.emphasize else "emphasis-off"
    emphasis_text = "強調ON" if income_eval.emphasize else "強調OFF"
    meta_items.append(("年収演出", f'<span class="{emphasis_class}">{emphasis_text}</span>'))

    meta_grid = "\n".join([
        f'<div class="meta-item"><div class="meta-label">{_esc(label)}</div><div class="meta-value">{value}</div></div>'
        for label, value in meta_items
    ])

    return f"""<header>
<h1>ディレクションレポート: {_esc(guest_name)}</h1>
<div class="meta-grid">
{meta_grid}
</div>
</header>"""


def _build_guest_classification(classification):
    """A-1: ゲスト層判定結果"""
    tier_class = f"tier-{classification.tier}"
    return f"""<section id="guest-classification" class="section">
<h2>ゲスト層分類 (A-1)</h2>
<p><span class="tier-badge {tier_class}">{_esc(classification.tier_label)}</span>
（信頼度: {_esc(classification.confidence)}）</p>
<p><strong>判定理由:</strong> {_esc(classification.reason)}</p>
<p><strong>見せ方テンプレート:</strong> {_esc(classification.presentation_template)}</p>
</section>"""


def _build_income_direction(income_eval):
    """A-2/A-3: 年収演出判断"""
    content = f"""<section id="income-direction" class="section">
<h2>年収演出判断 (A-2)</h2>
<p><strong>判定:</strong> <span class="{'emphasis-on' if income_eval.emphasize else 'emphasis-off'}">
{'強調ON' if income_eval.emphasize else '強調OFF'}</span></p>
<p><strong>理由:</strong> {_esc(income_eval.emphasis_reason)}</p>"""

    if income_eval.telop_suggestion:
        content += f"\n<p><strong>テロップ提案:</strong> {_esc(income_eval.telop_suggestion)}</p>"

    # A-3: 代替の強み
    if income_eval.alternative_strengths:
        content += "\n<h3>年収以外の強さ (A-3)</h3>"
        for s in income_eval.alternative_strengths:
            content += f"""
<div class="strength-card">
<strong>{_esc(s.category)}</strong>: {_esc(s.description)}
<div style="color:#888;font-size:0.85em;margin-top:4px;">根拠: {_esc(s.source_text[:100])}</div>
</div>"""

    content += "\n</section>"
    return content


def _build_proper_nouns(proper_nouns):
    """A-4: 固有名詞規制リスト"""
    if not proper_nouns:
        return """<section id="proper-nouns" class="section">
<h2>固有名詞規制 (A-4)</h2>
<p>検出された固有名詞はありません。</p>
</section>"""

    entries_html = ""
    for noun in proper_nouns:
        css_class = "noun-show" if noun.action == "show" else "noun-hide"
        action_label = "✅ 出す" if noun.action == "show" else "🔇 伏せる"
        entries_html += f"""
<div class="noun-entry {css_class}">
<strong>{_esc(noun.name)}</strong> — {action_label}
<div style="font-size:0.85em;color:#666;">理由: {_esc(noun.reason)}</div>"""
        if noun.telop_template:
            entries_html += f'<div style="font-size:0.85em;color:#c62828;">テロップ提案: {_esc(noun.telop_template)}</div>'
        entries_html += "</div>"

    return f"""<section id="proper-nouns" class="section">
<h2>固有名詞規制 (A-4)</h2>
{entries_html}
</section>"""


def _build_direction_timeline(timeline):
    """NEW-1: 演出ディレクション（タイムライン形式）"""
    entries_html = ""
    for entry in timeline.entries:
        type_class = f"type-{entry.direction_type}"
        priority_class = f"priority-{entry.priority}"
        type_label = {"telop": "テロップ", "camera": "画角", "color": "色変え", "composite": "複合"}.get(
            entry.direction_type, entry.direction_type
        )
        entries_html += f"""
<div class="timeline-entry {priority_class}">
<span class="timeline-ts">[{_esc(entry.timestamp)}]</span>
<span class="timeline-type {type_class}">{type_label}</span>
<div class="timeline-instruction">
<div>{_esc(entry.instruction)}</div>
<div style="font-size:0.8em;color:#888;">{_esc(entry.reason)}</div>
</div>
</div>"""

    llm_section = ""
    if timeline.llm_analysis:
        llm_section = f"""
<details>
<summary>LLMによる追加演出提案</summary>
<div style="background:#f8f9fa;padding:16px;border-radius:8px;white-space:pre-wrap;font-size:0.9em;">
{_esc(timeline.llm_analysis)}
</div>
</details>"""

    return f"""<section id="direction-timeline" class="section">
<h2>演出ディレクション (NEW-1)</h2>
{entries_html}
{llm_section}
</section>"""


def _build_target_checklist(target_result):
    """A-5: ターゲット別チェックリスト"""
    balance = target_result.balance

    # バランスメーター
    t1_pct = int(balance.tier1_ratio * 100) if balance.total > 0 else 50
    t2_pct = 100 - t1_pct
    meter = f"""<div class="balance-meter">
<div class="balance-tier1" style="width:{t1_pct}%"></div>
<div class="balance-tier2" style="width:{t2_pct}%"></div>
</div>
<div style="display:flex;justify-content:space-between;font-size:0.8em;color:#666;">
<span>1層 {balance.tier1_count}件</span>
<span>両層 {balance.both_count}件</span>
<span>2層 {balance.tier2_count}件</span>
</div>
<p><strong>バランス:</strong> {_esc(balance.balance_assessment)} — {_esc(balance.recommendation)}</p>"""

    # シーン一覧
    scenes_html = ""
    for scene in target_result.scenes:
        css_class = f"target-{scene.target_tier}"
        scenes_html += f"""
<div class="target-scene {css_class}">
<strong>[{_esc(scene.timestamp)}]</strong> {_esc(scene.tier_label)} — {_esc(scene.emotional_hook)}
<div style="font-size:0.85em;">{_esc(scene.text[:80])}{'...' if len(scene.text) > 80 else ''}</div>
</div>"""

    return f"""<section id="target-checklist" class="section">
<h2>ターゲット別チェックリスト (A-5)</h2>
{meter}
{scenes_html}
</section>"""


def _build_highlights(video_data):
    """ハイライトシーンまとめ"""
    if not video_data.highlights:
        return ""

    rows = ""
    for h in video_data.highlights:
        rows += f"""<tr>
<td>{_esc(h.timestamp)}</td>
<td>{_esc(h.speaker)}</td>
<td>{_esc(h.text[:100])}{'...' if len(h.text) > 100 else ''}</td>
<td>{_esc(h.category)}</td>
</tr>"""

    return f"""<section id="highlights" class="section">
<h2>ハイライトシーン</h2>
<table class="highlight-table">
<tr><th>時間</th><th>話者</th><th>発言</th><th>分類</th></tr>
{rows}
</table>
</section>"""


def _build_transcript(video_data):
    """整形済みトランスクリプト（折り畳み）"""
    if not video_data.full_transcript:
        return ""

    return f"""<details>
<summary>整形済みトランスクリプト（全文）</summary>
<div class="transcript">{_esc(video_data.full_transcript[:50000])}</div>
</details>"""


def _build_footer():
    """フッター"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<footer>
<p>AI開発10 映像品質追求・自動ディレクションシステム | 生成日時: {now}</p>
</footer>"""


def _get_guest_name(video_data):
    """ゲスト名を取得"""
    if video_data.profiles:
        return video_data.profiles[0].name
    # タイトルからゲスト名を抽出
    if video_data.title:
        import re
        match = re.search(r"撮影_(.+?)(?:さん|：|$)", video_data.title)
        if match:
            return match.group(1) + "さん"
    return "不明"


def _esc(text: str) -> str:
    """HTMLエスケープ"""
    if not text:
        return ""
    return html.escape(str(text))


def generate_index_html(pages: list[dict]) -> str:
    """index.htmlを生成する

    pages: [{"filename": "...", "title": "...", "date": "...", "tier": "a/b/c"}]
    """
    from .template import INDEX_CSS

    items_html = ""
    for page in sorted(pages, key=lambda p: p.get("date", ""), reverse=True):
        tier = page.get("tier", "")
        tier_badge = f'<span class="tier tier-{tier}">層{tier}</span>' if tier else ""
        items_html += f"""<div class="item">
<div class="date">{_esc(page.get('date', ''))}</div>
<a href="{_esc(page['filename'])}">{_esc(page.get('title', page['filename']))}</a>
{tier_badge}
</div>\n"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ディレクションレポート</title>
<style>{INDEX_CSS}</style>
</head>
<body>
<h1>ディレクションレポート</h1>
{items_html}
<p class="count">全{len(pages)}件</p>
</body>
</html>"""
