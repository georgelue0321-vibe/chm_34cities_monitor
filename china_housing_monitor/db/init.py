"""Database initialization and migration module.

Handles database schema creation, table migrations, and initial data setup.
"""
import os
import sqlite3
import re
from datetime import datetime

from ..config import DB_PATH, CORE_CITIES, compute_event_hash


def backup_db():
    """Create a timestamped backup of the database before reset."""
    import shutil
    if not os.path.exists(DB_PATH):
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Database backed up to: {backup_path}")

def add_column_if_not_exists(cursor, table, column, col_type, default=None):
    """Add a column to a table if it does not already exist."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        default_clause = f" DEFAULT {default}" if default is not None else ""
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}")
        print(f"Migration: Added column {column} to {table}")

def init_db(force_reset=False):
    """Initialize SQLite database with non-destructive incremental migration."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if force_reset:
        backup_db()
        cursor.execute("DROP TABLE IF EXISTS market_index")
        cursor.execute("DROP TABLE IF EXISTS professional_opinions")
        cursor.execute("DROP TABLE IF EXISTS pboc_global")
        cursor.execute("DROP TABLE IF EXISTS cities")
        cursor.execute("DROP TABLE IF EXISTS city_price_index_monthly")
        cursor.execute("DROP TABLE IF EXISTS city_transaction_monthly")
        cursor.execute("DROP TABLE IF EXISTS storage_execution_events")
        cursor.execute("DROP TABLE IF EXISTS data_quality_log")
        cursor.execute("DROP TABLE IF EXISTS bottom_score_monthly")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cities (
        id VARCHAR(10) PRIMARY KEY,
        name VARCHAR(50) NOT NULL,
        level VARCHAR(20) NOT NULL,
        quota_billion REAL DEFAULT 0.0
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pboc_global (
        date VARCHAR(20) PRIMARY KEY,
        balance_billion REAL NOT NULL,
        percentage REAL NOT NULL,
        source VARCHAR(100),
        collected_at TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_index (
        city_id VARCHAR(10),
        date VARCHAR(20),
        listings INTEGER NOT NULL,
        price_sqm INTEGER NOT NULL,
        PRIMARY KEY (city_id, date),
        FOREIGN KEY (city_id) REFERENCES cities(id)
    )
    """)
    add_column_if_not_exists(cursor, "market_index", "data_status", "TEXT", "'scraped'")
    add_column_if_not_exists(cursor, "market_index", "is_score_eligible", "INTEGER", "1")
    add_column_if_not_exists(cursor, "market_index", "source_label", "TEXT", "'链家'")
    add_column_if_not_exists(cursor, "market_index", "collected_at", "TEXT")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS professional_opinions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_id VARCHAR(10),
        date VARCHAR(20) NOT NULL,
        institution VARCHAR(100) NOT NULL,
        opinion TEXT NOT NULL,
        consensus TEXT,
        FOREIGN KEY (city_id) REFERENCES cities(id),
        UNIQUE(city_id, institution)
    )
    """)
    add_column_if_not_exists(cursor, "professional_opinions", "collected_at", "TEXT")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS city_price_index_monthly (
        city_id VARCHAR(10) NOT NULL,
        city_name VARCHAR(50) NOT NULL,
        month VARCHAR(20) NOT NULL,
        new_home_mom REAL,
        new_home_yoy REAL,
        resale_home_mom REAL,
        resale_home_yoy REAL,
        source TEXT DEFAULT 'EASTMONEY_API',
        source_url TEXT,
        collected_at TEXT,
        data_status TEXT,
        confidence_score INTEGER,
        is_score_eligible INTEGER,
        methodology_note TEXT,
        PRIMARY KEY (city_id, month, source),
        FOREIGN KEY (city_id) REFERENCES cities(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS city_transaction_monthly (
        city_id VARCHAR(10) NOT NULL,
        month VARCHAR(20) NOT NULL,
        new_home_sales_area REAL,
        new_home_sales_units INTEGER,
        resale_sales_area REAL,
        resale_sales_units INTEGER,
        resale_online_sign_units INTEGER,
        source TEXT,
        source_url TEXT,
        confidence INTEGER DEFAULT 80,
        collected_at TEXT,
        data_status TEXT,
        confidence_score INTEGER,
        is_score_eligible INTEGER,
        methodology_note TEXT,
        PRIMARY KEY (city_id, month, source),
        FOREIGN KEY (city_id) REFERENCES cities(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS storage_execution_events (
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
        methodology_note TEXT,
        FOREIGN KEY (city_id) REFERENCES cities(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS data_quality_log (
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
        methodology_note TEXT,
        FOREIGN KEY (city_id) REFERENCES cities(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bottom_score_monthly (
        city_id TEXT NOT NULL,
        month TEXT NOT NULL,
        score_raw REAL,
        score_final REAL,
        status_raw TEXT,
        status_final TEXT,
        is_true_bottom_candidate INTEGER,
        cap_reason TEXT,
        positive_drivers TEXT,
        negative_drivers TEXT,
        explanation TEXT,
        factor_policy REAL,
        factor_supply REAL,
        factor_demand REAL,
        factor_price REAL,
        factor_quality REAL,
        data_status TEXT,
        confidence_score INTEGER,
        is_score_eligible INTEGER,
        methodology_note TEXT,
        validation_status TEXT,
        validation_reason TEXT,
        transaction_validation TEXT,
        supply_validation TEXT,
        storage_validation TEXT,
        price_validation TEXT,
        PRIMARY KEY (city_id, month),
        FOREIGN KEY (city_id) REFERENCES cities(id)
    )
    """)
    
    add_column_if_not_exists(cursor, "bottom_score_monthly", "scoring_mode", "TEXT", "'low_data'")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "scoring_formula_version", "TEXT", "'BSS_LOW_DATA_V1'")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "formula_disclosure", "TEXT", "'0.60*S_Price + 0.30*S_Storage + 0.10*S_PBOC'")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "pboc_score", "INTEGER")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "pboc_pct", "REAL")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "pboc_stale_months", "INTEGER")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "pboc_is_stale", "INTEGER", "0")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "pboc_data_status", "TEXT")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "city_qualification", "TEXT", "'scored'")
    add_column_if_not_exists(cursor, "bottom_score_monthly", "calculated_at", "TEXT")
    
    conn.commit()
    
    for cid, info in CORE_CITIES.items():
        cursor.execute("INSERT OR IGNORE INTO cities VALUES (?, ?, ?, ?)", (cid, info["name"], info["level"], info["quota"]))
    
    # Remove cities that are no longer in CORE_CITIES (e.g., su/dg removed in RC5)
    cursor.execute("SELECT id FROM cities")
    for (cid,) in cursor.fetchall():
        if cid not in CORE_CITIES:
            cursor.execute("DELETE FROM cities WHERE id = ?", (cid,))
    
    pboc_history = [
        ("2024-05-17", 0.0, 0.0, "央行设立公告", "2024-05-17 00:00:00"),
        ("2024-06-30", 12.1, 4.03, "央行二季度结构性货币政策工具披露", "2024-06-30 00:00:00"),
        ("2024-09-30", 16.2, 5.4, "央行三季度货币政策执行报告披露", "2024-09-30 00:00:00")
    ]
    cursor.executemany("INSERT OR IGNORE INTO pboc_global (date, balance_billion, percentage, source, collected_at) VALUES (?, ?, ?, ?, ?)", pboc_history)
    conn.commit()

    try:
        cursor.execute("SELECT type FROM sqlite_master WHERE name='storage_events'")
        row = cursor.fetchone()
        if row and row[0] == 'table':
            cursor.execute("SELECT rowid, city_id, date, district, title, details, price_info, status, source_url FROM storage_events")
            old_storage_rows = cursor.fetchall()
            if old_storage_rows:
                print(f"Migrating {len(old_storage_rows)} historical storage events safely...")
                for r_id, cid, ev_date, district, title, details, price_info, status, source_url in old_storage_rows:
                    discount = 0.0
                    discount_match = re.search(r'(\d+(\.\d+)?)', price_info)
                    if discount_match:
                        try:
                            discount = float(discount_match.group(1))
                            if discount > 1.0: discount /= 10.0
                        except: pass
                    ev_hash = compute_event_hash(cid, ev_date, status, title)
                    cursor.execute("""
                    INSERT OR IGNORE INTO storage_execution_events (
                        city_id, district, event_date, event_stage, title, details, buyer_entity, seller_entity, 
                        project_name, units_planned, units_acquired, area_sqm_planned, area_sqm_acquired, 
                        acquisition_price_total, acquisition_price_sqm, local_resale_avg_price_sqm, discount_to_market, 
                        funding_type, source_url, source_reliability, collected_at, legacy_storage_event_id, event_hash,
                        data_status, confidence_score, is_score_eligible, methodology_note
                    ) VALUES (?, ?, ?, ?, ?, ?, '历史迁移收购方', '历史迁移出让方', '历史统筹收储区', 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, ?, ?, ?, 90, datetime('now'), ?, ?,
                               'official', 90, 1, '旧表平滑迁移数据')
                    """, (cid, district, ev_date, status, title, details, discount, '保障房再贷款' if '再贷款' in price_info else '历史收储资金', source_url, r_id, ev_hash))
                conn.commit()
                print('Data migration completed successfully!')
    except Exception as me:
        print(f"Migration warning: {me}")

    url_fixes = {
        'http://www.cq.gov.cn/ywdt/zwyw/202402/t20240206_12879555.html': 'https://mp.weixin.qq.com/s/lTyOpzM426MXBa_ajnNZMw',
        'http://www.gz.gov.cn/ywpd/cxjs/content/post_9678125.html': 'https://mp.weixin.qq.com/s/UUs9yiLO3rIs_P6q2VsSXA',
        'https://www.sz.gov.cn/cn/xxgk/zfxxgj/tzgg/content/post_11477757.html': 'https://www.sz.gov.cn/',
        'http://www.zhengzhou.gov.cn/tzgg/10928731.html': 'https://www.zhengzhou.gov.cn/',
        'http://fgj.fuzhou.gov.cn/': 'https://mp.weixin.qq.com/s/mCODpw-5GTPQtRZV-vEsEQ',
        'https://fgj.fuzhou.gov.cn/': 'https://mp.weixin.qq.com/s/mCODpw-5GTPQtRZV-vEsEQ',
        'https://cdzj.chengdu.gov.cn/': 'https://mp.weixin.qq.com/s/WphQnioGC0zAj5j5Gl9jRA',
    }
    fixed_count = 0
    for old_url, new_url in url_fixes.items():
        cursor.execute("UPDATE storage_execution_events SET source_url = ? WHERE source_url = ? AND source_url != ?",
                       (new_url, old_url, new_url))
        fixed_count += cursor.rowcount
    if fixed_count > 0:
        conn.commit()
        print(f'Fixed {fixed_count} migrated rows with corrected URLs.')

    new_fz_title = '福州左海集团收购首批存量现房用作保障性租赁住房项目签约'
    new_fz_hash = compute_event_hash('fz', '2024-07-10', '签约收购', new_fz_title)
    cursor.execute("SELECT event_hash FROM storage_execution_events WHERE event_hash = ?", (new_fz_hash,))
    if not cursor.fetchone():
        cursor.execute("""
        UPDATE storage_execution_events 
        SET event_hash = ?, title = ?, units_planned = 4768, units_acquired = 4768, 
            acquisition_price_total = 48800.0, local_resale_avg_price_sqm = 12000.0, discount_to_market = 0.55
        WHERE city_id = 'fz' AND title LIKE '%福州左海集团%'
        """, (new_fz_hash, new_fz_title))
    conn.commit()

    # Normalize market_index: listings=-1 should not be score eligible
    cursor.execute("""
    UPDATE market_index 
    SET is_score_eligible = 0 
    WHERE listings = -1 AND is_score_eligible = 1
    """)
    if cursor.rowcount > 0:
        print(f"Migration: Fixed {cursor.rowcount} records where listings=-1 but is_score_eligible=1")
    conn.commit()

    from .seed import seed_historical_data
    seed_historical_data(conn)
    
    conn.close()
