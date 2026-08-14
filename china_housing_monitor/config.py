"""Configuration module for China Housing Monitor.

Contains all constants, paths, city definitions, scoring parameters,
and shared utility functions used across the application.
"""
import os

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(WORKSPACE, "china_monitor_db.sqlite")
REPORT_PATH = os.path.join(WORKSPACE, "chm.html")

# Selected 34 Core Cities (18 original + 16 provincial capitals)
CORE_CITIES = {
    # Original 18 cities
    "bj": {"name": "北京", "level": "一线", "quota": 15.0, "lat": 39.90, "lng": 116.40},
    "sh": {"name": "上海", "level": "一线", "quota": 15.0, "lat": 31.23, "lng": 121.47},
    "sz": {"name": "深圳", "level": "一线", "quota": 10.0, "lat": 22.54, "lng": 114.06},
    "gz": {"name": "广州", "level": "一线", "quota": 10.0, "lat": 23.13, "lng": 113.26},
    "cd": {"name": "成都", "level": "新一线", "quota": 12.0, "lat": 30.57, "lng": 104.07},
    "cq": {"name": "重庆", "level": "新一线", "quota": 12.0, "lat": 29.56, "lng": 106.55},
    "hz": {"name": "杭州", "level": "新一线", "quota": 8.0, "lat": 30.27, "lng": 120.15},
    "wh": {"name": "武汉", "level": "新一线", "quota": 8.0, "lat": 30.59, "lng": 114.30},
    "xa": {"name": "西安", "level": "新一线", "quota": 6.0, "lat": 34.26, "lng": 108.94},
    "nj": {"name": "南京", "level": "新一线", "quota": 6.0, "lat": 32.06, "lng": 118.80},
    "tj": {"name": "天津", "level": "新一线", "quota": 5.0, "lat": 39.13, "lng": 117.20},
    "cs": {"name": "长沙", "level": "新一线", "quota": 5.0, "lat": 28.23, "lng": 112.94},
    "hf": {"name": "合肥", "level": "二线核心", "quota": 4.0, "lat": 31.82, "lng": 117.23},
    "zz": {"name": "郑州", "level": "二线核心", "quota": 4.0, "lat": 34.75, "lng": 113.65},
    "xm": {"name": "厦门", "level": "二线核心", "quota": 3.0, "lat": 24.48, "lng": 118.09},
    "qd": {"name": "青岛", "level": "二线核心", "quota": 3.0, "lat": 36.07, "lng": 120.38},
    "nb": {"name": "宁波", "level": "二线核心", "quota": 3.0, "lat": 29.87, "lng": 121.55},
    "fz": {"name": "福州", "level": "二线核心", "quota": 2.0, "lat": 26.07, "lng": 119.30},
    # New 16 provincial capitals (v0.8)
    "sjz": {"name": "石家庄", "level": "二线核心", "quota": 5.0, "lat": 38.04, "lng": 114.51},
    "ty": {"name": "太原", "level": "二线核心", "quota": 3.0, "lat": 37.87, "lng": 112.55},
    "hhht": {"name": "呼和浩特", "level": "二线核心", "quota": 2.0, "lat": 40.84, "lng": 111.75},
    "sy": {"name": "沈阳", "level": "二线核心", "quota": 5.0, "lat": 41.80, "lng": 123.43},
    "cc": {"name": "长春", "level": "二线核心", "quota": 3.0, "lat": 43.88, "lng": 125.32},
    "heb": {"name": "哈尔滨", "level": "二线核心", "quota": 3.0, "lat": 45.75, "lng": 126.65},
    "nc": {"name": "南昌", "level": "二线核心", "quota": 3.0, "lat": 28.68, "lng": 115.86},
    "jn": {"name": "济南", "level": "新一线", "quota": 5.0, "lat": 36.65, "lng": 116.99},
    "nn": {"name": "南宁", "level": "二线核心", "quota": 3.0, "lat": 22.82, "lng": 108.32},
    "hk": {"name": "海口", "level": "二线核心", "quota": 2.0, "lat": 20.02, "lng": 110.35},
    "gy": {"name": "贵阳", "level": "二线核心", "quota": 3.0, "lat": 26.65, "lng": 106.63},
    "km": {"name": "昆明", "level": "二线核心", "quota": 3.0, "lat": 25.04, "lng": 102.68},
    "lz": {"name": "兰州", "level": "二线核心", "quota": 2.0, "lat": 36.06, "lng": 103.83},
    "xn": {"name": "西宁", "level": "二线核心", "quota": 2.0, "lat": 36.62, "lng": 101.78},
    "yc": {"name": "银川", "level": "二线核心", "quota": 2.0, "lat": 38.49, "lng": 106.23},
    "wlmq": {"name": "乌鲁木齐", "level": "二线核心", "quota": 2.0, "lat": 43.80, "lng": 87.60},
}

# Lianjia city prefix mapping for web scraping
LIANJIA_CITY_PREFIXES = {
    "bj": "beijing", "sh": "shanghai", "sz": "shenzhen", "gz": "guangzhou",
    "cd": "chengdu", "cq": "chongqing", "hz": "hangzhou", "wh": "wuhan",
    "xa": "xian", "nj": "nanjing", "tj": "tianjin", "cs": "changsha",
    "hf": "hefei", "zz": "zhengzhou", "xm": "xiamen", "qd": "qingdao",
    "nb": "ningbo", "fz": "fuzhou",
    # New 16 cities (v0.8)
    "sjz": "shijiazhuang", "ty": "taiyuan", "hhht": "huhehaote",
    "sy": "shenyang", "cc": "changchun", "heb": "haerbin",
    "nc": "nanchang", "jn": "jinan", "nn": "nanning",
    "hk": "haikou", "gy": "guiyang", "km": "kunming",
    "lz": "lanzhou", "xn": "xining", "yc": "yinchuan",
    "wlmq": "wulumuqi"
}

# Low-Data Mode Constants
BSS_LOW_DATA_V1 = {
    "mode": "low_data",
    "version": "BSS_LOW_DATA_V1",
    "formula": "0.60*S_Price + 0.30*S_Storage + 0.10*S_PBOC",
    "factors": ["price", "storage", "pboc"],
    "gates": ["transaction", "listing", "inventory"]
}

PBOC_SCORE_MAP = [
    (10, 20),
    (25, 40),
    (40, 55),
    (60, 70),
    (80, 85),
    (100, 95),
]
PBOC_STALE_CAP = 30
PBOC_STALE_MONTHS_THRESHOLD = 6

# Weekly scores only became observable from the first collection week.
WEEKLY_SCORE_HISTORY_START = "2026-08-10"

DATA_STATUS_LABELS = {
    "official": "官方发布",
    "scraped": "爬取",
    "synthetic": "算法回退",
    "extrapolated": "推算",
    "missing": "缺失"
}


def compute_event_hash(city_id, event_date, event_stage, title):
    """Compute a deterministic hash for storage execution events."""
    import hashlib
    hash_str = f"{city_id}_{event_date}_{event_stage}_{title}"
    return hashlib.md5(hash_str.encode('utf-8')).hexdigest()
