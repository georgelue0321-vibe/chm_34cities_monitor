"""Probe official sources without writing transaction data to SQLite."""

import argparse
import json
import re
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import CORE_CITIES


BEIJING_SOURCE = "http://bjjs.zjw.beijing.gov.cn/eportal/ui?pageId=53610668"
OFFICIAL_PORTALS = {
    "bj": BEIJING_SOURCE, "sh": "https://www.fangdi.com.cn/", "sz": "https://zjj.sz.gov.cn/",
    "gz": "https://zfcj.gz.gov.cn/", "cd": "https://cdzj.chengdu.gov.cn/",
    "cq": "https://zfcxjw.cq.gov.cn/", "hz": "https://www.tmsf.com/",
    "wh": "https://zgj.wuhan.gov.cn/", "xa": "http://zjj.xa.gov.cn/",
    "nj": "https://www.njhouse.com.cn/", "tj": "https://zfcxjs.tj.gov.cn/",
    "cs": "http://zjw.changsha.gov.cn/", "hf": "https://fcj.hefei.gov.cn/",
    "zz": "https://zfbzj.zhengzhou.gov.cn/", "xm": "https://szjj.xm.gov.cn/",
    "qd": "https://sjw.qingdao.gov.cn/", "nb": "https://zjj.ningbo.gov.cn/",
    "fz": "https://zjj.fuzhou.gov.cn/", "sjz": "http://zjj.sjz.gov.cn/",
    "ty": "https://zjj.taiyuan.gov.cn/", "hhht": "https://zjj.huhhot.gov.cn/",
    "sy": "https://fcj.shenyang.gov.cn/", "cc": "http://zjj.changchun.gov.cn/",
    "heb": "https://zjj.harbin.gov.cn/", "nc": "https://zjj.nc.gov.cn/",
    "jn": "https://jncc.jinan.gov.cn/jnfdcinfo/jnfdcweb/", "nn": "https://zjj.nanning.gov.cn/",
    "hk": "https://zjj.haikou.gov.cn/", "gy": "https://zjj.guiyang.gov.cn/",
    "km": "http://zjj.km.gov.cn/", "lz": "http://zjj.lanzhou.gov.cn/",
    "xn": "https://zjj.xining.gov.cn/", "yc": "https://zjj.yinchuan.gov.cn/",
    "wlmq": "https://www.wlmq.gov.cn/",
}


def evaluate_candidate(city_id, month, source_url, page_text):
    """Accept only a monthly residential resale value with explicit evidence."""
    year, month_number = month.split("-", 1)
    month_label = f"{year}年{int(month_number)}月"
    visible_text = re.sub(r"<[^>]+>", " ", page_text)
    units_match = re.search(r"住宅签约套数：?\s*([0-9,]+)", visible_text)
    is_resale = "存量房" in visible_text or "二手住宅" in visible_text
    is_month = month_label in visible_text
    eligible = bool(units_match and is_resale and is_month)
    return {
        "city_id": city_id,
        "month": month,
        "source_url": source_url,
        "units": int(units_match.group(1).replace(",", "")) if eligible else None,
        "status": "eligible" if eligible else "rejected",
        "reason": "" if eligible else "未同时确认上月、二手住宅和月度套数口径",
    }


def fetch_page(url):
    request = Request(url, headers={"User-Agent": "CHM official-data audit/1.0"})
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def probe_city_http(city_id, month, fetcher=fetch_page):
    """Perform one real HTTP attempt; missing source progresses to browser stage."""
    source_url = OFFICIAL_PORTALS[city_id]
    try:
        result = evaluate_candidate(city_id, month, source_url, fetcher(source_url))
        result["city_name"] = CORE_CITIES[city_id]["name"]
        result["attempts"] = [{"method": "python_http", "result": result["status"]}]
        if result["status"] != "eligible":
            result["status"] = "browser_pending"
            result["reason"] = "官方门户已实际请求，但当前页未提供合格月度二手住宅数据"
        return result
    except (HTTPError, URLError, TimeoutError) as error:
        return {
            "city_id": city_id,
            "city_name": CORE_CITIES[city_id]["name"],
            "month": month,
            "status": "browser_pending",
            "units": None,
            "attempts": [{"method": "python_http", "result": "request_failed", "detail": str(error)}],
        }


def write_audit(records, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_http_probe(month, output_dir, fetcher=fetch_page):
    records = [probe_city_http(city_id, month, fetcher) for city_id in CORE_CITIES]
    write_audit(records, Path(output_dir) / "availability.json")
    return records


def previous_month(today=None):
    today = today or date.today()
    first_day = today.replace(day=1)
    return (first_day.replace(day=1).fromordinal(first_day.toordinal() - 1)).strftime("%Y-%m")


def main():
    parser = argparse.ArgumentParser(description="Audit official resale transaction availability")
    parser.add_argument("--month", default=previous_month())
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    records = run_http_probe(args.month, args.output_dir)
    eligible = sum(record["status"] == "eligible" for record in records)
    print(f"HTTP audit complete: {len(records)} cities, {eligible} eligible")


if __name__ == "__main__":
    main()
