from __future__ import annotations
"""J-1: AI開発5連携 — Markdownナレッジファイルのパーサー"""

import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class HighlightScene:
    """ハイライトシーン"""
    timestamp: str  # "MM:SS" 形式
    speaker: str
    text: str
    category: str  # 属性紹介, 実績数字, パンチライン, TEKO価値, メッセージ


@dataclass
class PersonProfile:
    """人物プロファイル"""
    name: str
    age: str = ""
    occupation: str = ""
    income: str = ""
    side_business: str = ""
    teko_info: str = ""
    thinking_traits: list = field(default_factory=list)
    key_quotes: list = field(default_factory=list)


@dataclass
class VideoData:
    """パース結果の構造化データ"""
    # メタ情報
    title: str = ""
    date: str = ""
    video_type: str = ""
    source: str = ""
    duration: str = ""
    speakers: str = ""
    category: str = ""
    tags: list = field(default_factory=list)
    transcript_method: str = ""
    guest_summary: str = ""  # メタ情報内のゲスト1行要約

    # コンテンツ
    three_line_summary: list = field(default_factory=list)
    main_topics: list = field(default_factory=list)
    detailed_summary: str = ""
    highlights: list = field(default_factory=list)  # List[HighlightScene]
    profiles: list = field(default_factory=list)  # List[PersonProfile]
    full_transcript: str = ""

    # ファイルパス
    source_path: str = ""


def parse_markdown_file(filepath: str | Path) -> VideoData:
    """Markdownナレッジファイルをパースして構造化データに変換する"""
    filepath = Path(filepath)
    content = filepath.read_text(encoding="utf-8")
    data = VideoData(source_path=str(filepath))

    # タイトル（H1）
    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
    if title_match:
        data.title = title_match.group(1).strip()

    # メタ情報セクション
    _parse_meta(content, data)

    # 3行要約
    data.three_line_summary = _parse_numbered_list(content, "3行要約")

    # 主要トピック
    data.main_topics = _parse_numbered_list(content, "主要トピック")

    # 詳細要約
    data.detailed_summary = _parse_section_content(content, "詳細要約")

    # ハイライトシーン
    data.highlights = _parse_highlights(content)

    # 人物プロファイル
    data.profiles = _parse_profiles(content)

    # 整形済みトランスクリプト（全文）
    data.full_transcript = _parse_transcript(content)

    return data


def _parse_meta(content: str, data: VideoData):
    """メタ情報セクションをパース"""
    meta_section = _extract_section(content, "メタ情報")
    if not meta_section:
        return

    field_map = {
        "日付": "date",
        "動画種別": "video_type",
        "ソース": "source",
        "動画時間": "duration",
        "話者": "speakers",
        "カテゴリ": "category",
        "文字起こし方式": "transcript_method",
    }

    for line in meta_section.split("\n"):
        line = line.strip()
        if not line.startswith("- **"):
            # ゲスト情報行（"- **名前**: ..."のパターンだがfield_mapに含まれないもの）
            # メタ情報の最後にゲスト1行要約がある
            continue
        match = re.match(r"- \*\*(.+?)\*\*:\s*(.+)", line)
        if not match:
            continue
        key, value = match.group(1).strip(), match.group(2).strip()

        if key == "タグ":
            data.tags = [t.strip().lstrip("#") for t in value.split(",")]
        elif key in field_map:
            setattr(data, field_map[key], value)
        else:
            # ゲスト名とその情報（例: "Izu": "年齢: 30代中盤 / ..."）
            data.guest_summary = f"{key}: {value}"


def _parse_numbered_list(content: str, section_name: str) -> list:
    """番号付きリストをパース"""
    section = _extract_section(content, section_name)
    if not section:
        return []
    items = []
    for line in section.split("\n"):
        match = re.match(r"\d+\.\s+(.+)", line.strip())
        if match:
            items.append(match.group(1))
    return items


def _parse_highlights(content: str) -> list:
    """ハイライトシーンのテーブルをパース"""
    section = _extract_section(content, "ハイライトシーン")
    if not section:
        return []
    highlights = []
    for line in section.split("\n"):
        # テーブル行: | 02:30 | Izu | 「...」 | 属性紹介 |
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 4:
            continue
        # ヘッダー行・セパレータ行をスキップ
        if cells[0] in ("時間", "---", "------") or "---" in cells[0]:
            continue
        timestamp = cells[0].strip()
        if not re.match(r"\d{1,3}:\d{2}", timestamp):
            continue
        highlights.append(HighlightScene(
            timestamp=timestamp,
            speaker=cells[1].strip(),
            text=cells[2].strip().strip("「」"),
            category=cells[3].strip(),
        ))
    return highlights


def _parse_profiles(content: str) -> list:
    """人物プロファイル情報をパース"""
    section = _extract_section(content, "人物プロファイル情報")
    if not section:
        return []

    profiles = []
    current_profile = None

    for line in section.split("\n"):
        line = line.strip()
        # H3: ### 名前
        if line.startswith("### "):
            if current_profile:
                profiles.append(current_profile)
            name = line[4:].strip()
            current_profile = PersonProfile(name=name)
        elif current_profile and line.startswith("- **"):
            match = re.match(r"- \*\*(.+?)\*\*:\s*(.+)", line)
            if match:
                key, value = match.group(1), match.group(2)
                if "年齢" in key:
                    current_profile.age = value
                elif "本業" in key:
                    current_profile.occupation = value
                elif "年収" in key:
                    current_profile.income = value
                elif "副業" in key or "複業" in key:
                    current_profile.side_business = value
                elif "TEKO" in key:
                    current_profile.teko_info = value
        elif current_profile and line.startswith("- ") and not line.startswith("- **"):
            # 思考特徴のリスト項目
            current_profile.thinking_traits.append(line[2:].strip())

    if current_profile:
        profiles.append(current_profile)

    return profiles


def _parse_transcript(content: str) -> str:
    """整形済みトランスクリプト全文を取得"""
    # "## 整形済みトランスクリプト" or "## トランスクリプト" を探す
    patterns = [
        r"## 整形済みトランスクリプト(?:（全文）)?.*?\n([\s\S]+?)(?=\n## |\Z)",
        r"## トランスクリプト.*?\n([\s\S]+?)(?=\n## |\Z)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()
    return ""


def _extract_section(content: str, section_name: str) -> str:
    """指定セクション名のH2セクション内容を抽出"""
    pattern = rf"## {re.escape(section_name)}.*?\n([\s\S]+?)(?=\n## |\Z)"
    match = re.search(pattern, content)
    if match:
        return match.group(1).strip()
    return ""


# エイリアス
_parse_section_content = _extract_section


def list_video_markdown_files(
    knowledge_dir: str | Path = None,
) -> list[Path]:
    """AI開発5の出力Markdownファイル一覧を取得（_archive等を除外）"""
    if knowledge_dir is None:
        knowledge_dir = Path.home() / "TEKO" / "knowledge" / "01_teko" / "sources" / "video"
    else:
        knowledge_dir = Path(knowledge_dir)

    files = []
    for f in sorted(knowledge_dir.glob("*.md")):
        # _archive, _backup, DUPLICATE_ANALYSIS等を除外
        if f.name.startswith("_") or f.name.startswith("DUPLICATE"):
            continue
        # _archive_duplicates等のサブディレクトリ配下は除外（glob("*.md")はトップレベルのみ）
        files.append(f)
    return files
