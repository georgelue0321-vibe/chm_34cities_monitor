#!/usr/bin/env python3
"""
Reviewed candidate importer for CHM storage execution events.

The importer is intentionally conservative:
- accepts only agent-reviewed candidates
- defaults to dry-run
- rejects temporary search redirect URLs
- writes storage_execution_events and data_quality_log together
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Tuple


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from china_housing_monitor.config import CORE_CITIES, DB_PATH, compute_event_hash


STAGE_ALIASES = {"改造完成": "改造完成/配租配售"}
VALID_STAGES = {"政策表态", "房源征集", "正式招标", "成交公示", "签约收购", "改造完成/配租配售"}
SCORE_ELIGIBLE_STAGES = {"房源征集", "正式招标", "成交公示", "签约收购", "改造完成/配租配售"}
REDIRECT_MARKERS = ("baidu.com/link", "weixin.sogou.com/link", "sogou.com/link", "antispider")
OFFICIAL_SOURCE_MARKERS = (
    ".gov.cn",
    "mp.weixin.qq.com",
    "xinhuanet.com",
    "people.com.cn",
    "cctv.com",
    "chinanews.com",
    "pbc.gov.cn",
)


def is_approved(event: Dict) -> bool:
    """Return whether an event has explicit review approval."""
    if event.get("approved") is True:
        return True
    review = event.get("review")
    return isinstance(review, dict) and review.get("status") == "approved"


def get_field(event: Dict, *keys, default=""):
    """Read a field from top-level event first, then chm_import."""
    nested = event.get("chm_import") if isinstance(event.get("chm_import"), dict) else {}
    for key in keys:
        value = event.get(key)
        if value not in (None, ""):
            return value
        value = nested.get(key)
        if value not in (None, ""):
            return value
    return default


def is_stable_source_url(url: str) -> bool:
    url_lower = (url or "").lower()
    return bool(url_lower) and not any(marker in url_lower for marker in REDIRECT_MARKERS)


def is_official_source_url(url: str) -> bool:
    url_lower = (url or "").lower()
    return any(marker in url_lower for marker in OFFICIAL_SOURCE_MARKERS)


def normalize_event(event: Dict, allow_placeholder_dates: bool = False) -> Tuple[Dict, List[str]]:
    """Normalize a reviewed candidate into storage_execution_events fields."""
    errors = []

    city_id = get_field(event, "city_id")
    event_date = get_field(event, "event_date", "suggested_date", "date")
    event_stage = get_field(event, "event_stage", "suggested_stage", "stage", default="政策表态")
    event_stage = STAGE_ALIASES.get(event_stage, event_stage)
    title = get_field(event, "title")
    source_url = get_field(event, "source_url", "final_url")

    if not is_approved(event):
        errors.append("candidate is not approved by agent review")
    if city_id not in CORE_CITIES:
        errors.append(f"unknown city_id: {city_id}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", event_date or ""):
        errors.append("event_date must be a confirmed YYYY-MM-DD date")
    if event_date == "2024-01-01" and not allow_placeholder_dates:
        errors.append("event_date looks like a placeholder; confirm the real article date first")
    if event_stage not in VALID_STAGES:
        errors.append(f"invalid event_stage: {event_stage}")
    if not title:
        errors.append("title is required")
    if not is_stable_source_url(source_url):
        errors.append("source_url must be a stable final URL, not a search redirect or antispider URL")
    if not is_official_source_url(source_url):
        errors.append("source_url is not an accepted CHM official/authoritative source")

    source_reliability = int(get_field(event, "source_reliability", "source_priority", default=80))
    confidence_score = int(get_field(event, "confidence_score", "confidence", default=source_reliability))
    requested_score_eligible = int(get_field(event, "is_score_eligible", default=1))
    is_score_eligible = requested_score_eligible if event_stage in SCORE_ELIGIBLE_STAGES else 0
    if errors:
        is_score_eligible = 0

    normalized = {
        "city_id": city_id,
        "district": get_field(event, "district", default="全市"),
        "event_date": event_date,
        "event_stage": event_stage,
        "title": title,
        "details": get_field(event, "details", "abstract"),
        "buyer_entity": get_field(event, "buyer_entity", "buyer"),
        "seller_entity": get_field(event, "seller_entity", "seller"),
        "project_name": get_field(event, "project_name", "project"),
        "units_planned": int(get_field(event, "units_planned", default=0) or 0),
        "units_acquired": int(get_field(event, "units_acquired", default=0) or 0),
        "area_sqm_planned": float(get_field(event, "area_sqm_planned", "area_planned", default=0.0) or 0.0),
        "area_sqm_acquired": float(get_field(event, "area_sqm_acquired", "area_acquired", default=0.0) or 0.0),
        "acquisition_price_total": float(get_field(event, "acquisition_price_total", "price_total", default=0.0) or 0.0),
        "acquisition_price_sqm": float(get_field(event, "acquisition_price_sqm", "price_sqm", default=0.0) or 0.0),
        "local_resale_avg_price_sqm": float(get_field(event, "local_resale_avg_price_sqm", "resale_avg", default=0.0) or 0.0),
        "discount_to_market": float(get_field(event, "discount_to_market", "discount", default=0.0) or 0.0),
        "funding_type": get_field(event, "funding_type", default="保障房再贷款"),
        "source_url": source_url,
        "source_reliability": source_reliability,
        "data_status": get_field(event, "data_status", default="official"),
        "confidence_score": confidence_score,
        "is_score_eligible": is_score_eligible,
        "methodology_note": get_field(event, "methodology_note", default="storage-event-scanner reviewed import"),
    }
    normalized["event_hash"] = compute_event_hash(city_id, event_date, event_stage, title)
    return normalized, errors


class DBImporter:
    """Handles reviewed storage event imports."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def event_exists(self, event_hash: str, source_url: str = "") -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM storage_execution_events WHERE event_hash = ? OR source_url = ?",
            (event_hash, source_url),
        )
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def insert_event(self, event: Dict) -> bool:
        if self.event_exists(event["event_hash"], event["source_url"]):
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            collected_at = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO storage_execution_events (
                    city_id, district, event_date, event_stage, title, details,
                    buyer_entity, seller_entity, project_name,
                    units_planned, units_acquired, area_sqm_planned, area_sqm_acquired,
                    acquisition_price_total, acquisition_price_sqm, local_resale_avg_price_sqm,
                    discount_to_market, funding_type, source_url, source_reliability,
                    collected_at, event_hash, data_status, confidence_score,
                    is_score_eligible, methodology_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event["city_id"], event["district"], event["event_date"], event["event_stage"],
                event["title"], event["details"], event["buyer_entity"], event["seller_entity"],
                event["project_name"], event["units_planned"], event["units_acquired"],
                event["area_sqm_planned"], event["area_sqm_acquired"],
                event["acquisition_price_total"], event["acquisition_price_sqm"],
                event["local_resale_avg_price_sqm"], event["discount_to_market"],
                event["funding_type"], event["source_url"], event["source_reliability"],
                collected_at, event["event_hash"], event["data_status"],
                event["confidence_score"], event["is_score_eligible"], event["methodology_note"],
            ))
            cursor.execute("""
                INSERT INTO data_quality_log (
                    city_id, metric_name, period, source, value_status, confidence_score,
                    issue_reason, collected_at, data_status, is_score_eligible, methodology_note
                ) VALUES (?, 'storage', ?, ?, ?, ?, 'reviewed storage event import', ?, ?, ?, ?)
            """, (
                event["city_id"], event["event_date"], event["source_url"], event["data_status"],
                event["confidence_score"], collected_at, event["data_status"],
                event["is_score_eligible"], event["methodology_note"],
            ))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def import_events(self, events: List[Dict]) -> Tuple[int, int]:
        imported = 0
        skipped = 0
        for event in events:
            if self.insert_event(event):
                imported += 1
            else:
                skipped += 1
        return imported, skipped


