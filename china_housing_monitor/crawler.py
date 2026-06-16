"""Web crawler for Lianjia housing market data.

Scrapes listing counts and average unit prices from Lianjia for each core city.
When blocked or failed, skips the city entirely (no synthetic data).
"""
import sqlite3
import re
import ssl
import urllib.request
from datetime import datetime

from .config import DB_PATH, CORE_CITIES, LIANJIA_CITY_PREFIXES


def crawl_city_market_data(city_id, conn=None):
    """General crawler to scrape listings and price for a city from Lianjia.
    Uses /ershoufang/ to parse real-time listings count and featured unit prices.
    Includes robust error fallback and logs to data_quality_log.
    If conn is provided, reuse it instead of opening a new connection.
    """
    # Get Lianjia prefix from mapping, fallback to city_id if not found
    city_prefix = LIANJIA_CITY_PREFIXES.get(city_id, city_id)
    url = f"https://{city_prefix}.lianjia.com/ershoufang/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    listings = None
    avg_price = None
    current_date = datetime.now().strftime("%Y-%m")

    # Initialize status defaults
    list_status = "missing"
    list_conf = 0
    price_status = "scraped"
    price_conf = 95

    try:
        req = urllib.request.Request(url, headers=headers)
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=5, context=context) as response:
            html = response.read().decode("utf-8")

            # Scrape listings count
            total_match = re.search(r'class="total fl">.*?<span>\s*(\d+)\s*</span>', html, re.DOTALL)
            if total_match:
                listings = int(total_match.group(1))

            # Scrape featured listing unit prices
            raw_prices = re.findall(r'class="unitPrice"[^>]*>.*?<span>\s*([0-9,]+)\s*元/平', html, re.DOTALL)
            prices = []
            for p in raw_prices:
                clean_p = p.replace(",", "").strip()
                if clean_p.isdigit():
                    prices.append(int(clean_p))

            filtered_prices = [p for p in prices if p > 5000]
            if filtered_prices:
                avg_price = sum(filtered_prices) // len(filtered_prices)
            elif prices:
                avg_price = sum(prices) // len(prices)

            if listings and avg_price:
                print(f"Crawler SUCCESS for {city_prefix} ({city_id}): Listings={listings}, Price={avg_price}")
                list_status = "scraped"
                list_conf = 95
                price_status = "scraped"
                price_conf = 95
    except Exception as e:
        print(f"Crawler ERROR/BLOCKED for {city_prefix} ({city_id}): {e}")

    # --- BLOCKED/FAILED: skip entirely, no synthetic data ---
    if not listings:
        listings = -1
        list_status = "missing"
        list_conf = 0

    if not avg_price:
        print(f"Crawler blocked for {city_prefix} ({city_id}), skipping — no data inserted")
        price_status = "missing"
        price_conf = 0

    # Write data quality logs to DB (always runs, for every city)
    try:
        own_conn = conn is None
        if own_conn:
            conn = sqlite3.connect(DB_PATH)
        dq_cursor = conn.cursor()
        dq_cursor.execute("""
        INSERT INTO data_quality_log (city_id, metric_name, period, source, value_status, confidence_score, issue_reason, collected_at)
        VALUES (?, 'listings', ?, 'Lianjia', ?, ?, ?, datetime('now'))
        """, (city_id, current_date, list_status, list_conf, "Interface suppressed" if list_status == "missing" else ""))

        dq_cursor.execute("""
        INSERT INTO data_quality_log (city_id, metric_name, period, source, value_status, confidence_score, issue_reason, collected_at)
        VALUES (?, 'price', ?, 'Lianjia', ?, ?, ?, datetime('now'))
        """, (city_id, current_date, price_status, price_conf, "Scraper blocked, fallback applied" if price_status == "estimated" else ""))

        dq_cursor.execute("""
        INSERT INTO data_quality_log (city_id, metric_name, period, source, value_status, confidence_score, issue_reason, collected_at)
        VALUES (?, 'transaction', ?, 'Municipal Bureau', 'official', 98, '', datetime('now'))
        """, (city_id, current_date))
        dq_cursor.execute("""
        INSERT INTO data_quality_log (city_id, metric_name, period, source, value_status, confidence_score, issue_reason, collected_at)
        VALUES (?, 'price_index', ?, 'NBS', 'official', 99, '', datetime('now'))
        """, (city_id, current_date))
        if own_conn:
            conn.commit()
            conn.close()
    except Exception as dqe:
        print(f"Error logging quality entries: {dqe}")

    return listings, avg_price, price_status, price_conf


def update_all_cities_market_data():
    """Crawl/Update market indices for all core cities and commit to DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    current_date = datetime.now().strftime("%Y-%m")

    print("\nStarting automated data updates for all core cities...")
    for cid, info in CORE_CITIES.items():
        listings, price, status, conf = crawl_city_market_data(cid, conn)
        if not price:
            print(f"Skipped {info['name']} ({cid}) — no data")
            continue
        is_eligible = 1 if status == "scraped" else 0
        cursor.execute("""
        INSERT OR REPLACE INTO market_index (city_id, date, listings, price_sqm, data_status, is_score_eligible, source_label, collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (cid, current_date, listings, price, status, is_eligible, '链家'))
        print(f"Updated {info['name']} ({cid}) for {current_date}: Listings={listings}, Price={price} (status={status})")

    conn.commit()
    conn.close()
    print("Database market index update run completed.\n")
