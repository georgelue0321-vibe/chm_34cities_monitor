#!/usr/bin/env python3
"""
Storage Event Scanner v2.2 — Search, filter, resolve URLs, output weekly candidates.

Workflow:
  1. Search Baidu/Sogou with tight keywords
  2. Filter by source whitelist + title blacklist
  3. Resolve redirect URLs (baidu.com/link → actual destination)
  4. Output candidates JSON for agent verification
  5. Agent verifies and imports manually

Does NOT auto-import. Outputs candidates for human/agent review.
"""

import json
import os
import sys
import subprocess
import hashlib
import re
import time
import urllib.request
import urllib.parse
import sqlite3
from datetime import datetime

# Paths
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(PROJECT_DIR, "china_monitor_db.sqlite")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
MAX_CANDIDATES_PER_CITY = 5
SCORE_ELIGIBLE_STAGES = {"房源征集", "正式招标", "成交公示", "签约收购", "改造完成/配租配售"}
STAGE_ALIASES = {"改造完成": "改造完成/配租配售"}

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from china_housing_monitor.config import CORE_CITIES
from deduplicator import EventDeduplicator
from source_validator import SourceValidator
from stage_classifier import StageClassifier

# CHM is the source of truth for city IDs. Do not maintain a separate list here.
CITIES = {city_id: meta["name"] for city_id, meta in CORE_CITIES.items()}
STAGE_CLASSIFIER = StageClassifier()
SOURCE_VALIDATOR = SourceValidator()
DEDUPLICATOR = EventDeduplicator()

# ─── Source Whitelist ────────────────────────────────────────────

SOURCE_WHITELIST = [
    ".gov.cn",
    "mp.weixin.qq.com",
    "xinhuanet.com",
    "people.com.cn",
    "cctv.com",
    "chinanews.com",
    "pbc.gov.cn",
]

# ─── Title Blacklist ────────────────────────────────────────────

# Titles containing these are automatically excluded
TITLE_EXCLUDE = [
    # Non-storage topics
    "以旧换新", "土地收储", "城中村", "租赁住房", "公租房",
    "房价", "涨跌", "预测", "分析", "观点", "评论", "解读",
    "盘点", "汇总", "梳理", "展望", "趋势",
    # Low quality
    "百度百科", "百度知道", "百度地图", "贴吧", "论坛",
    "小红书", "问答", "经验", "精选笔记",
    # National/multi-city (not city-specific)
    "多地", "全国", "各地", "各省", "众多城市",
    # Unrelated
    "二手房交易", "中介", "佣金", "法拍",
    "征迁", "拆迁", "旧改", "城市更新",
    "地铁", "交通", "教育", "医疗",
]

# ─── Search Keywords ────────────────────────────────────────────

def get_search_queries(city_name):
    """Generate tight search queries for a city."""
    return [
        f"{city_name} 收购存量商品房 用作保障性住房 site:gov.cn",
        f"{city_name} 征集 已建成 存量商品房 保障性住房 site:gov.cn",
        f"{city_name} 收购存量商品房 保障性住房 最近两周",
        f"{city_name} 保障性住房 房源征集 收购 最近两周",
    ]


def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def get_weekly_output_dir(run_date=None):
    """Return the weekly JSON output directory and create it if needed."""
    run_date = run_date or datetime.now().strftime("%Y-%m-%d")
    out_dir = os.path.join(OUTPUT_DIR, "weekly", run_date)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def load_existing_source_urls(db_path=DB_PATH):
    """Load already imported source URLs so weekly scans stay incremental."""
    if not os.path.exists(db_path):
        return set()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT source_url FROM storage_execution_events WHERE source_url IS NOT NULL AND source_url != ''")
        urls = {row[0] for row in cursor.fetchall()}
        conn.close()
        return urls
    except sqlite3.Error as exc:
        log(f"Could not load existing source URLs: {exc}", "WARN")
        return set()


def normalize_stage(stage):
    return STAGE_ALIASES.get(stage, stage)


def is_stage_score_eligible(stage):
    return normalize_stage(stage) in SCORE_ELIGIBLE_STAGES


def sort_candidates(candidates):
    """Put stronger evidence first for review."""
    return sorted(
        candidates,
        key=lambda item: (
            int(item.get("source_priority", 0)),
            1 if item.get("suggested_stage") in SCORE_ELIGIBLE_STAGES else 0,
            item.get("suggested_date") or "",
        ),
        reverse=True,
    )


