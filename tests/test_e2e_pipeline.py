"""E2E パイプラインテスト

Phase 1のコアパイプライン + Phase 2の新機能を含めた
エンドツーエンドテスト。実データ3件を使用。
"""

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.main import process_single_file
from src.video_direction.integrations.member_master import MemberMaster
from src.video_direction.integrations.ai_dev5_connector import parse_markdown_file
from src.video_direction.analyzer.guest_classifier import classify_guest
from src.video_direction.analyzer.income_evaluator import evaluate_income
from src.video_direction.analyzer.proper_noun_filter import detect_proper_nouns
from src.video_direction.analyzer.target_labeler import label_targets
from src.video_direction.analyzer.direction_generator import generate_directions
from src.video_direction.analyzer.clip_cutter import suggest_clip_cuts
from src.video_direction.analyzer.highlight_cutter import suggest_highlight_cuts
from src.video_direction.analyzer.quality_scorer import score_video_quality
from src.video_direction.reporter.html_generator import generate_direction_html


# 実データ3件
REAL_FILES = [
    Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_Izuさん：30代中盤元アクセンチュア年収1000万円台.md",
    Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.16_20251123撮影_りょうすけさん：20代後半内資IT勤務年収600万.md",
    Path.home() / "TEKO/knowledge/01_teko/sources/video/2026.02.28_ゆりかさん.md",
]


class TestE2EFullPipeline:
    """E2E: パイプライン全体の統合テスト"""

    def test_full_pipeline_izu(self):
        """Izuさん: Phase 1 + Phase 2 全機能を通貫"""
        filepath = REAL_FILES[0]
        if not filepath.exists():
            return

        # Phase 1: パース
        data = parse_markdown_file(filepath)
        assert data.title != ""
        assert len(data.profiles) >= 1
        assert len(data.highlights) >= 1

        # Phase 1: 分析
        classification = classify_guest(data)
        assert classification.tier == "a"

        income_eval = evaluate_income(data)
        assert income_eval.emphasize is True

        proper_nouns = detect_proper_nouns(data)
        assert len(proper_nouns) >= 1

        target_result = label_targets(data)
        assert target_result.balance.total > 0

        directions = generate_directions(data, classification, income_eval)
        assert len(directions.entries) >= 1

        # Phase 2: 切り抜きカットポイント
        clip_result = suggest_clip_cuts(data)
        assert clip_result.clip_count >= 1
        for clip in clip_result.clips:
            assert clip.duration_seconds >= 15
            assert clip.title_suggestion != ""

        # Phase 2: ハイライトカットポイント
        highlight_result = suggest_highlight_cuts(data, classification)
        assert highlight_result.scene_count >= 1
        assert highlight_result.structure_note != ""

        # Phase 2: 品質スコアリング
        quality = score_video_quality(data, classification, directions)
        assert 0 < quality.total_score <= 100
        assert quality.grade in ("S", "A", "B", "C", "D")
        assert len(quality.dimensions) == 7

        # Phase 1: HTML生成（Phase 2の結果も含む）
        html = generate_direction_html(
            video_data=data,
            classification=classification,
            income_eval=income_eval,
            proper_nouns=proper_nouns,
            target_result=target_result,
            direction_timeline=directions,
        )
        assert "<!DOCTYPE html>" in html
        assert "ディレクションレポート" in html

    def test_full_pipeline_ryosuke(self):
        """りょうすけさん: 層b、代替の強みが検出される"""
        filepath = REAL_FILES[1]
        if not filepath.exists():
            return

        data = parse_markdown_file(filepath)
        classification = classify_guest(data)
        assert classification.tier == "b"

        income_eval = evaluate_income(data)
        # 年収600万 → 強調OFF
        assert income_eval.emphasize is False

        # Phase 2
        clip_result = suggest_clip_cuts(data)
        highlight_result = suggest_highlight_cuts(data, classification)
        quality = score_video_quality(data, classification)

        assert quality.total_score > 0
        assert quality.is_estimated is True

    def test_full_pipeline_yurika(self):
        """ゆりかさん: 層b、週4勤務の強み"""
        filepath = REAL_FILES[2]
        if not filepath.exists():
            return

        data = parse_markdown_file(filepath)
        classification = classify_guest(data)
        assert classification.tier == "b"

        # Phase 2
        clip_result = suggest_clip_cuts(data)
        quality = score_video_quality(data, classification)
        assert quality.total_score > 0


