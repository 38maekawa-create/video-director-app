"""品質メトリクス統計計算モジュール

SQLiteのprojects/feedbacksテーブルとFeedbackLearnerのJSONデータから
品質ダッシュボード用の統計情報を算出する。
キャッシュ付きで頻繁なリクエストに対応。
"""

from __future__ import annotations

import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# キャッシュTTL（秒）
_CACHE_TTL = 60

# グレード境界値（0-100スケール）
_GRADE_BOUNDARIES = [
    (90, "A+"),
    (80, "A"),
    (70, "B+"),
    (60, "B"),
    (50, "C"),
    (40, "D"),
    (0, "E"),
]


def _grade_from_score(score: int) -> str:
    """0-100スケールのスコアをグレードに変換"""
    for boundary, grade in _GRADE_BOUNDARIES:
        if score >= boundary:
            return grade
    return "E"


@dataclass
class ProjectQualityTrend:
    """プロジェクト別品質スコアトレンド"""
    project_id: str
    guest_name: str
    title: str
    data_points: list = field(default_factory=list)
    # data_points: [{"date": str, "score": int, "grade": str}]


@dataclass
class CategoryProblemRanking:
    """カテゴリ別の問題頻度ランキング"""
    category: str
    count: int
    percentage: float  # 全フィードバック中の割合
    recent_examples: list = field(default_factory=list)


@dataclass
class EditorQualityProfile:
    """編集者別の品質傾向"""
    editor_name: str
    project_count: int
    average_score: float
    grade_distribution: dict = field(default_factory=dict)
    trend: str = ""  # "improving" / "stable" / "declining"
    recent_scores: list = field(default_factory=list)


@dataclass
class LearningRuleEffect:
    """FB学習ルールの適用効果"""
    rule_id: str
    rule_text: str
    category: str
    applied_count: int
    avg_score_before: Optional[float] = None
    avg_score_after: Optional[float] = None
    effect_delta: Optional[float] = None


@dataclass
class QualityStatsResult:
    """品質統計の全体結果"""
    # 基本統計
    total_projects: int = 0
    scored_projects: int = 0
    average_score: Optional[float] = None
    median_score: Optional[float] = None
    score_std_dev: Optional[float] = None

    # グレード分布
    grade_distribution: dict = field(default_factory=dict)

    # プロジェクト別トレンド
    project_trends: list = field(default_factory=list)

    # カテゴリ別問題頻度
    category_ranking: list = field(default_factory=list)

    # 編集者別品質
    editor_profiles: list = field(default_factory=list)

    # FB学習ルール効果
    learning_rule_effects: list = field(default_factory=list)

    # 改善率統計
    improvement_stats: dict = field(default_factory=dict)

    # 時系列サマリー（月別）
    monthly_averages: list = field(default_factory=list)

    # 生成時刻
    generated_at: str = ""