# ─── Browser Helpers ────────────────────────────────────────────

def run_cmd(cmd, timeout=20):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        log(f"Command error: {e}", "ERROR")
        return ""


def browser_open(url):
    return run_cmd(["browser-use", "--headed", "--session", "scanner", "open", url])


def browser_eval(js):
    output = run_cmd(["browser-use", "--session", "scanner", "eval", js])
    if output.startswith("result: "):
        return output[8:]
    return output


# ─── URL Resolution ─────────────────────────────────────────────

def resolve_redirect(url, timeout=10):
    """Follow redirects and return the final URL.
    
    If the redirect leads to an antispider page, waits for user
    to solve the captcha in Chrome, then retries.
    """
    if not url:
        return url, "empty"

    # If already a direct URL, just return it
    if not any(d in url for d in ["baidu.com/link", "sogou.com/link"]):
        return url, "direct"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        response = urllib.request.urlopen(req, timeout=timeout)
        final_url = response.geturl()

        # Check if redirected to antispider page
        if "antispider" in final_url or "verify" in final_url:
            log("    ⚠ Sogou antispider redirect detected!", "WARN")
            log("    Please solve the captcha in Chrome (opening the URL)...", "WARN")
            # Open in browser for user to solve
            browser_open(url)
            # Wait for captcha resolution
            for attempt in range(12):
                time.sleep(5)
                try:
                    req2 = urllib.request.Request(url, headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
                    })
                    resp2 = urllib.request.urlopen(req2, timeout=timeout)
                    final2 = resp2.geturl()
                    if "antispider" not in final2 and "verify" not in final2:
                        log(f"    ✓ Captcha solved, got: {final2[:60]}...")
                        return final2, "resolved_after_captcha"
                except Exception:
                    pass
            log("    ✗ Captcha timeout, URL unresolvable", "WARN")
            return final_url, "captcha_timeout"

        return final_url, "resolved"
    except Exception as e:
        return url, f"error: {str(e)[:50]}"


def is_whitelisted_source(url):
    """Check if URL is from a whitelisted source."""
    if not url:
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in SOURCE_WHITELIST)


def is_stable_final_url(url):
    """Reject temporary search-engine redirect URLs as final evidence."""
    if not url:
        return False
    url_lower = url.lower()
    redirect_markers = ["baidu.com/link", "weixin.sogou.com/link", "sogou.com/link", "antispider"]
    return not any(marker in url_lower for marker in redirect_markers)


# ─── City Label Verification ────────────────────────────────────

def verify_city_match(title, abstract, target_city_name):
    """Check if the article is actually about the target city."""
    text = title + " " + abstract

    # Direct city name mention
    if target_city_name in text:
        return True

    # Check for other city names (suggests mislabel)
    other_cities = [name for cid, name in CITIES.items() if name != target_city_name]
    for other in other_cities:
        if other in text:
            return False  # Mentions a different city

    # Ambiguous - no city mention
    return None


def classify_stage(text):
    """Classify event stage from text."""
    stage, _weight = STAGE_CLASSIFIER.classify(text)
    return stage


