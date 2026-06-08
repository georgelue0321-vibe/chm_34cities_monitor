#!/usr/bin/env python3
"""Tests for CHM-specific storage scanner/importer contracts."""

import os
import sqlite3
import subprocess
import sys
import tempfile


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(os.path.dirname(SKILL_DIR))
SCRIPTS_DIR = os.path.join(SKILL_DIR, "scripts")

sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, SCRIPTS_DIR)

from china_housing_monitor.config import CORE_CITIES, compute_event_hash
import scanner
from db_importer import DBImporter, normalize_event
from stage_classifier import StageClassifier


def test_scanner_uses_core_cities():
    assert scanner.CITIES == {city_id: meta["name"] for city_id, meta in CORE_CITIES.items()}
    assert "heb" in scanner.CITIES
    assert "hrb" not in scanner.CITIES
    print("✓ scanner city IDs come from CORE_CITIES")


def test_stable_url_filter():
    assert scanner.is_stable_final_url("https://zjj.example.gov.cn/article/1.html") is True
    assert scanner.is_stable_final_url("https://www.baidu.com/link?url=abc") is False
    assert scanner.is_stable_final_url("https://weixin.sogou.com/link?url=abc") is False
    print("✓ temporary redirect URLs are rejected as final evidence")


def test_stage_names_match_chm_scoring_contract():
    classifier = StageClassifier()
    stage, weight = classifier.classify("项目已竣工并投入使用，进入配租阶段")
    assert stage == "改造完成/配租配售"
    assert weight == 100

    event = valid_reviewed_event()
    event["suggested_stage"] = "改造完成"
    normalized, errors = normalize_event(event)
    assert not errors
    assert normalized["event_stage"] == "改造完成/配租配售"
    print("✓ final completion stage matches CHM scoring contract")


def valid_reviewed_event():
    return {
        "approved": True,
        "city_id": "bj",
        "title": "北京市收购存量商品房用作保障性住房公告",
        "final_url": "https://zjw.beijing.gov.cn/article/20260603.html",
        "abstract": "北京市征集已建成存量商品房用作保障性住房。",
        "suggested_stage": "房源征集",
        "suggested_date": "2026-06-03",
        "source_reliability": 100,
        "confidence": 95,
    }


def test_importer_rejects_unapproved_and_redirects():
    event = valid_reviewed_event()
    event["approved"] = False
    normalized, errors = normalize_event(event)
    assert "candidate is not approved by agent review" in errors

    event = valid_reviewed_event()
    event["final_url"] = "https://www.baidu.com/link?url=abc"
    normalized, errors = normalize_event(event)
    assert any("stable final URL" in error for error in errors)
    assert normalized["is_score_eligible"] == 0
    print("✓ importer rejects unapproved events and search redirects")


def test_policy_statement_imports_but_never_scores():
    assert scanner.is_stage_score_eligible("政策表态") is False

    event = valid_reviewed_event()
    event["suggested_stage"] = "政策表态"
    normalized, errors = normalize_event(event)
    assert not errors
    assert normalized["event_stage"] == "政策表态"
    assert normalized["is_score_eligible"] == 0
    print("✓ policy statements can import but are not score eligible")


def test_importer_rejects_placeholder_dates():
    event = valid_reviewed_event()
    event["suggested_date"] = "2024-01-01"
    normalized, errors = normalize_event(event)
    assert any("placeholder" in error for error in errors)

    normalized, errors = normalize_event(event, allow_placeholder_dates=True)
    assert not errors
    print("✓ importer blocks placeholder dates unless explicitly allowed")


def test_importer_writes_event_and_quality_log():
    event, errors = normalize_event(valid_reviewed_event())
    assert not errors

    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE storage_execution_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id TEXT NOT NULL,
                district TEXT,
                event_date TEXT,
                event_stage TEXT,
                title TEXT,
                details TEXT,
                buyer_entity TEXT,
                seller_entity TEXT,
                project_name TEXT,
                units_planned INTEGER,
                units_acquired INTEGER,
                area_sqm_planned REAL,
                area_sqm_acquired REAL,
                acquisition_price_total REAL,
                acquisition_price_sqm REAL,
                local_resale_avg_price_sqm REAL,
                discount_to_market REAL,
                funding_type TEXT,
                source_url TEXT,
                source_reliability INTEGER DEFAULT 80,
                collected_at TEXT,
                legacy_storage_event_id INTEGER,
                event_hash TEXT UNIQUE,
                data_status TEXT,
                confidence_score INTEGER,
                is_score_eligible INTEGER,
                methodology_note TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE data_quality_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id TEXT,
                metric_name TEXT,
                period TEXT,
                source TEXT,
                value_status TEXT,
                confidence_score INTEGER,
                issue_reason TEXT,
                collected_at TEXT,
                data_status TEXT,
                is_score_eligible INTEGER,
                methodology_note TEXT
            )
        """)
        conn.commit()
        conn.close()

        importer = DBImporter(db_path)
        assert importer.insert_event(event) is True
        assert importer.insert_event(event) is False

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT event_hash FROM storage_execution_events")
        assert cursor.fetchone()[0] == compute_event_hash("bj", "2026-06-03", "房源征集", event["title"])
        cursor.execute("SELECT COUNT(*) FROM data_quality_log WHERE metric_name = 'storage'")
        assert cursor.fetchone()[0] == 1
        conn.close()
        print("✓ importer writes event and matching data_quality_log entry")
    finally:
        os.unlink(db_path)


def test_invalid_city_cli_fails_before_network():
    scanner_path = os.path.join(SCRIPTS_DIR, "scanner.py")
    result = subprocess.run(
        [sys.executable, scanner_path, "--city", "hrb"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert "Unknown city id: hrb" in result.stdout
    print("✓ invalid city ID fails before browser/network work")


if __name__ == "__main__":
    print("\nRunning CHM storage scanner contract tests...\n")
    test_scanner_uses_core_cities()
    test_stable_url_filter()
    test_stage_names_match_chm_scoring_contract()
    test_importer_rejects_unapproved_and_redirects()
    test_policy_statement_imports_but_never_scores()
    test_importer_rejects_placeholder_dates()
    test_importer_writes_event_and_quality_log()
    test_invalid_city_cli_fails_before_network()
    print("\nAll CHM contract tests passed.")
