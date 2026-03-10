from __future__ import annotations
"""H-1: メンバーマスター自動連動"""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class MemberInfo:
    """メンバー情報"""
    canonical_name: str
    aliases: list = field(default_factory=list)
    has_people_file: bool = False
    people_file_path: str = ""
    video_transcripts: list = field(default_factory=list)


class MemberMaster:
    """MEMBER_MASTER.json を読み込み、メンバー属性の自動参照を提供する"""

    def __init__(self, master_path: str | Path = None):
        if master_path is None:
            master_path = Path.home() / "TEKO" / "knowledge" / "people" / "MEMBER_MASTER.json"
        self.master_path = Path(master_path)
        self._members: dict[str, MemberInfo] = {}
        self._alias_map: dict[str, str] = {}  # alias -> canonical_name
        self._load()

    def _load(self):
        """MEMBER_MASTER.jsonを読み込む"""
        if not self.master_path.exists():
            return
        data = json.loads(self.master_path.read_text(encoding="utf-8"))
        for m in data.get("members", []):
            info = MemberInfo(
                canonical_name=m["canonical_name"],
                aliases=m.get("aliases", []),
                has_people_file=m.get("has_people_file", False),
                people_file_path=m.get("source_of_truth", "") or "",
                video_transcripts=m.get("data_locations", {}).get("video_transcripts", []),
            )
            self._members[info.canonical_name] = info
            # エイリアスマップ構築
            for alias in info.aliases:
                self._alias_map[alias.lower()] = info.canonical_name
            self._alias_map[info.canonical_name.lower()] = info.canonical_name

    def find_member(self, name: str) -> MemberInfo | None:
        """名前（正式名・エイリアス）からメンバー情報を検索"""
        # 完全一致
        canonical = self._alias_map.get(name.lower())
        if canonical:
            return self._members.get(canonical)

        # 「さん」の有無で再試行
        name_no_san = name.rstrip("さん")
        canonical = self._alias_map.get(name_no_san.lower())
        if canonical:
            return self._members.get(canonical)

        name_with_san = name + "さん"
        canonical = self._alias_map.get(name_with_san.lower())
        if canonical:
            return self._members.get(canonical)

        # 部分一致
        for alias, canon in self._alias_map.items():
            if name.lower() in alias or alias in name.lower():
                return self._members.get(canon)
        return None

    def get_people_profile(self, member: MemberInfo) -> str:
        """メンバーの詳細プロファイルファイルを読み込む"""
        if not member.has_people_file or not member.people_file_path:
            return ""
        people_dir = self.master_path.parent
        profile_path = people_dir / Path(member.people_file_path).name
        if profile_path.exists():
            return profile_path.read_text(encoding="utf-8")
        return ""

    @property
    def all_members(self) -> list[MemberInfo]:
        return list(self._members.values())
