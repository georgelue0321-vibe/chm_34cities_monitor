import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from china_housing_monitor.scoring.factors import compute_and_store_weekly_scores

FEATURE_START = "2026-08-10"


def current_week_start():
    today = datetime.now()
    return (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")


def test_weekly_scores_remove_pre_feature_history():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE bottom_score_monthly (
            city_id TEXT,
            month TEXT,
            score_final REAL,
            factor_price REAL,
            factor_policy REAL,
            pboc_score REAL
        );
        CREATE TABLE storage_execution_events (
            city_id TEXT,
            event_stage TEXT,
            event_date TEXT,
            is_score_eligible INTEGER
        );
        CREATE TABLE weekly_bottom_score (
            city_id TEXT,
            week_start TEXT,
            score REAL,
            data_source TEXT,
            calculated_at TEXT,
            PRIMARY KEY (city_id, week_start)
        );
        """
    )
    conn.execute(
        "INSERT INTO bottom_score_monthly VALUES (?, ?, ?, ?, ?, ?)",
        ("bj", "2026-06", 59.0, 55.0, 10.0, 30.0),
    )
    conn.execute(
        "INSERT INTO weekly_bottom_score VALUES (?, ?, ?, ?, ?)",
        ("bj", "2026-03-16", 47.6, "monthly_carryover", "2026-08-14T11:55:30"),
    )
    conn.commit()

    compute_and_store_weekly_scores(conn)

    rows = conn.execute(
        "SELECT week_start FROM weekly_bottom_score WHERE city_id = ? ORDER BY week_start",
        ("bj",),
    ).fetchall()
    week_starts = [row[0] for row in rows]
    assert all(week >= FEATURE_START for week in week_starts)
    assert current_week_start() in week_starts
    conn.close()


if __name__ == "__main__":
    test_weekly_scores_remove_pre_feature_history()
    print("PASS: pre-feature weekly history is removed")
