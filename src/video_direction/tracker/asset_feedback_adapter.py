"""音声FBをEditLearnerのingest_edit()互換形式に変換するアダプター

AI生成物（タイトル・概要欄等）への音声FBを、EditLearnerが期待する
diff_resultオブジェクトに変換する薄いレイヤー。
EditLearner自体のインタフェースは変更しない。
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class VoiceFBDiffResult:
    """EditLearner.ingest_edit()が期待するdiff_result互換オブジェクト

    Attributes:
        changes: EditLearnerが期待するchange辞書のリスト
        edit_id: この音声FBの一意識別子
    """
    changes: list = field(default_factory=list)
    edit_id: str = ""


def voice_fb_to_edit_diff(fb_text: str, asset_type: str) -> VoiceFBDiffResult:
    """音声FBテキストからEditLearner互換のdiff結果を生成する

    Args:
        fb_text: 音声FBのテキスト（変換済みまたは生テキスト）
        asset_type: 対象アセットタイプ（"title" / "description"）

    Returns:
        VoiceFBDiffResult: EditLearner.ingest_edit()に渡せるオブジェクト
    """
    edit_id = f"voicefb_{asset_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    changes = [{
        "type": "modify",
        "content": fb_text,
        "context": f"音声フィードバック（{asset_type}）",
    }]
    return VoiceFBDiffResult(changes=changes, edit_id=edit_id)
