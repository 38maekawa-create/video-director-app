from __future__ import annotations
"""概要欄文章生成モジュール

そのままYouTubeに貼れる概要欄テキストを生成する。
構成: チャンネル登録CTA → ブランド紹介 → ゲスト紹介フック → トークサマリー → LINE CTA
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from ..integrations.ai_dev5_connector import VideoData
from ..analyzer.guest_classifier import ClassificationResult
from ..analyzer.income_evaluator import IncomeEvaluation
from ..knowledge.loader import KnowledgeContext
from ..knowledge.prompts import DESCRIPTION_GENERATION_PROMPT
from ..knowledge.loader import fetch_latest_description_template
from ..analyzer.proper_noun_filter import ProperNounEntry


@dataclass
class VideoDescription:
    """YouTube概要欄テキスト"""
    full_text: str = ""          # そのまま貼れる完成版
    hook: str = ""               # 冒頭フック
    summary: str = ""            # トークサマリー
    timestamps: str = ""         # タイムスタンプ
    cta: str = ""                # CTA
    hashtags: str = ""           # ハッシュタグ
    llm_raw_response: str = ""   # デバッグ・監査用


def generate_description(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
    knowledge_ctx: KnowledgeContext,
    edit_learner=None,
    proper_nouns: list[ProperNounEntry] | None = None,
) -> VideoDescription:
    """YouTube概要欄テキストを生成する（teko_core.llm経由 — MAX定額内）"""

    profile = video_data.profiles[0] if video_data.profiles else None

    # 過去概要欄テキスト（few-shot examples）
    past_descriptions_text = ""
    if knowledge_ctx.past_descriptions:
        for i, desc in enumerate(knowledge_ctx.past_descriptions[:3], 1):
            # 全文をfew-shotに使用（品質のため切り詰めない）
            example_desc = desc
            past_descriptions_text += f"\n--- 過去例{i} ---\n{example_desc}\n"
    else:
        past_descriptions_text = "（過去概要欄データなし — 初回生成のため独自に構成）"

    # タイムスタンプ付きハイライト
    highlights_with_timestamps = "\n".join([
        f"{h.timestamp} - {h.category}: {h.text[:60]}"
        for h in video_data.highlights[:10]
    ]) or "なし"

    # EditLearnerから過去のFB・手修正ルールを取得してプロンプトに注入
    edit_rules_text = ""
    if edit_learner is not None:
        try:
            rules = edit_learner.get_active_rules(asset_type="description")
            if rules:
                edit_rules_text = "\n\n## 過去のフィードバック・手修正から学習した概要欄改善ルール（必ず反映すること）:\n"
                for r in rules[:10]:
                    edit_rules_text += f"- [{r.priority}] {r.rule_text}\n"
                print(f"  📚 EditLearnerルール {len(rules)}件を注入")
        except Exception:
            pass

    # カテゴリ判定（運営者情報テンプレートの分岐に使用）
    guest_category = video_data.category or "unknown"

    # YouTube API から最新テンプレートを取得（フォールバック: ハードコードテンプレート）
    template_text = _build_youtube_template(guest_category)

    prompt = DESCRIPTION_GENERATION_PROMPT.format(
        marketing_principles=knowledge_ctx.marketing_principles,
        past_descriptions_text=past_descriptions_text,
        video_title=video_data.title or "不明",
        guest_age=profile.age if profile else "不明",
        guest_occupation=profile.occupation if profile else "不明",
        guest_income=profile.income if profile else "不明",
        guest_category=guest_category,
        three_line_summary="\n".join(video_data.three_line_summary) if video_data.three_line_summary else "なし",
        main_topics="\n".join(video_data.main_topics) if video_data.main_topics else "なし",
        duration=video_data.duration or "不明",
        highlights_with_timestamps=highlights_with_timestamps,
        youtube_template=template_text,
    )

    # EditLearnerルールをプロンプト末尾に追加
    if edit_rules_text:
        prompt += edit_rules_text

    # 固有名詞規制: 「伏せる」と判定された企業名を使用禁止ワードとして注入
    hidden_nouns = _get_hidden_noun_names(proper_nouns)
    if hidden_nouns:
        forbidden_text = "\n\n## 使用禁止ワード（固有名詞規制 — 概要欄に絶対に含めないこと）:\n"
        for noun_name in hidden_nouns:
            forbidden_text += f"- 「{noun_name}」（伏せ対象の企業名）\n"
        forbidden_text += "※ 上記の企業名・サービス名は概要欄内に一切使用禁止。\n"
        prompt += forbidden_text

    try:
        from teko_core.llm import ask
        raw = ask(prompt, model="opus", max_tokens=3000, timeout=120)
        result = _parse_description_response(raw)
        # full_textが空 or 200文字未満（テンプレ欠落の検知）の場合はフォールバックに回す
        if not result.full_text or len(result.full_text.strip()) < 200:
            print(f"  ⚠️ LLMレスポンスのfull_textが不十分（{len(result.full_text.strip()) if result.full_text else 0}文字） → フォールバック生成に切り替え")
            return _fallback_description(video_data, classification, income_eval)
        # LLM生成結果からも伏せ対象の企業名を除去（セーフティネット）
        if hidden_nouns:
            result = _sanitize_description(result, hidden_nouns)
        return result

    except Exception as e:
        print(f"  ⚠️ 概要欄文章LLM生成失敗: {e}")
        return _fallback_description(video_data, classification, income_eval)


def _get_hidden_noun_names(proper_nouns: list[ProperNounEntry] | None) -> list[str]:
    """「伏せる」と判定された固有名詞の名前リストを返す"""
    if not proper_nouns:
        return []
    return [n.name for n in proper_nouns if n.action == "hide"]


def _sanitize_description(desc: VideoDescription, hidden_nouns: list[str]) -> VideoDescription:
    """概要欄テキストから伏せ対象の企業名を除去する（セーフティネット）"""
    from ..analyzer.proper_noun_filter import INDUSTRY_CATEGORIES

    for noun in hidden_nouns:
        industry_info = INDUSTRY_CATEGORIES.get(noun)
        if industry_info:
            _, company_type = industry_info
            replacement = f"大手{company_type}"
        else:
            replacement = "大手企業"

        if desc.full_text and noun in desc.full_text:
            desc.full_text = desc.full_text.replace(noun, replacement)
        if desc.hook and noun in desc.hook:
            desc.hook = desc.hook.replace(noun, replacement)
        if desc.summary and noun in desc.summary:
            desc.summary = desc.summary.replace(noun, replacement)

    # ハッシュタグは特別処理: 伏せ対象企業名を含むハッシュタグ全体を除去
    if desc.hashtags and hidden_nouns:
        desc.hashtags = _remove_hashtags_with_hidden_nouns(desc.hashtags, hidden_nouns)

    return desc


def _remove_hashtags_with_hidden_nouns(hashtags_text: str, hidden_nouns: list[str]) -> str:
    """伏せ対象企業名を含むハッシュタグを丸ごと除去する"""
    # ハッシュタグを分割（#で始まる各タグを抽出）
    tags = re.findall(r'#\S+', hashtags_text)
    filtered = []
    for tag in tags:
        if any(noun in tag for noun in hidden_nouns):
            continue
        filtered.append(tag)
    # 元の区切り文字（全角スペース or 半角スペース）を維持
    separator = "　" if "　" in hashtags_text else " "
    return separator.join(filtered)


def _parse_description_response(raw: str) -> VideoDescription:
    """LLMレスポンスからVideoDescriptionを構築（full_textのみ取得）

    パース戦略（優先順）:
    1. JSON正規パース（strict=False）
    2. "full_text"キーの値を直接抽出（JSON全体のパースが壊れた場合のフォールバック）
    3. コードブロック内の全テキストをfull_textとして扱う（JSONを返さなかった場合）
    """
    # コードブロック内を優先抽出
    code_match = re.search(r"```json\s*([\s\S]*?)```", raw)
    if code_match:
        json_str = code_match.group(1).strip()
    else:
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            # JSONもコードブロックもない → raw全体にテンプレが含まれてればそれを使う
            if "チャンネル登録はこちらから" in raw and "@TEKO-公式" in raw:
                return VideoDescription(full_text=raw.strip(), llm_raw_response=raw)
            return VideoDescription(llm_raw_response=raw)
        json_str = json_match.group()

    # 戦略1: JSON正規パース
    try:
        data = json.loads(json_str, strict=False)
        full_text = data.get("full_text", "")
        if full_text:
            return VideoDescription(full_text=full_text, llm_raw_response=raw)
    except json.JSONDecodeError:
        pass

    # 戦略2: "full_text"の値を直接抽出（JSONパース失敗時）
    # "full_text": "..." の中身を最後の閉じ"} まで取得
    ft_match = re.search(r'"full_text"\s*:\s*"([\s\S]*)"', json_str)
    if ft_match:
        extracted = ft_match.group(1)
        # エスケープされた改行を実際の改行に変換
        extracted = extracted.replace("\\n", "\n")
        if len(extracted) > 200:
            return VideoDescription(full_text=extracted, llm_raw_response=raw)

    return VideoDescription(llm_raw_response=raw)


def _fallback_description(
    video_data: VideoData,
    classification: ClassificationResult,
    income_eval: IncomeEvaluation,
) -> VideoDescription:
    """フォールバック（テンプレートベース）

    ゲストのcategoryに応じてテンプレートを分岐する。
    - teko_realestate: 不動産事業向けテンプレート（従来版）
    - teko_member / その他: 汎用テンプレート（不動産固有表現を除去）
    """
    profile = video_data.profiles[0] if video_data.profiles else None

    # ゲスト名（「さん」の二重付与を防止）
    raw_name = profile.name if profile and profile.name else "ゲスト"
    guest_name = raw_name.rstrip("さん") + "さん"

    # カテゴリ判定（video_dataから取得）
    guest_category = video_data.category or ""

    # ハッシュタグ生成（動画内容に合わせて）
    hashtag_parts = []
    if profile and profile.occupation:
        # 職業からハッシュタグ候補を生成（長い場合は最初の区切りまで）
        occ = re.split(r'[。（]', profile.occupation)[0][:20]
        hashtag_parts.append(f"#{occ.replace(' ', '')}")
    if profile and profile.income:
        hashtag_parts.append(f"#年収{profile.income}")
    # カテゴリに応じたハッシュタグ（不動産固有タグは不動産カテゴリのみ）
    if guest_category == "teko_realestate":
        hashtag_parts.extend(["#プロパー八重洲", "#年収1000万", "#年収", "#副業", "#不動産投資", "#ハイキャリ", "#TEKO", "#転職"])
    else:
        hashtag_parts.extend(["#プロパー八重洲", "#年収1000万", "#年収", "#副業", "#ハイキャリ", "#TEKO", "#転職"])

    hashtags_text = "　".join(hashtag_parts[:10])

    # タイムスタンプ（ハイライト情報がある場合）
    timestamps_text = ""
    if video_data.highlights:
        for h in video_data.highlights[:8]:
            ts = h.timestamp if h.timestamp else "0:00"
            timestamps_text += f"{ts} {h.text[:40]}\n"

    # 運営者紹介文をカテゴリに応じて分岐
    if guest_category == "teko_realestate":
        # 不動産カテゴリ: 不動産投資に言及した従来版
        owner_bio = """【運営者情報】　プロパー八重洲 / 藤田光貴

