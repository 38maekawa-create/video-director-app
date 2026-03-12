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

    # TEKOチャンネルID（YouTube Data API用）
    YOUTUBE_CHANNEL_ID = "UCNEsgjVHvL4y0suJGwu8ZPg"

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
        """過去投稿済み動画の概要欄テキストをYouTube Data APIから取得する

        TEKOチャンネル（UCNEsgjVHvL4y0suJGwu8ZPg）の公開済み動画から
        snippet.descriptionを取得し、概要欄生成のfew-shot examplesとして使う。
        APIキーなし・ネットワークエラー時は空リスト（安全な失敗）。
        取得結果はローカルにキャッシュして次回以降はAPI不要にする。
        """
        # まずローカルキャッシュを確認
        cache_file = Path.home() / "AI開発10" / ".cache" / "youtube_descriptions.json"
        descriptions = self._load_cached_descriptions(cache_file)
        if descriptions:
            return descriptions

        # YouTube Data APIから取得
        descriptions = self._fetch_from_youtube_api()

        # 取得成功したらキャッシュ保存
        if descriptions:
            self._save_cached_descriptions(cache_file, descriptions)

        return descriptions

    def _load_cached_descriptions(self, cache_file: Path) -> list[str]:
        """ローカルキャッシュから概要欄を読み込む（24時間有効）"""
        try:
            if not cache_file.exists():
                return []

            import json
            import time
            data = json.loads(cache_file.read_text(encoding="utf-8"))

            # 24時間以内のキャッシュのみ有効
            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at > 86400:  # 24時間
                return []

            return data.get("descriptions", [])
        except Exception:
            return []

    def _save_cached_descriptions(self, cache_file: Path, descriptions: list[str]):
        """概要欄をローカルキャッシュに保存"""
        try:
            import json
            import time
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "cached_at": time.time(),
                "channel_id": self.YOUTUBE_CHANNEL_ID,
                "count": len(descriptions),
                "descriptions": descriptions,
            }
            cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _fetch_from_youtube_api(self) -> list[str]:
        """YouTube Data APIからチャンネルの動画概要欄を取得"""
        import os

        api_key = os.environ.get("YOUTUBE_API_KEY", "")
        if not api_key:
            # 複数の.envファイルを検索（AI開発5の.envも含む）
            env_candidates = [
                Path.home() / ".config" / "maekawa" / "api-keys.env",
                Path.home() / "AI開発5" / ".env",
            ]
            for env_file in env_candidates:
                if not env_file.exists():
                    continue
                for line in env_file.read_text().split("\n"):
                    line = line.strip()
                    if line.startswith("YOUTUBE_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
                    if not api_key and line.startswith("GOOGLE_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                if api_key:
                    break

        if not api_key:
            return []

        try:
            import urllib.request
            import json

            # Step 1: チャンネルのアップロードプレイリストIDを取得
            channel_url = (
                f"https://www.googleapis.com/youtube/v3/channels"
                f"?part=contentDetails&id={self.YOUTUBE_CHANNEL_ID}&key={api_key}"
            )
            req = urllib.request.Request(channel_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                channel_data = json.loads(resp.read().decode("utf-8"))

            items = channel_data.get("items", [])
            if not items:
                return []

            uploads_playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

            # Step 2: アップロードプレイリストから動画IDを取得（最新20件）
            playlist_url = (
                f"https://www.googleapis.com/youtube/v3/playlistItems"
                f"?part=contentDetails&playlistId={uploads_playlist_id}"
                f"&maxResults=20&key={api_key}"
            )
            req = urllib.request.Request(playlist_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                playlist_data = json.loads(resp.read().decode("utf-8"))

            video_ids = [
                item["contentDetails"]["videoId"]
                for item in playlist_data.get("items", [])
            ]

            if not video_ids:
                return []

            # Step 3: 動画の概要欄を取得
            ids_str = ",".join(video_ids)
            videos_url = (
                f"https://www.googleapis.com/youtube/v3/videos"
                f"?part=snippet&id={ids_str}&key={api_key}"
            )
            req = urllib.request.Request(videos_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                videos_data = json.loads(resp.read().decode("utf-8"))

            descriptions = []
            for item in videos_data.get("items", []):
                desc = item.get("snippet", {}).get("description", "")
                if desc and len(desc) > 50:  # 短すぎるものは除外
                    descriptions.append(desc)

            # 最新10件に制限（プロンプトサイズ管理）
            return descriptions[:10]

        except Exception:
            return []