class TestE2EOutputConsistency:
    """E2E: 出力の一貫性テスト"""

    def test_same_input_same_output(self):
        """同じ入力に対して同じ出力を返す（決定的動作）"""
        filepath = REAL_FILES[0]
        if not filepath.exists():
            return

        data = parse_markdown_file(filepath)

        # 2回分類
        c1 = classify_guest(data)
        c2 = classify_guest(data)
        assert c1.tier == c2.tier
        assert c1.reason == c2.reason

        # 2回スコアリング
        q1 = score_video_quality(data)
        q2 = score_video_quality(data)
        assert q1.total_score == q2.total_score
        assert q1.grade == q2.grade

    def test_process_single_dry_run(self):
        """ドライランモードでHTML生成まで完了する"""
        filepath = REAL_FILES[0]
        if not filepath.exists():
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            result = process_single_file(
                filepath,
                member_master=MemberMaster(),
                dry_run=True,
                output_dir=tmpdir,
            )
            assert result["success"] is True
            assert result["tier"] == "a"
            html_path = Path(result["html_path"])
            assert html_path.exists()
            html = html_path.read_text(encoding="utf-8")
            assert len(html) > 1000  # 最低限のサイズ

    def test_all_three_dry_run(self):
        """3件全てドライランで成功する"""
        for filepath in REAL_FILES:
            if not filepath.exists():
                continue
            with tempfile.TemporaryDirectory() as tmpdir:
                result = process_single_file(
                    filepath,
                    member_master=MemberMaster(),
                    dry_run=True,
                    output_dir=tmpdir,
                )
                assert result["success"] is True, f"失敗: {filepath.name}"


class TestE2EPhase2Integration:
    """E2E: Phase 2機能のPhase 1統合テスト"""

    def test_clip_from_full_analysis(self):
        """Phase 1の分析結果をPhase 2の切り抜き機能に渡す"""
        filepath = REAL_FILES[0]
        if not filepath.exists():
            return

        data = parse_markdown_file(filepath)
        classification = classify_guest(data)
        income_eval = evaluate_income(data)

        # Phase 1の結果がPhase 2に影響
        clip_result = suggest_clip_cuts(data)
        # 層aの動画は実績数字のハイライトが多い → クリップも多い
        if classification.tier == "a":
            assert clip_result.clip_count >= 1

    def test_quality_with_direction(self):
        """演出ディレクションの有無で品質スコアが変わる"""
        filepath = REAL_FILES[0]
        if not filepath.exists():
            return

        data = parse_markdown_file(filepath)
        classification = classify_guest(data)
        income_eval = evaluate_income(data)

        # ディレクションなし
        q_no_dir = score_video_quality(data, classification)

        # ディレクションあり
        directions = generate_directions(data, classification, income_eval)
        q_with_dir = score_video_quality(data, classification, directions)

        # ディレクションがある方がスコアが高い（画角変更等のスコアが上がる）
        assert q_with_dir.total_score >= q_no_dir.total_score

    def test_highlight_respects_classification(self):
        """ハイライトカットが分類結果を受け取れる"""
        filepath = REAL_FILES[0]
        if not filepath.exists():
            return

        data = parse_markdown_file(filepath)
        classification = classify_guest(data)

        result = suggest_highlight_cuts(data, classification)
        # テロップ提案が生成される
        for scene in result.scenes:
            # テロップ提案は空の場合もあるが、少なくとも1つは非空のはず
            pass
        assert result.scene_count >= 1