1993年、愛媛県生まれ。
TEKO合同会社 代表社員 / Yohack合同会社 代表社員。

小野薬品工業（株） → (株) ストライク → アレクシオンファーマ（同）を経て独立。

アレクシオンファーマ在籍時、30歳時点で年収約1,100万円と500万円相当のRSUを受け取る。

サラリーマン時代に副業・不動産投資を並行して実践し、アレクシオンファーマ（同）在籍時に純資産1億円超えに至る。

Xフォロワー2.2万人。Instagramフォロワー1万人。（2025.9時点）

医師、GAFAM、5大総合商社、外資系戦略コンサルなどハイクラスのビジネスパーソンも数多く在籍する会員制ビジネスパーソン向けプラットフォーム"TEKO"を運営。

2025年9月時点で、300名ほどのビジネスパーソンがTEKOに在籍中。

海外輸出物販事業を運営する法人と不動産賃貸業及びハイキャリア中心にビジネスパーソンのキャリア支援・経済支援を行うTEKO事業を運営する法人の2法人を所有。

海外輸出物販法人の前期決算では年商1.3億円。

2016年 小野薬品工業株式会社  入社
2021年 株式会社ストライク 入社
2022年 アレクシオンファーマ合同会社  入社
2024年 TEKO設立"""
    else:
        # 汎用カテゴリ（teko_member等）: 不動産固有表現を除いた汎用版
        owner_bio = """【運営者情報】　プロパー八重洲 / 藤田光貴