def extract_date(text):
    """Extract date from text."""
    patterns = [
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"(\d{4})-(\d{2})-(\d{2})",
        r"(\d{4})\.(\d{2})\.(\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            groups = match.groups()
            return f"{groups[0]}-{groups[1].zfill(2)}-{groups[2].zfill(2)}"
    return ""


# ─── Search ─────────────────────────────────────────────────────

def search_baidu(city_name, queries):
    """Search Baidu with tight keywords and filter results."""
    results = []

    for query in queries:
        encoded = urllib.parse.quote(query)
        url = f"https://www.baidu.com/s?wd={encoded}"
        log(f"  [Baidu] {query[:50]}...")
        browser_open(url)
        time.sleep(5)

        js = """
        JSON.stringify(Array.from(document.querySelectorAll('#content_left .c-container')).slice(0,10).map(el => {
            const t = el.querySelector('h3 a');
            const a = el.querySelector('.c-abstract');
            return {
                title: t ? t.innerText.trim().substring(0,200) : '',
                url: t ? t.href : '',
                abstract: a ? a.innerText.trim().substring(0,500) : ''
            };
        }).filter(x => x.title && x.url))
        """

        raw = browser_eval(js)
        if not raw:
            continue

        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for item in items:
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            raw_url = item.get("url", "")

            if any(ex in title for ex in TITLE_EXCLUDE):
                continue
            if any(ex in abstract for ex in ["以旧换新", "土地收储"]):
                continue

            other_cities = [name for cid, name in CITIES.items() if name != city_name]
            if any(other in title for other in other_cities):
                continue

            storage_kw = ["收购", "收储", "存量房", "存量商品房", "保障房", "保障性住房"]
            if not any(kw in title or kw in abstract for kw in storage_kw):
                continue

            results.append({
                "title": title,
                "raw_url": raw_url,
                "abstract": abstract,
                "engine": "baidu",
            })

    return results


def search_sogou_wechat(city_name):
    """Search Sogou WeChat index for government WeChat articles.
    
    Sogou WeChat search finds articles from WeChat Official Accounts,
    which often contain government announcements not indexed by Baidu.
    The redirect URLs (weixin.sogou.com/link) are temporary, but we
    resolve them to permanent mp.weixin.qq.com URLs in the pipeline.
    
    If anti-spider (captcha) is detected, waits for user to solve it
    in Chrome, then retries.
    """
    results = []
    queries = [
        f"{city_name} 收购存量商品房 保障房",
        f"{city_name} 保障性住房 征集公告",
    ]

    for query in queries:
        encoded = urllib.parse.quote(query)
        url = f"https://weixin.sogou.com/weixin?type=2&query={encoded}"
        log(f"  [Sogou WX] {query[:50]}...")
        browser_open(url)
        time.sleep(5)

        # Check for anti-spider captcha (in page URL or content)
        current_url = browser_eval("window.location.href")
        page_text = browser_eval("document.body.innerText.substring(0, 500)")
        is_captcha = (
            (current_url and "antispider" in current_url) or
            (page_text and ("请输入验证码" in page_text[:200] or "antispider" in page_text[:200]))
        )
        if is_captcha:
            log("  ⚠ Sogou captcha detected! Please solve it in Chrome...", "WARN")
            log("  Waiting up to 60s for captcha resolution...", "WARN")
            # Wait for user to solve captcha
            for attempt in range(12):
                time.sleep(5)
                check = browser_eval("document.querySelectorAll('.news-list li, .txt-box').length")
                if check and check != "0":
                    log(f"  ✓ Captcha solved, resuming...")
                    break
            else:
                log("  ✗ Captcha timeout, skipping Sogou WX for this query", "WARN")
                continue

        # Sogou WeChat search results structure
        js = """
        JSON.stringify(Array.from(document.querySelectorAll('.news-list li, .txt-box')).slice(0,8).map(el => {
            const titleEl = el.querySelector('h3 a, .txt-box h3 a');
            const abstractEl = el.querySelector('.txt-info, .txt-box p');
            return {
                title: titleEl ? titleEl.innerText.trim().substring(0,200) : '',
                url: titleEl ? titleEl.href : '',
                abstract: abstractEl ? abstractEl.innerText.trim().substring(0,500) : ''
            };
        }).filter(x => x.title && x.url))
        """

        raw = browser_eval(js)
        if not raw:
            continue

        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            continue

        for item in items:
            title = item.get("title", "")
            abstract = item.get("abstract", "")
            raw_url = item.get("url", "")

            # Skip antispider URLs
            if "antispider" in raw_url:
                continue

            # Same filters as Baidu
            if any(ex in title for ex in TITLE_EXCLUDE):
                continue
            if any(ex in abstract for ex in ["以旧换新", "土地收储"]):
                continue

            other_cities = [name for cid, name in CITIES.items() if name != city_name]
            if any(other in title for other in other_cities):
                continue

            storage_kw = ["收购", "收储", "存量房", "存量商品房", "保障房", "保障性住房"]
            if not any(kw in title or kw in abstract for kw in storage_kw):
                continue

            results.append({
                "title": title,
                "raw_url": raw_url,
                "abstract": abstract,
                "engine": "sogou_wechat",
            })

    return results


# ─── Main Pipeline ──────────────────────────────────────────────

def scan_city(city_id, city_name, existing_source_urls=None):
    """Scan a city and return candidates plus weekly scan stats."""
    log(f"\n{'='*60}")
    log(f"Scanning: {city_name} ({city_id})")
    log(f"{'='*60}")

    existing_source_urls = existing_source_urls or set()
    skipped_existing = 0

    # Step 1: Search both Baidu and Sogou WeChat
    queries = get_search_queries(city_name)
    baidu_results = search_baidu(city_name, queries)
    sogou_results = search_sogou_wechat(city_name)

    raw_results = baidu_results + sogou_results
    log(f"  Baidu: {len(baidu_results)}, Sogou WX: {len(sogou_results)}")
    log(f"  Total raw: {len(raw_results)}")

    # Step 2: Resolve URLs and check whitelist
    candidates = []
    seen_urls = set()

    for item in raw_results:
        raw_url = item["raw_url"]

        # Deduplicate by URL
        url_hash = hashlib.md5(raw_url.encode()).hexdigest()
        if url_hash in seen_urls:
            continue
        seen_urls.add(url_hash)

        # Resolve redirect
        final_url, resolve_status = resolve_redirect(raw_url)
        item["final_url"] = final_url
        item["resolve_status"] = resolve_status

        if final_url in existing_source_urls:
            skipped_existing += 1
            continue

        # Source whitelist check (after redirect resolution)
        if not is_whitelisted_source(final_url):
            if "antispider" in final_url or resolve_status == "captcha_timeout":
                log(f"  SKIP (captcha unresolved): {item['title'][:50]}...")
            else:
                log(f"  SKIP (not whitelisted): {final_url[:60]}...")
            continue

        # City label verification
        city_match = verify_city_match(item["title"], item["abstract"], city_name)
        if city_match is False:
            log(f"  SKIP (wrong city): {item['title'][:50]}...")
            continue

        # Classify
        text = item["title"] + " " + item["abstract"]
        stage = normalize_stage(classify_stage(text))
        date = extract_date(text)

        # Source type
        source_type = SOURCE_VALIDATOR.classify_source(final_url)
        source_reliability = SOURCE_VALIDATOR.get_source_priority(final_url)
        if source_type == "other":
            source_type = "state_media"
            source_reliability = 80

        stable_final_url = is_stable_final_url(final_url)
        score_eligible_suggestion = bool(date and city_match is True and stable_final_url and is_stage_score_eligible(stage))

        candidate = {
            "city_id": city_id,
            "city_name": city_name,
            "title": item["title"],
            "raw_url": raw_url,
            "final_url": final_url,
            "resolve_status": resolve_status,
            "abstract": item["abstract"],
            "source_type": source_type,
            "source_reliability": source_reliability,
            "source_priority": source_reliability,
            "confidence": min(source_reliability, 95),
            "suggested_stage": stage,
            "suggested_date": date,
            "city_match": city_match,
            "stable_final_url": stable_final_url,
            "score_eligible_suggestion": score_eligible_suggestion,
            "engine": item.get("engine", "unknown"),
            "needs_verification": True,
            "review": {
                "status": "pending",
                "required_checks": [
                    "open final_url and confirm the page is accessible",
                    "confirm publisher is an official government, official account, or authoritative media source",
                    "confirm the event is about buying completed inventory commodity housing for保障性住房",
                    "confirm the city in the article matches city_id",
                    "confirm event_date from article body, not search snippet",
                    "check storage_execution_events for duplicate title/date/source_url",
                ],
            },
            "chm_import": {
                "city_id": city_id,
                "event_date": date,
                "event_stage": stage,
                "title": item["title"],
                "details": item["abstract"],
                "source_url": final_url,
                "source_reliability": source_reliability,
                "data_status": "official",
                "confidence_score": min(source_reliability, 95),
                "is_score_eligible": 1 if score_eligible_suggestion else 0,
                "methodology_note": "Scanner candidate; requires agent review before import",
            },
        }
        candidates.append(candidate)
        log(f"  CANDIDATE: {item['title'][:60]}... [{source_type}]")

    deduplicated = DEDUPLICATOR.deduplicate(candidates)
    if len(deduplicated) != len(candidates):
        log(f"  Deduplicated candidates: {len(candidates)} → {len(deduplicated)}")
    for candidate in deduplicated:
        candidate.pop("core", None)
        candidate.pop("core_hash", None)

    deduplicated = sort_candidates(deduplicated)
    log(f"  Candidates for review: {len(deduplicated)}")
    return deduplicated, {"raw_results": len(raw_results), "skipped_existing": skipped_existing}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Storage Event Scanner v2.2")
    parser.add_argument("--city", help="City ID to scan (e.g., bj, sh)")
    parser.add_argument("--all", action="store_true", help="Scan all cities")
    parser.add_argument("--run-date", default=datetime.now().strftime("%Y-%m-%d"), help="Weekly output date directory, YYYY-MM-DD")
    parser.add_argument("--db", default=DB_PATH, help="Path to china_monitor_db.sqlite for incremental URL filtering")
    args = parser.parse_args()

    log("=" * 60)
    log("Storage Event Scanner v2.2")
    log("=" * 60)
    log("Mode: Search engine → Stable URL → Weekly JSON candidates")
    log("Does NOT auto-import. Agent verifies each candidate.\n")

    if args.city and args.city not in CITIES:
        log(f"Unknown city id: {args.city}", "ERROR")
        log("Available city ids: " + ", ".join(sorted(CITIES.keys())), "ERROR")
        sys.exit(2)

    if args.city:
        cities = {args.city: CITIES[args.city]}
    elif args.all:
        cities = CITIES
    else:
        log("Usage: scanner.py --city <id> | --all")
        return

    out_dir = get_weekly_output_dir(args.run_date)
    existing_source_urls = load_existing_source_urls(args.db)
    total_candidates = 0
    combined_candidates = []
    city_logs = []

    for i, (city_id, city_name) in enumerate(cities.items(), 1):
        try:
            log(f"\n[{i}/{len(cities)}] {city_name}")
            candidates, stats = scan_city(city_id, city_name, existing_source_urls=existing_source_urls)
            review_candidates = candidates[:MAX_CANDIDATES_PER_CITY]
            overflow_candidates = candidates[MAX_CANDIDATES_PER_CITY:]
            total_candidates += len(review_candidates)
            combined_candidates.extend(review_candidates)

            out_file = os.path.join(out_dir, f"{city_id}_candidates.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(review_candidates, f, ensure_ascii=False, indent=2)

            overflow_file = ""
            if overflow_candidates:
                overflow_file = os.path.join(out_dir, f"{city_id}_overflow_candidates.json")
                with open(overflow_file, "w", encoding="utf-8") as f:
                    json.dump(overflow_candidates, f, ensure_ascii=False, indent=2)

            needs_watchlist = not review_candidates and stats.get("raw_results", 0) == 0
            city_logs.append({
                "city_id": city_id,
                "city_name": city_name,
                "raw_results": stats.get("raw_results", 0),
                "skipped_existing_source_urls": stats.get("skipped_existing", 0),
                "candidates_for_review": len(review_candidates),
                "overflow_candidates": len(overflow_candidates),
                "candidate_file": out_file,
                "overflow_file": overflow_file,
                "needs_missed_city_watchlist": needs_watchlist,
                "watchlist_reason": "search_engine_returned_no_candidates" if needs_watchlist else "",
            })

            if review_candidates:
                log(f"  → Saved {len(review_candidates)} candidates to {out_file}")
            else:
                log("  → No new candidates found")

            time.sleep(2)

        except KeyboardInterrupt:
            log("\nInterrupted by user.", "WARN")
            break
        except Exception as e:
            log(f"  Error: {e}", "ERROR")
            city_logs.append({
                "city_id": city_id,
                "city_name": city_name,
                "raw_results": 0,
                "skipped_existing_source_urls": 0,
                "candidates_for_review": 0,
                "overflow_candidates": 0,
                "candidate_file": "",
                "overflow_file": "",
                "needs_missed_city_watchlist": True,
                "watchlist_reason": f"scan_error: {e}",
            })
            continue

    combined_file = os.path.join(out_dir, "candidates.json")
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(combined_candidates, f, ensure_ascii=False, indent=2)

    scan_log = {
        "run_date": args.run_date,
        "strategy": "search_engine_plus_stable_url_plus_human_review",
        "searched_city_count": len(cities),
        "max_candidates_per_city": MAX_CANDIDATES_PER_CITY,
        "total_candidates_for_review": total_candidates,
        "city_results": city_logs,
    }
    scan_log_file = os.path.join(out_dir, "scan_log.json")
    with open(scan_log_file, "w", encoding="utf-8") as f:
        json.dump(scan_log, f, ensure_ascii=False, indent=2)

    watchlist = [item for item in city_logs if item.get("needs_missed_city_watchlist")]
    watchlist_file = os.path.join(out_dir, "missed_city_watchlist.json")
    with open(watchlist_file, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

    log(f"\n{'='*60}")
    log(f"Scan complete. Total new candidates for review: {total_candidates}")
    log(f"Weekly output: {out_dir}")
    log("Next: Agent verifies candidates.json before importing.")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
