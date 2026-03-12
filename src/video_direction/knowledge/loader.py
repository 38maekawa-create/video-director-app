from __future__ import annotations
"""ナレッジローダー — サムネ・タイトル・概要欄生成に必要なナレッジを読み込む

Z理論、マーケティング原則、過去タイトルパターン、過去概要欄テキストを
KnowledgeContext にまとめて各analyzer に提供する。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KnowledgeContext:
    """ナレッジコンテキスト（各analyzerへの入力）"""
    z_theory_summary: str = ""          # Z理論要約（thumbnail-z-theory-director-education.md）
    z_theory_detailed: str = ""         # Z理論詳細（対談セッション書き起こし要点）
    marketing_principles: str = ""      # 事業横断マーケティング原則
    past_title_patterns: list[str] = field(default_factory=list)   # 過去タイトル一覧（H1行抽出）
    past_descriptions: list[str] = field(default_factory=list)     # 過去投稿済み動画の概要欄テキスト


class KnowledgeLoader:
    """ナレッジファイルを読み込んでKnowledgeContextを構築する

    - プロセス内キャッシュ（一度読んだら再読み込みしない）
    - ファイル不在時は空文字返却（安全な失敗）
    """

    # ナレッジファイルのパス定義
    KNOWLEDGE_FILES = {
        "z_theory_summary": Path.home() / "TEKO" / "knowledge" / "_refinery" / "output" / "teko" / "thumbnail-z-theory-director-education.md",
        "z_theory_detailed": Path.home() / "TEKO" / "knowledge" / "external-knowledge" / "2026.02.15_YouTube動画制作におけるサムネイル設計とクリエイティブディレクションの実践知.md",
        "marketing_principles": Path.home() / "TEKO" / "knowledge" / "philosophy" / "core" / "cross-project-marketing-principles.md",
    }

    # 過去タイトル抽出元ディレクトリ
    VIDEO_TRANSCRIPTS_DIR = Path.home() / "TEKO" / "knowledge" / "raw-data" / "video_transcripts"

    def __init__(self):
        self._cache: KnowledgeContext | None = None

    def load(self) -> KnowledgeContext:
        """ナレッジコンテキストを読み込む（キャッシュあり）"""
        if self._cache is not None:
            return self._cache

        ctx = KnowledgeContext()

        # Z理論要約（全文注入）
        ctx.z_theory_summary = self._read_file(self.KNOWLEDGE_FILES["z_theory_summary"])

        # Z理論詳細（要点抽出 — 長いので先頭部分+重要セクション）
        ctx.z_theory_detailed = self._extract_z_theory_key_points(
            self._read_file(self.KNOWLEDGE_FILES["z_theory_detailed"])
        )

        # マーケティング原則（全文注入）
        ctx.marketing_principles = self._read_file(self.KNOWLEDGE_FILES["marketing_principles"])

        # 過去タイトルパターン（video_transcriptsのH1行抽出）
        ctx.past_title_patterns = self._extract_past_titles()

        # 過去概要欄テキスト（YouTube Data API経由 — チャンネルID未設定時は空）
        ctx.past_descriptions = self._fetch_past_descriptions()

        self._cache = ctx
        return ctx

    def _read_file(self, path: Path) -> str:
        """ファイルを安全に読み込む（不在時は空文字）"""
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception:
            pass
        return ""

    def _extract_z_theory_key_points(self, full_text: str) -> str:
        """Z理論詳細テキストから要点を抽出する

        639行全文を注入するとトークンが膨大になるため、
        重要なセクション（Z理論の定義・4ゾーン・実践ポイント）を抽出する。
        """
        if not full_text:
            return ""

        # セクションヘッダーベースで重要部分を抽出
        key_sections = []
        lines = full_text.split("\n")
        in_key_section = False
        current_section = []

        # 重要キーワード（これらを含むセクションを抽出）
        key_patterns = [
            r"[Zz]理論", r"サムネ", r"ゾーン", r"レイアウト",
            r"フック", r"ベネフィット", r"モザイク", r"シルエット",
            r"クリック率", r"視線誘導", r"0\.2秒",
        ]

        for line in lines:
            # セクションヘッダー検出
            if line.startswith("##"):
                # 前のセクションを保存
                if in_key_section and current_section:
                    key_sections.append("\n".join(current_section))
                    current_section = []

                # このセクションが重要かチェック
                in_key_section = any(
                    re.search(pat, line) for pat in key_patterns
                )
                if in_key_section:
                    current_section.append(line)
            elif in_key_section:
                current_section.append(line)

        # 最後のセクション
        if in_key_section and current_section:
            key_sections.append("\n".join(current_section))

        result = "\n\n".join(key_sections)

        # 抽出結果が少なすぎる場合は先頭200行を使用
        if len(result) < 200:
            return "\n".join(lines[:200])

        return result

    def _extract_past_titles(self) -> list[str]:
        """video_transcriptsディレクトリから過去タイトルを抽出する

        TEKO対談動画（撮影_を含むファイル）のみを対象に、
        JSONファイルからtitleフィールドまたはファイル名からタイトルを抽出する。
        """
        titles = []
        transcripts_dir = self.VIDEO_TRANSCRIPTS_DIR

        if not transcripts_dir.exists():
            return titles

        try:
            import json
            for json_file in sorted(transcripts_dir.glob("*.json")):
                # TEKO対談動画のみ（撮影を含むファイル名）
                if "撮影" not in json_file.name:
                    continue

                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))

                    # _metadata.source_type でフィルタ（interviewのみ）
                    metadata = data.get("_metadata", {})
                    source_type = metadata.get("source_type", "")
                    if source_type and source_type != "interview":
                        continue

                    # タイトル取得（ナレッジファイル内のタイトルフィールド）
                    title = data.get("title", "")
                    if not title:
                        # H1行からの抽出を試行
                        content = data.get("content", "")
                        h1_match = re.search(r"^# (.+)$", content, re.MULTILINE)
                        if h1_match:
                            title = h1_match.group(1).strip()

                    if not title:
                        # ファイル名からの抽出にフォールバック
                        title = json_file.stem
                        # 日付プレフィックスを除去
                        title = re.sub(r"^\d{4}\.\d{2}\.\d{2}_", "", title)

                    if title and title not in titles:
                        titles.append(title)

                except (json.JSONDecodeError, KeyError):
                    continue

        except Exception:
            pass

        return titles

    def _fetch_past_descriptions(self) -> list[str]:
        """過去投稿済み動画の概要欄テキストを取得する

        AI開発5のyoutube_monitor.pyのYouTube Data API連携を利用。
        チャンネルIDが未設定の場合は空リストを返す（安全な失敗）。

        TODO: チャンネルID設定後にYouTube Data APIから取得する実装を追加
        """
        descriptions = []

        try:
            # AI開発5のYouTube監視データから概要欄を取得
            youtube_data_dir = Path.home() / "AI開発5" / "data" / "youtube_monitor"
            if not youtube_data_dir.exists():
                # 代替パス
                youtube_data_dir = Path.home() / "AI開発5" / "output" / "youtube"

            if not youtube_data_dir.exists():
                return descriptions

            import json
            for json_file in sorted(youtube_data_dir.glob("*.json"), reverse=True):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))

                    # snippet.descriptionを取得
                    if isinstance(data, dict):
                        desc = data.get("snippet", {}).get("description", "")
                        if not desc:
                            desc = data.get("description", "")
                        if desc and len(desc) > 50:  # 短すぎるものは除外
                            descriptions.append(desc)
                    elif isinstance(data, list):
                        for item in data:
                            desc = item.get("snippet", {}).get("description", "")
                            if not desc:
                                desc = item.get("description", "")
                            if desc and len(desc) > 50:
                                descriptions.append(desc)

                except (json.JSONDecodeError, KeyError):
                    continue

            # 最新10件に制限（プロンプトサイズ管理）
            descriptions = descriptions[:10]

        except Exception:
            pass

        return descriptions