1993年、愛媛県生まれ。
TEKO合同会社 代表社員 / Yohack合同会社 代表社員。

小野薬品工業（株） → (株) ストライク → アレクシオンファーマ（同）を経て独立。

アレクシオンファーマ在籍時、30歳時点で年収約1,100万円と500万円相当のRSUを受け取る。

サラリーマン時代に副業を並行して実践し、アレクシオンファーマ（同）在籍時に純資産1億円超えに至る。

Xフォロワー2.2万人。Instagramフォロワー1万人。（2025.9時点）

医師、GAFAM、5大総合商社、外資系戦略コンサルなどハイクラスのビジネスパーソンも数多く在籍する会員制ビジネスパーソン向けプラットフォーム"TEKO"を運営。

2025年9月時点で、300名ほどのビジネスパーソンがTEKOに在籍中。

ハイキャリア中心にビジネスパーソンのキャリア支援・経済支援を行うTEKO事業を運営。

2016年 小野薬品工業株式会社  入社
2021年 株式会社ストライク 入社
2022年 アレクシオンファーマ合同会社  入社
2024年 TEKO設立"""

    # 概要欄全文（TEKO投稿済みフォーマット準拠、カテゴリに応じた運営者紹介を使用）
    full_text = f"""チャンネル登録はこちらから▼
              @TEKO-公式

