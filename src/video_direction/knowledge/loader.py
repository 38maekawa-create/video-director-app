from __future__ import annotations
"""ナレッジローダー — サムネ・タイトル・概要欄生成に必要なナレッジを読み込む

Z理論、マーケティング原則、過去タイトルパターン、過去概要欄テキストを
KnowledgeContext にまとめて各analyzer に提供する。
"""

import json as _json
import re
import time as _time
import urllib.parse
import urllib.request
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
        """チャンネルの動画概要欄をyt-dlpで取得する

        YouTube Data API v3のAPIキーが不要。
        yt-dlpが未インストールの場合は空リスト（安全な失敗）。
        """
        try:
            import subprocess
            import json

            # Step 1: チャンネルから最新20件の動画IDを取得
            channel_url = f"https://www.youtube.com/channel/{self.YOUTUBE_CHANNEL_ID}/videos"
            result = subprocess.run(
                [
                    "yt-dlp", "--flat-playlist", "--print", "%(id)s",
                    channel_url,
                ],
                capture_output=True, text=True, timeout=30,
            )

            if result.returncode != 0:
                # PATHにない場合のフォールバック
                yt_dlp_path = Path.home() / "Library" / "Python" / "3.9" / "bin" / "yt-dlp"
                if yt_dlp_path.exists():
                    result = subprocess.run(
                        [
                            str(yt_dlp_path), "--flat-playlist", "--print", "%(id)s",
                            channel_url,
                        ],
                        capture_output=True, text=True, timeout=30,
                    )

            if result.returncode != 0:
                return []

            video_ids = [vid.strip() for vid in result.stdout.strip().split("\n") if vid.strip()]
            if not video_ids:
                return []

            # 最新20件に制限
            video_ids = video_ids[:20]

            # Step 2: 各動画の概要欄を取得
            descriptions = []
            yt_dlp_cmd = "yt-dlp"
            yt_dlp_path = Path.home() / "Library" / "Python" / "3.9" / "bin" / "yt-dlp"
            if yt_dlp_path.exists():
                yt_dlp_cmd = str(yt_dlp_path)

            for vid in video_ids:
                try:
                    vid_result = subprocess.run(
                        [
                            yt_dlp_cmd, "--skip-download",
                            "--print", "%(description)s",
                            f"https://www.youtube.com/watch?v={vid}",
                        ],
                        capture_output=True, text=True, timeout=15,
                    )
                    if vid_result.returncode == 0:
                        desc = vid_result.stdout.strip()
                        if desc and len(desc) > 50:  # 短すぎるものは除外
                            descriptions.append(desc)
                except subprocess.TimeoutExpired:
                    continue

                # 10件取得したら終了（プロンプトサイズ管理）
                if len(descriptions) >= 10:
                    break

            return descriptions

        except FileNotFoundError:
            # yt-dlp未インストール
            return []
        except Exception:
            return []


# ---------------------------------------------------------------------------
# YouTube Data API v3 — 最新通常動画の概要欄をテンプレートとして取得
# ---------------------------------------------------------------------------

def fetch_latest_description_template() -> str | None:
    """YouTube Data API v3でTEKOチャンネルの最新通常動画の概要欄を取得する。

    Shorts（タイトルに#shortsを含む or 概要欄が300文字未満）を除外し、
    最新の通常動画の概要欄をテンプレートとして返す。

    取得失敗時はNoneを返す（呼び出し側でフォールバック処理）。
    24時間キャッシュを使用してAPI呼び出し回数を削減する。
    """
    # キャッシュ確認
    cache_file = Path.home() / "AI開発10" / ".cache" / "youtube_template.json"
    cached = _load_template_cache(cache_file)
    if cached is not None:
        return cached

    try:
        from dotenv import load_dotenv
        import os
        load_dotenv(Path.home() / "AI開発10" / ".env")
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            return None

        channel_id = KnowledgeLoader.YOUTUBE_CHANNEL_ID

        # Step 1: search.list で最新動画10件のIDを取得（100ユニット/回）
        search_params = urllib.parse.urlencode({
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": 10,
            "key": api_key,
        })
        search_url = f"https://www.googleapis.com/youtube/v3/search?{search_params}"
        req = urllib.request.Request(search_url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            search_data = _json.loads(resp.read().decode("utf-8"))

        items = search_data.get("items", [])
        if not items:
            return None

        video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
        if not video_ids:
            return None

        # Step 2: videos.list で各動画のsnippetを取得（1ユニット/回）
        videos_params = urllib.parse.urlencode({
            "part": "snippet",
            "id": ",".join(video_ids),
            "key": api_key,
        })
        videos_url = f"https://www.googleapis.com/youtube/v3/videos?{videos_params}"
        req2 = urllib.request.Request(videos_url)
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            videos_data = _json.loads(resp2.read().decode("utf-8"))

        # Step 3: Shorts除外 → 最初の通常動画の概要欄を返す
        for v in videos_data.get("items", []):
            snippet = v.get("snippet", {})
            title = snippet.get("title", "")
            description = snippet.get("description", "")

            # Shorts判定: タイトルに#shorts or 概要欄300文字未満
            if "#shorts" in title.lower():
                continue
            if len(description) < 300:
                continue

            # 通常動画の概要欄を発見
            _save_template_cache(cache_file, description)
            return description

        return None

    except Exception:
        return None


def _load_template_cache(cache_file: Path) -> str | None:
    """テンプレートキャッシュを読み込む（24時間有効）"""
    try:
        if not cache_file.exists():
            return None
        data = _json.loads(cache_file.read_text(encoding="utf-8"))
        cached_at = data.get("cached_at", 0)
        if _time.time() - cached_at > 86400:
            return None
        return data.get("template")
    except Exception:
        return None


def _save_template_cache(cache_file: Path, template: str):
    """テンプレートをキャッシュに保存"""
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cached_at": _time.time(),
            "template": template,
        }
        cache_file.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
