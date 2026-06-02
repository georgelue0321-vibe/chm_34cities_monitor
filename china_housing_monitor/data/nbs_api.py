"""Fetch NBS 70-city housing price index from East Money API.

Replaces manual CSV import. Data source: National Bureau of Statistics via East Money.
API: https://datacenter-web.eastmoney.com/api/data/v1/get
"""
import json
import urllib.request
import urllib.parse
import ssl
import re
from datetime import datetime

# City name to city_id mapping (Chinese name -> our ID)
CITY_NAME_MAP = {
    "北京": "bj", "上海": "sh", "深圳": "sz", "广州": "gz",
    "成都": "cd", "重庆": "cq", "杭州": "hz", "武汉": "wh",
    "西安": "xa", "南京": "nj", "天津": "tj", "长沙": "cs",
    "合肥": "hf", "郑州": "zz", "厦门": "xm", "青岛": "qd",
    "宁波": "nb", "福州": "fz",
    # v0.8 new cities
    "石家庄": "sjz", "太原": "ty", "呼和浩特": "hhht",
    "沈阳": "sy", "长春": "cc", "哈尔滨": "heb",
    "南昌": "nc", "济南": "jn", "南宁": "nn",
    "海口": "hk", "贵阳": "gy", "昆明": "km",
    "兰州": "lz", "西宁": "xn", "银川": "yc", "乌鲁木齐": "wlmq",
}

API_BASE = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT_NAME = "RPT_ECONOMY_HOUSE_PRICE"
COLUMNS = "REPORT_DATE,CITY,FIRST_COMHOUSE_SEQUENTIAL,FIRST_COMHOUSE_SAME,SECOND_HOUSE_SEQUENTIAL,SECOND_HOUSE_SAME"


def fetch_price_index(months=36):
    """Fetch housing price index data from East Money API.
    
    Args:
        months: How many months of data to fetch (default 36 = 3 years)
        
    Returns:
        List of dicts with keys: city_id, city_name, month, new_home_mom, new_home_yoy, resale_home_mom, resale_home_yoy
    """
    ssl._create_unverified_context()
    
    all_records = []
    page = 1
    page_size = 50  # API max
    
    while True:
        params = {
            "reportName": REPORT_NAME,
            "columns": COLUMNS,
            "filter": "",
            "pageNumber": page,
            "pageSize": page_size,
            "sortColumns": "REPORT_DATE,CITY",
            "sortTypes": "-1,-1",
            "source": "WEB",
            "client": "WEB",
        }
        
        url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
        
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://data.eastmoney.com/",
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"  API error on page {page}: {e}")
            break
        
        if not data.get("success") or not data.get("result"):
            print(f"  API returned error: {data.get('message', 'unknown')}")
            break
        
        records = data["result"].get("data", [])
        if not records:
            break
        
        for rec in records:
            city_name = rec.get("CITY", "")
            city_id = CITY_NAME_MAP.get(city_name)
            
            if not city_id:
                continue  # Skip cities not in our coverage
            
            report_date = rec.get("REPORT_DATE", "")
            if not report_date:
                continue
            
            # Extract YYYY-MM from "2026-04-01 00:00:00"
            month_match = re.match(r"(\d{4}-\d{2})", report_date)
            if not month_match:
                continue
            month = month_match.group(1)
            
            all_records.append({
                "city_id": city_id,
                "city_name": city_name,
                "month": month,
                "new_home_mom": rec.get("FIRST_COMHOUSE_SEQUENTIAL"),
                "new_home_yoy": rec.get("FIRST_COMHOUSE_SAME"),
                "resale_home_mom": rec.get("SECOND_HOUSE_SEQUENTIAL"),
                "resale_home_yoy": rec.get("SECOND_HOUSE_SAME"),
            })
        
        # Check if we have enough data
        total_pages = data["result"].get("pages", 1)
        if page >= total_pages:
            break
        
        page += 1
        
        # Safety limit
        if page > 20:
            break
    
    # Filter to our cities only and deduplicate
    seen = set()
    filtered = []
    for rec in all_records:
        key = (rec["city_id"], rec["month"])
        if key not in seen:
            seen.add(key)
            filtered.append(rec)
    
    # Sort by city_id, month desc
    filtered.sort(key=lambda x: (x["city_id"], x["month"]), reverse=True)
    
    return filtered


def update_price_index_db(conn, records):
    """Insert or update price index records in the database.
    
    Args:
        conn: SQLite connection
        records: List of dicts from fetch_price_index()
        
    Returns:
        Tuple of (inserted_count, updated_count)
    """
    cursor = conn.cursor()
    inserted = 0
    updated = 0
    
    for rec in records:
        # Check if record exists
        cursor.execute(
            "SELECT new_home_mom, resale_home_mom FROM city_price_index_monthly WHERE city_id=? AND month=?",
            (rec["city_id"], rec["month"])
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update if values changed
            if (existing[0] != rec["new_home_mom"] or existing[1] != rec["resale_home_mom"]):
                cursor.execute("""
                    UPDATE city_price_index_monthly 
                    SET new_home_mom=?, new_home_yoy=?, resale_home_mom=?, resale_home_yoy=?,
                        source='EASTMONEY_API', collected_at=datetime('now')
                    WHERE city_id=? AND month=?
                """, (
                    rec["new_home_mom"], rec["new_home_yoy"],
                    rec["resale_home_mom"], rec["resale_home_yoy"],
                    rec["city_id"], rec["month"]
                ))
                updated += 1
        else:
            # Insert new record
            cursor.execute("""
                INSERT INTO city_price_index_monthly 
                (city_id, city_name, month, new_home_mom, new_home_yoy, resale_home_mom, resale_home_yoy,
                 source, source_url, collected_at, data_status, confidence_score, is_score_eligible)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'EASTMONEY_API', ?, datetime('now'), 'official', 95, 1)
            """, (
                rec["city_id"], rec["city_name"], rec["month"],
                rec["new_home_mom"], rec["new_home_yoy"],
                rec["resale_home_mom"], rec["resale_home_yoy"],
                "https://data.eastmoney.com/cjsj/newhouse.html"
            ))
            inserted += 1
    
    conn.commit()
    return inserted, updated


def fetch_and_update(conn):
    """Main entry point: fetch data from API and update database.
    
    Args:
        conn: SQLite connection
        
    Returns:
        Tuple of (inserted_count, updated_count, total_records)
    """
    print("Fetching NBS housing price index from East Money API...")
    records = fetch_price_index(months=36)
    print(f"  Fetched {len(records)} records from API")
    
    if not records:
        print("  No records fetched, skipping DB update")
        return 0, 0, 0
    
    # Show date range
    months = sorted(set(r["month"] for r in records))
    if months:
        print(f"  Date range: {months[-1]} to {months[0]}")
    
    # Count cities
    cities = sorted(set(r["city_id"] for r in records))
    print(f"  Cities: {len(cities)}")
    
    inserted, updated = update_price_index_db(conn, records)
    print(f"  DB update: {inserted} inserted, {updated} updated")
    
    return inserted, updated, len(records)


if __name__ == "__main__":
    # Test: fetch and print sample data
    records = fetch_price_index(months=3)
    for r in records[:10]:
        print(f"{r['city_id']} ({r['city_name']}) {r['month']}: "
              f"新房环比={r['new_home_mom']}, 二手房环比={r['resale_home_mom']}")
    print(f"... total {len(records)} records")