【TEKO公式メディア】
ハイキャリアパーソンの裏側とキャリア、資産形成について発信
https://levaraging.daive-teko.com/?openExternalBrowser=1

【運営者：プロパー八重洲公式メールマガジンはこちら】
▼パラレルキャリア戦略やTEKOについてはメルマガから▼
https://leverage.daive-teko.com/p/lp_youtube_tekoofficial?openExternalBrowser=1

【プロパー八重洲公式チャンネルはこちらから】
     @プロパー八重洲キャリア戦略室

ハイキャリアのキャリアの裏側と挑戦に迫ったキャリア密着ドキュメンタリー番組・"ハイキャリアの裏側"はこちら▼
   @ハイキャリアの裏側-TEKO

▼タイムスタンプ▼
{timestamps_text}

━━━━━━━━━━━
{hashtags_text}
━━━━━━━━━━━


{owner_bio}


▪️他SNSでもキャリアや資産形成に関する戦略・戦術を発信中
X（旧Twitter）
https://x.com/yaesu_pro

Instagram
https://www.instagram.com/yaesu.pro/"""

    return VideoDescription(
        full_text=full_text,
        hook=f"{guest_name}のキャリアと資産形成のリアルに迫る",
        summary="",
        timestamps=timestamps_text,
        cta="",
        hashtags=hashtags_text,
        llm_raw_response=f"[フォールバック: TEKO実投稿済みテンプレート準拠 (category={guest_category or 'unknown'})]",
    )


# ---------------------------------------------------------------------------
# YouTube APIテンプレート取得・抽出ロジック
# ---------------------------------------------------------------------------

