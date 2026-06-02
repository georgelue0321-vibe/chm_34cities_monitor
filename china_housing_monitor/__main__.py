"""
CLI entry point for China Housing Monitor.

Usage:
    python -m china_housing_monitor              # Full pipeline: init DB, scrape, generate HTML
    python -m china_housing_monitor --no-scrape  # Skip scraping, just regenerate HTML from existing DB
    python -m china_housing_monitor --init-only  # Only initialize/seed the database
"""

import argparse
import sys

from .config import DB_PATH, REPORT_PATH
from .db.init import init_db
from .crawler import update_all_cities_market_data
from .report.generator import generate_html_report


def main():
    parser = argparse.ArgumentParser(description="China Housing Monitor - Property Bottom Signal Terminal")
    parser.add_argument("--no-scrape", action="store_true", help="Skip web scraping, regenerate HTML from existing DB")
    parser.add_argument("--init-only", action="store_true", help="Only initialize/seed the database")
    parser.add_argument("--month", type=str, default=None, help="Target month in YYYY-MM format")
    args = parser.parse_args()

    print("=" * 60)
    print("China Housing Monitor (CHM) v2.0.0")
    print("=" * 60)

    # Step 1: Initialize database
    print("\n[1/3] Initializing database...")
    init_db()

    if args.init_only:
        print("\nDatabase initialized. Exiting (--init-only).")
        return

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
