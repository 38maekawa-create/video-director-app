"""member_master のユニットテスト"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.integrations.member_master import MemberMaster


class TestMemberMaster:
    """メンバーマスターのテスト"""

    def test_load(self):
        """MEMBER_MASTER.jsonが読み込める"""
        mm = MemberMaster()
        assert len(mm.all_members) > 0

    def test_find_by_canonical(self):
        """正式名で検索できる"""
        mm = MemberMaster()
        member = mm.find_member("PAY")
        assert member is not None
        assert member.canonical_name == "PAY"

    def test_find_by_alias(self):
        """エイリアスで検索できる"""
        mm = MemberMaster()
        member = mm.find_member("payさん")
        assert member is not None
        assert member.canonical_name == "PAY"

    def test_find_with_san(self):
        """「さん」付きで検索できる"""
        mm = MemberMaster()
        member = mm.find_member("RYO")
        if member:
            assert member.canonical_name == "RYO"

    def test_not_found(self):
        """存在しないメンバーはNone"""
        mm = MemberMaster()
        member = mm.find_member("存在しない人物XYZ")
        assert member is None