# フォールバック用ハードコードテンプレート（API障害時のセーフティネット）
_FALLBACK_TEMPLATE = """```
{{ゲスト紹介フック}}
← ここにゲストの魅力・動画の核心を伝える導入文を3〜5行で書く。最後に「」で囲んだパンチライン引用を入れると効果的

チャンネル登録はこちらから▼
              @TEKO-公式

【TEKO公式メディア】
ハイキャリアパーソンの裏側とキャリア、資産形成について発信
https://levaraging.daive-teko.com/?openExternalBrowser=1

【運営者：プロパー八重洲公式メールマガジンはこちら】
▼パラレルキャリア戦略やTEKOについてはメルマガから▼
https://leverage.daive-teko.com/p/lp_youtube_tekoofficial?openExternalBrowser=1

【プロパー八重洲公式チャンネルはこちらから】
               @プロパー八重洲キャリア戦略室

ハイキャリアのキャリアの裏側と挑戦に迫ったキャリア密着ドキュメンタリー番組・"ハイキャリアの裏側"はこちら▼
             @ハイキャリアの裏側-TEKO


▼タイムスタンプ▼
{{タイムスタンプ}}
← ハイライト情報から「01:44 お金持ちへの原体験——大学の友人の親から学んだこと」のような形式で生成する。情報がなければ空欄でOK



━━━━━━━━━━━
{{ハッシュタグ}}
← 動画内容に合った5-10個のハッシュタグ（例: #薬剤師　#プロパー八重洲　#不動産投資　#副業　#ハイキャリ　#TEKO　#資産形成　#物販　#信用組合　#年収700万）
━━━━━━━━━━━


{{運営者情報}}

▪️他SNSでもキャリアや資産形成に関する戦略・戦術を発信中
X（旧Twitter）
https://x.com/yaesu_pro

Instagram
https://www.instagram.com/yaesu.pro/
```

【運営者情報の選択ルール】
ゲストカテゴリに応じて、以下の2パターンから適切な運営者情報を選んでそのまま使うこと。

■ パターンA: 不動産カテゴリ（ゲストカテゴリが teko_realestate の場合）
```
【運営者情報】　プロパー八重洲 / 藤田光貴

1993年、愛媛県生まれ。
TEKO合同会社 代表社員 / Yohack合同会社 代表社員。

小野薬品工業（株） → (株) ストライク → アレクシオンファーマ（同）を経て独立。

アレクシオンファーマ在籍時、30歳時点で年収約1,100万円と500万円相当のRSUを受け取る。

サラリーマン時代に副業・不動産投資を並行して実践し、アレクシオンファーマ（同）在籍時に純資産1億円超えに至る。

Xフォロワー2.2万人。Instagramフォロワー1万人。（2025.9時点）

医師、GAFAM、5大総合商社、外資系戦略コンサルなどハイクラスのビジネスパーソンも数多く在籍する会員制ビジネスパーソン向けプラットフォーム"TEKO"を運営。

2025年9月時点で、300名ほどのビジネスパーソンがTEKOに在籍中。

海外輸出物販事業を運営する法人と不動産賃貸業及びハイキャリア中心にビジネスパーソンのキャリア支援・経済支援を行うTEKO事業を運営する法人の2法人を所有。

海外輸出物販法人の前期決算では年商1.3億円。

2016年 小野薬品工業株式会社  入社
2021年 株式会社ストライク 入社
2022年 アレクシオンファーマ合同会社  入社
2024年 TEKO設立
```

■ パターンB: 汎用カテゴリ（ゲストカテゴリが teko_realestate 以外の場合）
```
【運営者情報】　プロパー八重洲 / 藤田光貴

1993年、愛媛県生まれ。
TEKO合同会社 代表社員 / Yohack合同会社 代表社員。

小野薬品工業（株） → (株) ストライク → アレクシオンファーマ（同）を経て独立。

アレクシオンファーマ在籍時、30歳時点で年収約1,100万円と500万円相当のRSUを受け取る。

サラリーマン時代に副業を並行して実践し、アレクシオンファーマ（同）在籍時に純資産1億円超えに至る。

Xフォロワー2.2万人。Instagramフォロワー1万人。（2025.9時点）

医師、GAFAM、5大総合商社、外資系戦略コンサルなどハイクラスのビジネスパーソンも数多く在籍する会員制ビジネスパーソン向けプラットフォーム"TEKO"を運営。

2025年9月時点で、300名ほどのビジネスパーソンがTEKOに在籍中。

ハイキャリア中心にビジネスパーソンのキャリア支援・経済支援を行うTEKO事業を運営。

2016年 小野薬品工業株式会社  入社
2021年 株式会社ストライク 入社
2022年 アレクシオンファーマ合同会社  入社
2024年 TEKO設立
```"""


