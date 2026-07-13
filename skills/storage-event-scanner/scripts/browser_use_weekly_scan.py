#!/usr/bin/env python3
"""Run headed browser-use search checks for CHM weekly storage evidence."""

import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote


PROJECT_DIR = Path(__file__).resolve().parents[3]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from china_housing_monitor.config import CORE_CITIES


RESULT_JS = r"""
JSON.stringify(Array.from(document.querySelectorAll('#content_left h3 a')).slice(0,8).map((a,i)=>{
  const box = a.closest('.c-container') || a.closest('[class*=result]') || a.parentElement;
  return {
    rank: i + 1,
    title: (a.innerText || a.textContent || '').trim(),
    href: a.href,
    text: ((box && box.innerText) || '').trim().slice(0, 800)
  };
}).filter(x => x.title))
"""

PAGE_JS = r"""
JSON.stringify({
  title: document.title,
  href: location.href,
  text: (document.body.innerText || '').trim().slice(0, 2200)
})
"""

SOGOU_JS = r"""
JSON.stringify(Array.from(document.querySelectorAll('.news-list li, .txt-box')).slice(0,8).map((el,i)=>{
  const a = el.querySelector('h3 a, a');
  return {
    rank: i + 1,
    title: a ? (a.innerText || a.textContent || '').trim() : '',
    href: a ? a.href : '',
    text: (el.innerText || '').trim().slice(0, 800)
  };
}).filter(x => x.title))
"""

OFFICIAL_MARKERS = (".gov.cn", "mp.weixin.qq.com", "people.com.cn", "xinhuanet.com", "cctv.com")
REJECT_MARKERS = ("baijiahao.baidu.com", "zhidao.baidu.com", "baidu.com/link", "antispider")
HEADED_SESSION_STARTED = False


def run_browser_use(args, timeout=45):
    command = ["browser-use", *args]
    try:
        proc = subprocess.run(
            command,
            cwd=PROJECT_DIR,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "returncode": 124,
            "stdout": "",
            "stderr": f"Timed out after {timeout}s",
            "command": command,
        }
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "command": command,
    }


def open_url(url):
    global HEADED_SESSION_STARTED
    if not HEADED_SESSION_STARTED:
        opened = run_browser_use(["--headed", "open", url])
        if opened["returncode"] == 0:
            HEADED_SESSION_STARTED = True
        return opened
    return run_browser_use(["eval", f"location.href = {json.dumps(url)}; 'navigated'"])


def parse_result(output):
    text = output.get("stdout", "")
    if text.startswith("result:"):
        text = text.split("result:", 1)[1].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": text[:1000]}


def parse_iso_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def previous_week_window(run_date):
    current = parse_iso_date(run_date)
    this_monday = current - timedelta(days=current.weekday())
    week_start = this_monday - timedelta(days=7)
    week_end = this_monday - timedelta(days=1)
    return week_start.isoformat(), week_end.isoformat()


def format_cn_window(start_date, end_date):
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    return f"{start.year}年{start.month}月{start.day}日 至 {end.month}月{end.day}日"


def build_storage_query(city_name, year, window_text, source):
    base = f"{city_name} 收购存量商品房 保障房 {year} 上周 {window_text}"
    if source == "baidu":
        return f"{base} 征集 通告 签约"
    return f"{base} 官方微信 征集"


def search_baidu(city_name, year, window_text):
    query = build_storage_query(city_name, year, window_text, "baidu")
    url = f"https://www.baidu.com/s?wd={quote(query)}"
    opened = open_url(url)
    time.sleep(1)
    evaluated = run_browser_use(["eval", RESULT_JS])
    return {
        "query": query,
        "url": url,
        "open": opened,
        "results": parse_result(evaluated),
    }


def search_sogou_weixin(city_name, year, window_text):
    query = build_storage_query(city_name, year, window_text, "sogou")
    url = f"https://weixin.sogou.com/weixin?type=2&query={quote(query)}"
    opened = open_url(url)
    time.sleep(1)
    evaluated = run_browser_use(["eval", SOGOU_JS])
    return {
        "query": query,
        "url": url,
        "open": opened,
        "results": parse_result(evaluated),
    }


