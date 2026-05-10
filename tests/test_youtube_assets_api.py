"""YouTube素材APIのUI互換変換テスト"""

from src.video_direction.integrations.api_server import (
    _normalize_youtube_title_proposals_for_ui,
)


def test_normalize_title_proposals_fills_swift_required_fields():
    proposals = {
        "candidates": [
            {
                "title": "バーボンさん対談（2026-03-28）",
                "source": "ai10_propagation_minimal_draft",
                "rank": 1,
            }
        ],
        "quality": "draft_placeholder_until_ai10_copy_agent",
    }

    normalized = _normalize_youtube_title_proposals_for_ui(proposals)

    assert normalized["recommended_index"] == 0
    candidate = normalized["candidates"][0]
    assert candidate["target_segment"] == "TEKO対談視聴者"
    assert candidate["appeal_type"] == "暫定候補"
    assert "既存AI10素材の候補1" in candidate["rationale"]


def test_normalize_title_proposals_preserves_existing_fields():
    proposals = {
        "recommended_index": 2,
        "candidates": [
            {
                "title": "完成タイトル",
                "target_segment": "20代会社員",
                "appeal_type": "逆説",
                "rationale": "原文のパンチラインが強い",
            }
        ],
    }

    normalized = _normalize_youtube_title_proposals_for_ui(
        proposals,
        selected_title_index=0,
    )

    assert normalized == proposals