def _extract_template_from_description(raw_description: str) -> str:
    """YouTube投稿済み概要欄から動的部分をプレースホルダーに置換したテンプレートを構築する。

    認識する構造:
    - ゲスト紹介フック: 先頭〜「チャンネル登録はこちらから」の前
    - タイムスタンプ: 「▼タイムスタンプ▼」の後〜「━━━」の前
    - ハッシュタグ: 「━━━」で囲まれた部分
    - 運営者情報: 「【運営者情報】」〜「TEKO設立」の行まで
    """
    lines = raw_description.split("\n")
    result_lines = []
    i = 0

    # --- ゲスト紹介フック: 先頭 〜 「チャンネル登録はこちらから」の前 ---
    hook_end = None
    for idx, line in enumerate(lines):
        if "チャンネル登録はこちらから" in line:
            hook_end = idx
            break

    if hook_end is not None and hook_end > 0:
        result_lines.append("{{ゲスト紹介フック}}")
        result_lines.append("← ここにゲストの魅力・動画の核心を伝える導入文を3〜5行で書く。最後に「」で囲んだパンチライン引用を入れると効果的")
        result_lines.append("")
        i = hook_end
    # hook_endが0またはNoneの場合はそのまま先頭から

    # --- 中間部分: タイムスタンプとハッシュタグを置換しつつコピー ---
    in_timestamps = False
    in_hashtags = False
    separator_count = 0

    while i < len(lines):
        line = lines[i]

        # タイムスタンプセクション検出
        if "▼タイムスタンプ▼" in line:
            result_lines.append(line)
            result_lines.append("{{タイムスタンプ}}")
            result_lines.append("← ハイライト情報から「01:44 お金持ちへの原体験——大学の友人の親から学んだこと」のような形式で生成する。情報がなければ空欄でOK")
            in_timestamps = True
            i += 1
            continue

        if in_timestamps:
            # タイムスタンプ部分をスキップ（━━━ or 空行連続で終了）
            if "━━━" in line:
                in_timestamps = False
                # ハッシュタグセクション開始
                result_lines.append("")
                result_lines.append("")
                result_lines.append(line)
                separator_count = 1
                in_hashtags = True
                i += 1
                continue
            # タイムスタンプ行をスキップ（数字:数字で始まる行 or 空行）
            if re.match(r'^\d', line) or line.strip() == "":
                i += 1
                continue
            # タイムスタンプっぽくない行が来たら終了
            in_timestamps = False

        # ハッシュタグセクション（━━━で囲まれた部分）
        if in_hashtags:
            if "━━━" in line:
                separator_count += 1
                if separator_count >= 2:
                    # ハッシュタグセクション終了
                    result_lines.append("{{ハッシュタグ}}")
                    result_lines.append("← 動画内容に合った5-10個のハッシュタグ（例: #薬剤師　#プロパー八重洲　#不動産投資　#副業　#ハイキャリ　#TEKO　#資産形成　#物販　#信用組合　#年収700万）")
                    result_lines.append(line)
                    in_hashtags = False
                    i += 1
                    continue
            else:
                # ハッシュタグ行をスキップ
                i += 1
                continue

        # 最初の━━━（タイムスタンプセクション外）
        if not in_hashtags and "━━━" in line and separator_count == 0:
            result_lines.append(line)
            separator_count = 1
            in_hashtags = True
            i += 1
            continue

        # 運営者情報セクション
        if "【運営者情報】" in line:
            result_lines.append("{{運営者情報}}")
            # TEKO設立の行までスキップ
            i += 1
            while i < len(lines):
                if "TEKO設立" in lines[i]:
                    i += 1
                    break
                i += 1
            continue

        result_lines.append(line)
        i += 1

    template = "\n".join(result_lines)

    # テンプレートとして最低限の構造を持っているか検証
    if "チャンネル登録はこちらから" not in template:
        return ""

    return template


def _build_youtube_template(guest_category: str) -> str:
    """YouTube APIテンプレートを構築する。API取得失敗時はフォールバックを使用。"""
    raw = fetch_latest_description_template()
    if raw:
        extracted = _extract_template_from_description(raw)
        if extracted:
            # 抽出成功 → テンプレートとしてフォーマット
            template = f"""```
{extracted}
```

【運営者情報の選択ルール】
ゲストカテゴリに応じて、以下の2パターンから適切な運営者情報を選んでそのまま使うこと。
ゲストカテゴリが teko_realestate の場合 → 不動産投資に言及したパターンA
それ以外 → 汎用パターンB
（具体的な運営者情報テキストは過去概要欄の例を参照すること）"""
            print(f"  🌐 YouTube APIから最新テンプレート取得成功（{len(raw)}文字）")
            return template

    # フォールバック: ハードコードテンプレート
    print("  📋 フォールバック: ハードコードテンプレートを使用")
    return _FALLBACK_TEMPLATE
