from __future__ import annotations
"""LLMプロンプトテンプレート — サムネ・タイトル・概要欄生成用

全てのプロンプトは以下の構造:
- <knowledge> ブロックにナレッジ注入
- <video_data> ブロックにVideoDataから抽出した情報
- JSON形式で出力を指定（パース可能）
"""

# === サムネイル指示書生成プロンプト ===
THUMBNAIL_DESIGN_PROMPT = """あなたはYouTubeサムネイル設計の専門家です。
以下のナレッジとゲスト情報をもとに、Z型サムネイルの指示書を作成してください。

<knowledge>
## Z理論（サムネイル設計の基本理論）
{z_theory_summary}

## Z理論の詳細・実践ポイント
{z_theory_detailed}

## マーケティング原則
{marketing_principles}
</knowledge>

<video_data>
## 動画情報
- タイトル: {video_title}
- ゲスト名: {guest_name}
- ゲスト属性: 年齢={guest_age}, 職業={guest_occupation}, 年収={guest_income}
- ゲスト分類: {guest_tier}（{tier_label}）
- 年収演出: {income_emphasis}
- 3行要約: {three_line_summary}
- 主要トピック: {main_topics}

## ハイライトシーン（上位5件）
{highlights_text}
</video_data>

【重要な制約】
- ゲストの顔はモザイク処理されます。表情指定は不要です
- ゲストはシルエット配置 + 属性テキスト（年収・職業等）で表現します
- 0.2秒で視線がZ字に流れる設計を意識してください
- ターゲット視聴者が「自分ごと」と感じるフックを最優先にしてください

以下のJSON形式で出力してください:
```json
{{
  "overall_concept": "サムネ全体のコンセプト（1行）",
  "font_suggestion": "推奨フォント・文字サイズの方向性",
  "background_suggestion": "背景の色味・トーンの提案",
  "zones": {{
    "top_left": {{
      "role": "フック（最初に目に入る）",
      "content": "具体的なテキスト・要素",
      "color_suggestion": "色の提案",
      "notes": "配置・サイズの注意点"
    }},
    "top_right": {{
      "role": "人物シルエット＋属性",
      "content": "シルエットの配置と属性テキストの内容",
      "color_suggestion": "色の提案",
      "notes": "モザイク顔シルエットの演出方法"
    }},
    "diagonal": {{
      "role": "コンテンツ要素（斜めに視線誘導）",
      "content": "視線を誘導するコンテンツ要素",
      "color_suggestion": "色の提案",
      "notes": "Z字の流れを作る要素配置"
    }},
    "bottom_right": {{
      "role": "ベネフィット（最後の着地）",
      "content": "視聴者が得られるベネフィット",
      "color_suggestion": "色の提案",
      "notes": "クリック動機となる要素"
    }}
  }}
}}
```"""

# === タイトル考案プロンプト ===
TITLE_GENERATION_PROMPT = """あなたはYouTubeタイトル設計の専門家です。
以下のナレッジと過去のタイトルパターンを参考に、この動画のタイトル案を3〜5個提案してください。

<knowledge>
## マーケティング原則
{marketing_principles}

## Z理論（クリック率向上のポイント）
{z_theory_summary}
</knowledge>

<past_titles>
## 過去のTEKO対談動画タイトル一覧（パターン参照用）
{past_titles_text}
</past_titles>

<video_data>
## 動画情報
- 撮影タイトル: {video_title}
- ゲスト名: {guest_name}
- ゲスト属性: 年齢={guest_age}, 職業={guest_occupation}, 年収={guest_income}
- ゲスト分類: {guest_tier}（{tier_label}）
- 年収演出: {income_emphasis}
- 3行要約: {three_line_summary}
- 主要トピック: {main_topics}
- ゲスト副業・TEKO関連: {side_business}

## ハイライトシーン（パンチライン・実績数字）
{highlights_text}
</video_data>

【タイトル設計の原則】
- YouTube検索とサジェストを意識したキーワード配置
- 30文字前後を目安（長すぎると途切れる）
- ターゲット層が「自分ごと」と感じるフック
- 数字（年収・実績）を含む場合はインパクト重視
- ゲストの顔はモザイクなので名前は出さない（「〇〇万円サラリーマン」等の属性表記）
- 煽りすぎない上品なトーン（リテラシーの高い層がターゲット）

以下のJSON形式で出力してください:
```json
{{
  "candidates": [
    {{
      "title": "タイトル案",
      "target_segment": "このタイトルが刺さるターゲット層",
      "appeal_type": "訴求タイプ（数字系/ストーリー系/問いかけ系/権威系）",
      "rationale": "このタイトルを選んだ理由"
    }}
  ],
  "recommended_index": 0
}}
```"""

# === 概要欄文章生成プロンプト ===
DESCRIPTION_GENERATION_PROMPT = """あなたはYouTube概要欄の文章作成の専門家です。
以下の情報をもとに、そのままYouTubeに貼れる概要欄文章を作成してください。

<knowledge>
## マーケティング原則
{marketing_principles}
</knowledge>

<past_descriptions>
## 過去投稿済み動画の概要欄（トーン・構成の参考）
{past_descriptions_text}
</past_descriptions>

<video_data>
## 動画情報
- タイトル: {video_title}
- ゲスト属性: 年齢={guest_age}, 職業={guest_occupation}, 年収={guest_income}
- 3行要約: {three_line_summary}
- 主要トピック: {main_topics}
- 動画時間: {duration}

## ハイライトシーン（タイムスタンプ付き）
{highlights_with_timestamps}
</video_data>

【概要欄の構成ルール】
1. 冒頭フック: 動画の核心を1-2行で伝える（ゲスト名は出さない、属性で表現）
2. トークサマリー: 主要トピックを箇条書き（3-5項目）
3. タイムスタンプ: 主要シーンの時間リンク
4. CTA（全て含める）:
   - TEKO LP: https://teko-lp.com/
   - LINE公式: [LINEリンク]
   - チャンネル登録促進
   - SNSリンク: Instagram / X（Twitter）/ TikTok
5. ハッシュタグ: 5-8個（検索・関連動画表示用）

【注意】
- ゲストの実名は出さない（モザイク処理のため）
- 上品で知的なトーン（煽りや恐怖訴求は使わない）
- 過去の概要欄のトーン・構成を踏襲すること
- CTAのリンク先URLは仮置き可（後から編集者が差し替え可能な形に）

以下のJSON形式で出力してください:
```json
{{
  "full_text": "そのままコピペして使える概要欄の全文テキスト",
  "sections": {{
    "hook": "冒頭フック部分",
    "summary": "トークサマリー部分",
    "timestamps": "タイムスタンプ部分",
    "cta": "CTA部分",
    "hashtags": "ハッシュタグ部分"
  }}
}}
```"""