def load_events(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("reviewed JSON must be a list of candidate objects")
    return data


def backup_db(db_path: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.storage_import_backup_{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def main():
    parser = argparse.ArgumentParser(description="Import reviewed CHM storage event candidates")
    parser.add_argument("reviewed_json", help="Path to reviewed candidates JSON")
    parser.add_argument("--db", default=DB_PATH, help="Path to china_monitor_db.sqlite")
    parser.add_argument("--commit", action="store_true", help="Actually write to DB. Default is dry-run.")
    parser.add_argument("--allow-placeholder-dates", action="store_true", help="Allow 2024-01-01 placeholder dates")
    args = parser.parse_args()

    raw_events = load_events(args.reviewed_json)
    accepted = []
    rejected = []
    for raw in raw_events:
        normalized, errors = normalize_event(raw, allow_placeholder_dates=args.allow_placeholder_dates)
        if errors:
            rejected.append({"title": normalized.get("title", ""), "errors": errors})
        else:
            accepted.append(normalized)

    print(f"Reviewed candidates: {len(raw_events)}")
    print(f"Accepted for import: {len(accepted)}")
    print(f"Rejected: {len(rejected)}")
    for item in rejected[:20]:
        print(f"  REJECT {item['title'][:80]} :: {'; '.join(item['errors'])}")

    if not args.commit:
        print("Dry-run only. Re-run with --commit to write accepted events.")
        return

    backup_path = backup_db(args.db)
    print(f"Database backup: {backup_path}")
    importer = DBImporter(args.db)
    imported, skipped = importer.import_events(accepted)
    print(f"Imported: {imported}, skipped existing: {skipped}")


if __name__ == "__main__":
    main()
