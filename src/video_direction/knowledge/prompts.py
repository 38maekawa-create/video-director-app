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

【視認時間0.2秒制約】
- サムネの視認時間は0.5秒から0.2秒に短縮された。Z構造で左上が勝負を決める
- 文字は最小限。映像・ロゴ・アイコンで情報を伝える
- 文字詰め込みではなく、インスタのロゴ1枚で「インスタで稼ぐ」を瞬時に伝えるような非言語戦略を優先
- 非言語要素（企業ロゴ、業界アイコン、映像カット）の活用を積極的に提案すること

【層別フック戦略】
- tier a（年収2000万〜）: 数字+権威性（企業ブランド、役職）でフック
- tier b（年収1000-2000万）: ストーリー+共感（転職ストーリー、人生の転機）でフック
- tier c（年収〜1000万）: 行動のきっかけ+等身大感（「自分でもできそう」感）でフック
- ゲスト分類（{guest_tier}）に応じて最適なフック戦略を選択すること

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

【タイトル設計の原則 — TEKOチャンネル統一フォーマット】
1. 構造テンプレート: 年収[金額][年代][職業]「[パンチライン]」[名前]さんが語る[テーマ]とは？【TEKO独占インタビュー】
2. 年収フック: 必ずタイトル最先端に配置（金額判明時は必須）
3. 属性詳細化: 「20代後半」「30代中盤」など年代区分を詳細化。職業も具体的に（「営業職」「MR」「薬剤師」等）
4. 名前表記: 実名 + 「さん」で記載（モザイク動画でもYouTubeタイトルでは実名掲載がTEKO運用方針）
5. 引用フレーズ: 「」内に本人の肉声・思考・価値観を1フレーズ抽出（感情訴求・パンチライン化）。ハイライトの中から最もインパクトのあるフレーズを選ぶ
6. テーマバリエーション: キャリアプラン / 人生総取り戦略 / 将来設計 / キャリアパス / 収入戦略 等（毎回違うテーマを設定）
7. クロージング: 【TEKO独占インタビュー】固定
8. 長さ: 60〜80文字OK（TEKOの実例に基づく。短くまとめる必要はない）
9. トーン: 上品で知的。煽りすぎない。リテラシーの高い層がターゲット
10. 複数案: メイン案1本 + バリエーション2本の計3案を生成

【実例】
- 年収3000万30代元アクセンチュア マネージャー職「労働集約的じゃないキャッシュフローの構築を」Izuさんが語るキャリア戦略とは【TEKO独占インタビュー】
- 年収1400万20代半導体メーカー営業職「妻も私も欲深いので」てぃーひろさんが語る人生総取り戦略とは【TEKO独占インタビュー】
- 年収600万20代内資IT営業職「稼ぐために本業で役職を上げるのは最短ルートではない」りょうすけさんが語る収入を上げるための最適解とは？

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

【概要欄の構成ルール — TEKOチャンネル統一フォーマット】
1. CTA冒頭配置（絶対位置）: 「チャンネル登録はこちらから▼」+ チャンネルURL
2. ブランド紹介: 「【TEKO公式メディア】」+ 「ハイキャリアパーソンの裏側と本音に迫る対談メディア」
3. ゲスト紹介フック: 1-2行で動画の核心（ゲスト実名 + さん表記でOK）
4. トークサマリー: 主要トピック箇条書き（3-5項目）
5. LINE公式CTA: 「【運営者：プロパー八重洲とLINEで繋がりませんか？】」+ 「▼パラレルキャリア相談はこちら」+ LINE URL
6. トーン: 上品・知的

【禁止事項】
- タイムスタンプは記載しない（TEKOは掲載なし）
- ハッシュタグは記載しない（TEKOは掲載なし）
- Instagram / X / TikTok リンクは記載しない（LINE専構成）
- SNSリンクは記載しない

以下のJSON形式で出力してください:
```json
{{
  "full_text": "そのままコピペして使える概要欄の全文テキスト",
  "sections": {{
    "channel_cta": "チャンネル登録CTA部分",
    "brand_intro": "ブランド紹介部分",
    "hook": "ゲスト紹介フック部分",
    "summary": "トークサマリー部分",
    "line_cta": "LINE公式CTA部分"
  }}
}}
```"""