def looks_relevant(item, city_name):
    text = f"{item.get('title', '')}\n{item.get('text', '')}"
    return city_name in text and "收购" in text and ("存量商品房" in text or "保障" in text)


def verify_candidate(item, from_date, to_date):
    href = item.get("href", "")
    opened = open_url(href)
    time.sleep(1)
    evaluated = run_browser_use(["eval", PAGE_JS])
    page = parse_result(evaluated)
    final_url = page.get("href", "")
    lower_url = final_url.lower()
    stable = bool(final_url) and not any(marker in lower_url for marker in REJECT_MARKERS)
    authoritative = any(marker in lower_url for marker in OFFICIAL_MARKERS)
    text = page.get("text", "")
    content_match = "收购存量商品房" in text and ("保障性住房" in text or "保障性租赁住房" in text)
    date_strings = {
        current.isoformat()
        for current in (
            parse_iso_date(from_date) + timedelta(days=offset)
            for offset in range((parse_iso_date(to_date) - parse_iso_date(from_date)).days + 1)
        )
    }
    cn_date_strings = {value.replace("-", "年", 1).replace("-", "月", 1) + "日" for value in date_strings}
    in_window = any(value in text for value in date_strings | cn_date_strings)
    return {
        "source_result": item,
        "open": opened,
        "page": page,
        "stable": stable,
        "authoritative": authoritative,
        "content_match": content_match,
        "in_window": in_window,
        "verified": stable and authoritative and content_match and in_window,
    }


def scan_city(city_id, city, year, verify_limit, window_text, from_date, to_date):
    city_name = city["name"]
    baidu = search_baidu(city_name, year, window_text)
    sogou = search_sogou_weixin(city_name, year, window_text)
    verified = []
    baidu_results = baidu["results"] if isinstance(baidu["results"], list) else []
    sogou_results = sogou["results"] if isinstance(sogou["results"], list) else []
    relevant_results = [x for x in baidu_results + sogou_results if looks_relevant(x, city_name)]
    for item in relevant_results[:verify_limit]:
        verified.append(verify_candidate(item, from_date, to_date))
    return {
        "city_id": city_id,
        "city_name": city_name,
        "baidu": baidu,
        "sogou_weixin": sogou,
        "verified_candidates": verified,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--year", default=str(date.today().year))
    parser.add_argument("--from-date", help="Inclusive scan window start. Defaults to previous Monday.")
    parser.add_argument("--to-date", help="Inclusive scan window end. Defaults to previous Sunday.")
    parser.add_argument("--cities", nargs="*", default=list(CORE_CITIES.keys()))
    parser.add_argument("--verify-limit", type=int, default=2)
    args = parser.parse_args()
    default_from, default_to = previous_week_window(args.run_date)
    from_date = args.from_date or default_from
    to_date = args.to_date or default_to
    window_text = format_cn_window(from_date, to_date)

    out_dir = PROJECT_DIR / "skills/storage-event-scanner/results/weekly" / args.run_date
    out_dir.mkdir(parents=True, exist_ok=True)

    scans = []
    for city_id in args.cities:
        if city_id not in CORE_CITIES:
            raise SystemExit(f"Unknown city_id: {city_id}")
        scans.append(scan_city(city_id, CORE_CITIES[city_id], args.year, args.verify_limit, window_text, from_date, to_date))
        (out_dir / "browser_use_scan_partial.json").write_text(
            json.dumps(scans, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    verified = []
    for city_scan in scans:
        for item in city_scan["verified_candidates"]:
            if item.get("verified"):
                verified.append({
                    "city_id": city_scan["city_id"],
                    "city_name": city_scan["city_name"],
                    "title": item["page"].get("title", ""),
                    "source_url": item["page"].get("href", ""),
                    "text_excerpt": item["page"].get("text", "")[:1200],
                    "source_result": item["source_result"],
                })

    (out_dir / "browser_use_scan.json").write_text(
        json.dumps(
            {
                "run_date": args.run_date,
                "scan_window": {"from": from_date, "to": to_date, "label": window_text},
                "city_results": scans,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "browser_use_verified_candidates.json").write_text(
        json.dumps(verified, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "cities": len(scans),
        "verified": len(verified),
        "scan_window": {"from": from_date, "to": to_date},
        "out_dir": str(out_dir),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
