"""
CLI entry point for China Housing Monitor.

Usage:
    python -m china_housing_monitor              # Full pipeline: init DB, scrape, generate HTML
    python -m china_housing_monitor --no-scrape  # Skip scraping, just regenerate HTML from existing DB
    python -m china_housing_monitor --init-only  # Only initialize/seed the database
    python -m china_housing_monitor --fetch-nbs  # Fetch latest NBS price index from East Money API
"""

import argparse
import sqlite3
import sys

from . import __version__
from .config import DB_PATH, REPORT_PATH
from .db.init import init_db
from .crawler import update_all_cities_market_data
from .report.generator import generate_html_report


def main():
    parser = argparse.ArgumentParser(description="China Housing Monitor - Property Bottom Signal Terminal")
    parser.add_argument("--no-scrape", action="store_true", help="Skip web scraping, regenerate HTML from existing DB")
    parser.add_argument("--init-only", action="store_true", help="Only initialize/seed the database")
    parser.add_argument("--fetch-nbs", action="store_true", help="Fetch latest NBS price index from East Money API")
    parser.add_argument("--month", type=str, default=None, help="Target month in YYYY-MM format")
    args = parser.parse_args()

    print("=" * 60)
    print(f"China Housing Monitor (CHM) v{__version__}")
    print("=" * 60)

    # Step 1: Initialize database
    print("\n[1/3] Initializing database...")
    init_db()

    if args.init_only:
        print("\nDatabase initialized. Exiting (--init-only).")
        return

    # Step 1.5: Fetch NBS data from API (optional)
    if args.fetch_nbs:
        print("\n[1.5/3] Fetching NBS price index from East Money API...")
        from .data.nbs_api import fetch_and_update
        conn = sqlite3.connect(DB_PATH)
        try:
            inserted, updated, total = fetch_and_update(conn)
            print(f"  NBS data update complete: {total} records, {inserted} new, {updated} updated")
        finally:
            conn.close()

    # Step 2: Scrape market data
    if not args.no_scrape:
        print("\n[2/3] Scraping market data from Lianjia...")
        update_all_cities_market_data()
    else:
        print("\n[2/3] Skipping scraping (--no-scrape)")

    # Step 3: Generate HTML report
    print("\n[3/3] Generating HTML report...")
    generate_html_report()

    print("\n" + "=" * 60)
    print(f"Done! Open {REPORT_PATH} in your browser.")
    print("=" * 60)


if __name__ == "__main__":
    main()