class QualityStatsCalculator:
    """品質統計計算エンジン

    SQLiteデータベースとFeedbackLearnerのJSONから統計情報を算出する。
    結果はTTL付きでキャッシュされる。
    """

    def __init__(self, db_path: Path, learning_data_dir: Optional[Path] = None):
        """初期化

        Args:
            db_path: SQLiteデータベースのパス
            learning_data_dir: FeedbackLearnerのデータディレクトリ（Noneの場合はデフォルト）
        """
        self._db_path = db_path
        self._learning_data_dir = learning_data_dir or (
            Path.home() / "AI開発10" / ".data" / "learning"
        )
        self._cache: dict[str, tuple[float, object]] = {}  # {key: (timestamp, data)}

    def _get_db(self) -> sqlite3.Connection:
        """DB接続を取得"""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_cached(self, key: str) -> Optional[object]:
        """キャッシュから取得（TTL超過なら None）"""
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < _CACHE_TTL:
                return data
        return None

    def _set_cached(self, key: str, data: object):
        """キャッシュに保存"""
        self._cache[key] = (time.time(), data)

    def invalidate_cache(self):
        """キャッシュを全て無効化"""
        self._cache.clear()

    # ------------------------------------------------------------------
    # プロジェクト別品質スコアトレンド
    # ------------------------------------------------------------------

    def get_project_trends(self, limit: int = 20) -> list[dict]:
        """プロジェクト別の品質スコアトレンドを取得

        各プロジェクトのスコア推移（時系列）を返す。
        shoot_date順にソートし、直近limitプロジェクトを返す。
        """
        cache_key = f"project_trends_{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        conn = self._get_db()
        rows = conn.execute(
            "SELECT id, guest_name, title, shoot_date, quality_score, status, "
            "created_at, updated_at "
            "FROM projects WHERE quality_score IS NOT NULL "
            "ORDER BY shoot_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()

        trends = []
        for r in rows:
            grade = _grade_from_score(r["quality_score"])
            trends.append({
                "project_id": r["id"],
                "guest_name": r["guest_name"],
                "title": r["title"],
                "shoot_date": r["shoot_date"],
                "quality_score": r["quality_score"],
                "grade": grade,
                "status": r["status"],
            })

        # 日付昇順に並び替え（時系列として使いやすくする）
        trends.reverse()

        self._set_cached(cache_key, trends)
        return trends

    # ------------------------------------------------------------------
    # カテゴリ別問題頻度ランキング
    # ------------------------------------------------------------------

    def get_category_problem_ranking(self, limit: int = 10) -> list[dict]:
        """フィードバックのカテゴリ別問題頻度ランキング

        feedbacksテーブルのcategoryを集計し、頻度の高い順にランキングを返す。
        """
        cache_key = f"category_ranking_{limit}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        conn = self._get_db()

        # 全件数
        total_count = conn.execute(
            "SELECT COUNT(*) FROM feedbacks WHERE category IS NOT NULL AND category != ''"
        ).fetchone()[0]

        # カテゴリ別集計
        rows = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM feedbacks "
            "WHERE category IS NOT NULL AND category != '' "
            "GROUP BY category ORDER BY cnt DESC LIMIT ?",
            (limit,),
        ).fetchall()

        ranking = []
        for r in rows:
            # 直近の事例を3件取得
            examples = conn.execute(
                "SELECT converted_text, project_id FROM feedbacks "
                "WHERE category = ? ORDER BY created_at DESC LIMIT 3",
                (r["category"],),
            ).fetchall()

            pct = round(r["cnt"] / total_count * 100, 1) if total_count > 0 else 0
            ranking.append({
                "category": r["category"],
                "count": r["cnt"],
                "percentage": pct,
                "recent_examples": [
                    {"text": ex["converted_text"], "project_id": ex["project_id"]}
                    for ex in examples
                ],
            })

        conn.close()
        self._set_cached(cache_key, ranking)
        return ranking

    # ------------------------------------------------------------------
    # 編集者別品質傾向
    # ------------------------------------------------------------------

    def get_editor_quality_profiles(self) -> list[dict]:
        """編集者別の品質傾向を算出

        feedbacksテーブルのcreated_byをキーにして、
        関連プロジェクトの品質スコアを集計する。
        """
        cache_key = "editor_profiles"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        conn = self._get_db()

        # feedbacksのcreated_byでグルーピングし、関連プロジェクトのスコアを取得
        rows = conn.execute(
            "SELECT DISTINCT f.created_by, f.project_id, p.quality_score, p.shoot_date "
            "FROM feedbacks f "
            "JOIN projects p ON f.project_id = p.id "
            "WHERE f.created_by IS NOT NULL AND f.created_by != '' "
            "AND p.quality_score IS NOT NULL "
            "ORDER BY f.created_by, p.shoot_date ASC"
        ).fetchall()
        conn.close()

        # 編集者ごとに集計
        editor_data: dict[str, list] = defaultdict(list)
        editor_projects: dict[str, set] = defaultdict(set)
        for r in rows:
            editor = r["created_by"]
            pid = r["project_id"]
            if pid not in editor_projects[editor]:
                editor_projects[editor].add(pid)
                editor_data[editor].append({
                    "score": r["quality_score"],
                    "date": r["shoot_date"],
                })

        profiles = []
        for editor, data_points in editor_data.items():
            scores = [d["score"] for d in data_points]
            if not scores:
                continue

            avg = round(sum(scores) / len(scores), 1)

            # グレード分布
            grade_dist: dict[str, int] = {}
            for s in scores:
                g = _grade_from_score(s)
                grade_dist[g] = grade_dist.get(g, 0) + 1

            # トレンド判定（直近3件の平均 vs その前3件の平均）
            trend = "stable"
            if len(scores) >= 6:
                recent_avg = sum(scores[-3:]) / 3
                prev_avg = sum(scores[-6:-3]) / 3
                delta = recent_avg - prev_avg
                if delta > 3:
                    trend = "improving"
                elif delta < -3:
                    trend = "declining"
            elif len(scores) >= 2:
                if scores[-1] > scores[0] + 3:
                    trend = "improving"
                elif scores[-1] < scores[0] - 3:
                    trend = "declining"

            profiles.append({
                "editor_name": editor,
                "project_count": len(scores),
                "average_score": avg,
                "grade_distribution": grade_dist,
                "trend": trend,
                "recent_scores": scores[-5:],
            })

        # 平均スコア降順でソート
        profiles.sort(key=lambda p: p["average_score"], reverse=True)

        self._set_cached(cache_key, profiles)
        return profiles

    # ------------------------------------------------------------------
    # FB学習ルールの適用効果測定
    # ------------------------------------------------------------------

    def get_learning_rule_effects(self) -> list[dict]:
        """FB学習ルールの適用効果を測定

        learning_rules.jsonのルールごとに、適用前後の品質スコア変化を推定する。
        ルールのcreated_atを境に、同カテゴリのプロジェクトスコアを比較する。
        """
        cache_key = "learning_rule_effects"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        import json

        rules_path = self._learning_data_dir / "learning_rules.json"
        if not rules_path.exists():
            self._set_cached(cache_key, [])
            return []

        try:
            rules_data = json.loads(rules_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            self._set_cached(cache_key, [])
            return []

        rules = rules_data.get("rules", [])
        if not rules:
            self._set_cached(cache_key, [])
            return []

        conn = self._get_db()

        # 全プロジェクトのスコアと日時を取得
        all_projects = conn.execute(
            "SELECT id, quality_score, created_at FROM projects "
            "WHERE quality_score IS NOT NULL ORDER BY created_at ASC"
        ).fetchall()

        # カテゴリ別のフィードバック数を取得
        fb_counts = conn.execute(
            "SELECT category, COUNT(*) as cnt FROM feedbacks "
            "WHERE category IS NOT NULL GROUP BY category"
        ).fetchall()
        fb_count_map = {r["category"]: r["cnt"] for r in fb_counts}

        conn.close()

        effects = []
        for rule in rules:
            if not rule.get("is_active", True):
                continue

            rule_created = rule.get("created_at", "")
            category = rule.get("category", "")

            # ルール作成前後のスコアを分類
            before_scores = []
            after_scores = []
            for p in all_projects:
                if p["created_at"] and rule_created:
                    if p["created_at"] < rule_created:
                        before_scores.append(p["quality_score"])
                    else:
                        after_scores.append(p["quality_score"])

            avg_before = round(sum(before_scores) / len(before_scores), 1) if before_scores else None
            avg_after = round(sum(after_scores) / len(after_scores), 1) if after_scores else None

            effect_delta = None
            if avg_before is not None and avg_after is not None:
                effect_delta = round(avg_after - avg_before, 1)

            effects.append({
                "rule_id": rule.get("id", ""),
                "rule_text": rule.get("rule_text", ""),
                "category": category,
                "priority": rule.get("priority", "medium"),
                "applied_count": rule.get("applied_count", 0),
                "related_feedback_count": fb_count_map.get(category, 0),
                "avg_score_before": avg_before,
                "avg_score_after": avg_after,
                "effect_delta": effect_delta,
            })

        # 適用回数降順でソート
        effects.sort(key=lambda e: e["applied_count"], reverse=True)

        self._set_cached(cache_key, effects)
        return effects

    # ------------------------------------------------------------------
    # 改善率統計
    # ------------------------------------------------------------------

    def get_improvement_stats(self) -> dict:
        """改善率の統計を算出

        shoot_date順にスコアを並べ、移動平均的な改善傾向を算出する。
        """
        cache_key = "improvement_stats"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        conn = self._get_db()
        rows = conn.execute(
            "SELECT quality_score, shoot_date FROM projects "
            "WHERE quality_score IS NOT NULL "
            "ORDER BY shoot_date ASC"
        ).fetchall()
        conn.close()

        scores = [r["quality_score"] for r in rows]

        if not scores:
            result = {
                "total_projects": 0,
                "overall_trend": "no_data",
                "first_half_avg": None,
                "second_half_avg": None,
                "overall_delta": None,
                "best_score": None,
                "worst_score": None,
                "score_range": None,
            }
            self._set_cached(cache_key, result)
            return result

        mid = len(scores) // 2
        first_half = scores[:mid] if mid > 0 else scores
        second_half = scores[mid:] if mid > 0 else []

        first_avg = round(sum(first_half) / len(first_half), 1) if first_half else None
        second_avg = round(sum(second_half) / len(second_half), 1) if second_half else None

        overall_delta = None
        overall_trend = "stable"
        if first_avg is not None and second_avg is not None:
            overall_delta = round(second_avg - first_avg, 1)
            if overall_delta > 3:
                overall_trend = "improving"
            elif overall_delta < -3:
                overall_trend = "declining"

        result = {
            "total_projects": len(scores),
            "overall_trend": overall_trend,
            "first_half_avg": first_avg,
            "second_half_avg": second_avg,
            "overall_delta": overall_delta,
            "best_score": max(scores),
            "worst_score": min(scores),
            "score_range": max(scores) - min(scores),
        }

        self._set_cached(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # 月別平均スコア
    # ------------------------------------------------------------------

    def get_monthly_averages(self) -> list[dict]:
        """月別の平均品質スコアを算出"""
        cache_key = "monthly_averages"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        conn = self._get_db()
        rows = conn.execute(
            "SELECT shoot_date, quality_score FROM projects "
            "WHERE quality_score IS NOT NULL AND shoot_date IS NOT NULL "
            "ORDER BY shoot_date ASC"
        ).fetchall()
        conn.close()

        # 月別に集計
        monthly: dict[str, list[int]] = defaultdict(list)
        for r in rows:
            date_str = r["shoot_date"] or ""
            # YYYY-MM形式に変換
            if len(date_str) >= 7:
                month_key = date_str[:7]  # "YYYY-MM"
            elif len(date_str) >= 4:
                month_key = date_str[:4] + "-01"
            else:
                continue
            monthly[month_key].append(r["quality_score"])

        result = []
        for month, month_scores in sorted(monthly.items()):
            avg = round(sum(month_scores) / len(month_scores), 1)
            result.append({
                "month": month,
                "average_score": avg,
                "count": len(month_scores),
                "min_score": min(month_scores),
                "max_score": max(month_scores),
            })

        self._set_cached(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # 総合統計取得
    # ------------------------------------------------------------------

    def get_full_stats(self) -> dict:
        """品質統計の全体結果を一括取得"""
        cache_key = "full_stats"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        conn = self._get_db()

        # 基本統計
        total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        scored_rows = conn.execute(
            "SELECT quality_score FROM projects WHERE quality_score IS NOT NULL"
        ).fetchall()
        conn.close()

        scores = [r["quality_score"] for r in scored_rows]

        # 基本統計量
        avg_score = None
        median_score = None
        std_dev = None
        grade_dist: dict[str, int] = {g: 0 for _, g in _GRADE_BOUNDARIES}

        if scores:
            avg_score = round(sum(scores) / len(scores), 1)

            # 中央値
            sorted_scores = sorted(scores)
            n = len(sorted_scores)
            if n % 2 == 0:
                median_score = round((sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2, 1)
            else:
                median_score = float(sorted_scores[n // 2])

            # 標準偏差
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std_dev = round(variance ** 0.5, 1)

            # グレード分布
            for s in scores:
                g = _grade_from_score(s)
                grade_dist[g] = grade_dist.get(g, 0) + 1

        result = {
            "total_projects": total,
            "scored_projects": len(scores),
            "average_score": avg_score,
            "median_score": median_score,
            "score_std_dev": std_dev,
            "grade_distribution": grade_dist,
            "project_trends": self.get_project_trends(),
            "category_ranking": self.get_category_problem_ranking(),
            "editor_profiles": self.get_editor_quality_profiles(),
            "learning_rule_effects": self.get_learning_rule_effects(),
            "improvement_stats": self.get_improvement_stats(),
            "monthly_averages": self.get_monthly_averages(),
            "generated_at": datetime.now().isoformat(),
        }

        self._set_cached(cache_key, result)
        return result
