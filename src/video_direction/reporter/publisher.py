from __future__ import annotations
"""GitHub Pages への公開 — direction-pages リポジトリ管理"""

import re
import subprocess
from pathlib import Path
from datetime import datetime
from .html_generator import generate_index_html


REPO_OWNER = "38maekawa-create"
REPO_NAME = "direction-pages"
CACHE_DIR = Path.home() / ".cache" / REPO_NAME
PAGES_BASE_URL = f"https://{REPO_OWNER}.github.io/{REPO_NAME}"


def publish_direction_page(
    html_content: str,
    guest_name: str,
    tier: str = "",
    date_str: str = "",
) -> str:
    """ディレクションHTMLをGitHub Pagesに公開し、公開URLを返す"""
    repo_path = _ensure_repo(CACHE_DIR)

    # ファイル名生成
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    slug = _safe_filename(guest_name)
    filename = f"{date_str}_{slug}_direction.html"

    # HTMLファイル書き込み
    filepath = repo_path / filename
    filepath.write_text(html_content, encoding="utf-8")

    # index.html更新
    _update_index(repo_path, tier_map={filename: tier})

    # git add + commit + push
    _git_push(repo_path, f"追加: {guest_name} ディレクションレポート")

    return f"{PAGES_BASE_URL}/{filename}"


def _ensure_repo(cache_dir: Path) -> Path:
    """リポジトリがクローン済みか確認し、なければクローンする"""
    if cache_dir.exists() and (cache_dir / ".git").exists():
        # 既存リポジトリをpull
        subprocess.run(
            ["git", "pull", "--rebase"],
            cwd=cache_dir,
            capture_output=True,
            timeout=30,
        )
        return cache_dir

    # クローンを試行
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["gh", "repo", "clone", f"{REPO_OWNER}/{REPO_NAME}", str(cache_dir)],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        # リポジトリが存在しない → 新規作成
        _create_repo(cache_dir)

    return cache_dir


def _create_repo(cache_dir: Path):
    """新規リポジトリを作成する"""
    cache_dir.mkdir(parents=True, exist_ok=True)

    # git init
    subprocess.run(["git", "init"], cwd=cache_dir, capture_output=True)

    # 初期ファイル作成
    (cache_dir / ".gitignore").write_text(".DS_Store\n", encoding="utf-8")
    (cache_dir / "index.html").write_text(
        generate_index_html([]), encoding="utf-8"
    )

    # 初期コミット
    subprocess.run(["git", "add", "."], cwd=cache_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "初期化: ディレクションレポートリポジトリ"],
        cwd=cache_dir,
        capture_output=True,
    )

    # GitHubリポジトリ作成 + push
    subprocess.run(
        ["gh", "repo", "create", f"{REPO_OWNER}/{REPO_NAME}",
         "--public", "--source", str(cache_dir), "--push"],
        capture_output=True,
        text=True,
        timeout=30,
    )


def _update_index(repo_path: Path, tier_map: dict = None):
    """index.htmlを全HTMLファイルリストから再生成する"""
    existing_tiers = _extract_existing_tier_map(repo_path / "index.html")
    if tier_map is None:
        tier_map = {}
    merged_tiers = {**existing_tiers, **tier_map}

    pages = []
    for f in sorted(repo_path.glob("*_direction.html")):
        # ファイル名からメタ情報抽出
        name_parts = f.stem.split("_")
        date_str = name_parts[0] if name_parts else ""
        # YYYYMMDD → YYYY/MM/DD
        formatted_date = ""
        if len(date_str) == 8 and date_str.isdigit():
            formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"

        # ゲスト名抽出
        guest = "_".join(name_parts[1:-1]) if len(name_parts) > 2 else f.stem
        guest = guest.replace("_", " ")

        tier = merged_tiers.get(f.name, "")

        pages.append({
            "filename": f.name,
            "title": f"ディレクション: {guest}",
            "date": formatted_date,
            "tier": tier,
        })

    index_html = generate_index_html(pages)
    (repo_path / "index.html").write_text(index_html, encoding="utf-8")


def _extract_existing_tier_map(index_path: Path) -> dict[str, str]:
    """既存 index.html から filename -> tier を抽出する"""
    if not index_path.exists():
        return {}

    text = index_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r'<a[^>]+href="([^"]+_direction\.html)"[^>]*>.*?</a>\s*'
        r'<span[^>]+class="[^"]*\btier-([a-z])\b[^"]*"',
        re.IGNORECASE | re.DOTALL,
    )
    return {filename: tier.lower() for filename, tier in pattern.findall(text)}


def _git_push(repo_path: Path, message: str):
    """git add + commit + push"""
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)

    # 変更があるか確認
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=repo_path,
        capture_output=True,
    )
    if result.returncode == 0:
        return  # 変更なし

    subprocess.run(
        ["git", "commit", "-m", message[:60]],
        cwd=repo_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push"],
        cwd=repo_path,
        capture_output=True,
        timeout=30,
    )


def _safe_filename(text: str) -> str:
    """URLセーフなファイル名を生成"""
    # 日本語のカタカナ・ひらがな・漢字はそのまま保持
    safe = re.sub(r'[^\w\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF-]', '_', text)
    safe = re.sub(r'_+', '_', safe).strip('_')
    return safe[:50]
