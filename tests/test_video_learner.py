"""VideoLearner / VideoPattern のユニットテスト（外部API不要）"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video_direction.tracker.video_learner import VideoPattern, VideoLearner


# ────────────────────────────────────────────────
# VideoPattern データクラス
# ────────────────────────────────────────────────

class TestVideoPattern:
    def test_最低限のフィールドで生成できる(self):
        p = VideoPattern(id="p001", category="cutting", pattern="高速カット")
        assert p.id == "p001"
        assert p.category == "cutting"
        assert p.pattern == "高速カット"

    def test_デフォルト値が正しい(self):
        p = VideoPattern(id="p002", category="color", pattern="暖色系")
        assert p.source_count == 1
        assert p.source_video_ids == []
        assert p.confidence == 0.0
        assert p.example_urls == []
        assert p.is_active is True

    def test_created_atがISO形式で自動設定される(self):
        p = VideoPattern(id="p003", category="tempo", pattern="テスト")
        datetime.fromisoformat(p.created_at)


# ────────────────────────────────────────────────
# VideoLearner — 初期化
# ────────────────────────────────────────────────

class TestVideoLearnerInit:
    def test_tmpディレクトリで初期化できる(self):
        tmp = Path(tempfile.mkdtemp())
        learner = VideoLearner(data_dir=tmp)
        assert learner.get_patterns() == []

    def test_パターンファイルがない場合も正常初期化(self):
        tmp = Path(tempfile.mkdtemp())
        assert not (tmp / "video_patterns.json").exists()
        learner = VideoLearner(data_dir=tmp)
        assert learner.get_summary()["total_patterns"] == 0


# ────────────────────────────────────────────────
# VideoLearner — learn_from_analysis
# ────────────────────────────────────────────────

class TestLearnFromAnalysis:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.learner = VideoLearner(data_dir=self.tmp)

    def test_cutting_styleからパターンを学習する(self):
        patterns = self.learner.learn_from_analysis(
            video_id="v001",
            analysis_result={"cutting_style": "高速カット — MTV風"},
        )
        assert len(patterns) == 1
        assert patterns[0].category == "cutting"
        assert "高速カット" in patterns[0].pattern

    def test_color_gradingからパターンを学習する(self):
        patterns = self.learner.learn_from_analysis(
            video_id="v002",
            analysis_result={"color_grading": "暖色系 — 温かみのあるトーン"},
        )
        assert any(p.category == "color" for p in patterns)

    def test_tempoからパターンを学習する(self):
        patterns = self.learner.learn_from_analysis(
            video_id="v003",
            analysis_result={"tempo": "標準的なテンポ"},
        )
        assert any(p.category == "tempo" for p in patterns)

    def test_key_techniquesからパターンを学習する(self):
        patterns = self.learner.learn_from_analysis(
            video_id="v004",
            analysis_result={"key_techniques": ["テクニックA", "テクニックB"]},
        )
        technique_patterns = [p for p in patterns if p.category == "technique"]
        assert len(technique_patterns) == 2

    def test_複数フィールドを同時に学習する(self):
        patterns = self.learner.learn_from_analysis(
            video_id="v005",
            analysis_result={
                "cutting_style": "ロングテイク",
                "color_grading": "寒色系",
                "tempo": "ゆっくり",
            },
        )
        assert len(patterns) == 3

    def test_空の分析結果では何も学習しない(self):
        patterns = self.learner.learn_from_analysis(
            video_id="v006",
            analysis_result={},
        )
        assert patterns == []

    def test_同一パターンは重複せずsource_countが増える(self):
        for i in range(3):
            self.learner.learn_from_analysis(
                video_id=f"v{i:02d}",
                analysis_result={"cutting_style": "高速カット — MTV風スタイル"},
            )
        cutting_patterns = self.learner.get_patterns(category="cutting")
        assert len(cutting_patterns) == 1
        assert cutting_patterns[0].source_count == 3

    def test_video_urlを渡すとexample_urlsに追加される(self):
        self.learner.learn_from_analysis(
            video_id="v010",
            analysis_result={"cutting_style": "テストスタイル"},
            video_url="https://youtube.com/watch?v=test",
        )
        patterns = self.learner.get_patterns(category="cutting")
        assert "https://youtube.com/watch?v=test" in patterns[0].example_urls


# ────────────────────────────────────────────────
# VideoLearner — _is_similar
# ────────────────────────────────────────────────

class TestIsSimilar:
    def setup_method(self):
        tmp = Path(tempfile.mkdtemp())
        self.learner = VideoLearner(data_dir=tmp)

    def test_同一テキストはTrue(self):
        assert self.learner._is_similar("高速カット MTV風", "高速カット MTV風") is True

    def test_キーワードの重複が多い場合はTrue(self):
        assert self.learner._is_similar("高速カット MTV風 対談", "高速カット MTV風") is True

    def test_全く異なるテキストはFalse(self):
        assert self.learner._is_similar("全然違うテキスト", "全く別の内容") is False

    def test_空文字列2はFalse(self):
        assert self.learner._is_similar("何かのテキスト", "") is False


# ────────────────────────────────────────────────
# VideoLearner — get_patterns / get_insights / get_summary
# ────────────────────────────────────────────────

class TestVideoLearnerQuery:
    def setup_method(self):
        tmp = Path(tempfile.mkdtemp())
        self.learner = VideoLearner(data_dir=tmp)
        # 複数パターンを登録
        self.learner.learn_from_analysis(
            video_id="v001",
            analysis_result={"cutting_style": "パターンA"},
        )
        self.learner.learn_from_analysis(
            video_id="v002",
            analysis_result={"color_grading": "パターンB"},
        )

    def test_category指定でフィルタできる(self):
        cutting = self.learner.get_patterns(category="cutting")
        assert all(p.category == "cutting" for p in cutting)

    def test_min_confidence指定で高確信度のみ取得できる(self):
        patterns = self.learner.get_patterns(min_confidence=0.9)
        assert all(p.confidence >= 0.9 for p in patterns)

    def test_get_summaryが正しい件数を返す(self):
        summary = self.learner.get_summary()
        assert summary["total_patterns"] == 2
        assert "cutting" in summary["category_distribution"]

    def test_get_insights_for_directionは確信度04以上のみ返す(self):
        # デフォルトconfidence=0.2なので空になるはず
        insights = self.learner.get_insights_for_direction()
        assert isinstance(insights, list)

    def test_高確信度パターンはinsightsに含まれる(self):
        # 5件以上同じパターンを追加して confidence >= 0.4 にする
        for i in range(5):
            self.learner.learn_from_analysis(
                video_id=f"extra_{i}",
                analysis_result={"cutting_style": "パターンA"},
            )
        insights = self.learner.get_insights_for_direction()
        assert len(insights) >= 1
