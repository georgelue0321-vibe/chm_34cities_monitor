#!/usr/bin/env python3
"""
Storage Event Scanner v2.0 — Search, filter, resolve URLs, output candidates.

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
from datetime import datetime

# Paths
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(PROJECT_DIR, "china_monitor_db.sqlite")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

# 34 cities
CITIES = {
    "bj": "北京", "sh": "上海", "sz": "深圳", "gz": "广州",
    "cd": "成都", "cq": "重庆", "hz": "杭州", "wh": "武汉",
    "xa": "西安", "nj": "南京", "tj": "天津", "cs": "长沙",
    "hf": "合肥", "zz": "郑州", "xm": "厦门", "qd": "青岛",
    "nb": "宁波", "fz": "福州",
    "sjz": "石家庄", "ty": "太原", "hhht": "呼和浩特",
    "sy": "沈阳", "cc": "长春", "heb": "哈尔滨",
    "nc": "南昌", "jn": "济南", "nn": "南宁", "hk": "海口",
    "gy": "贵阳", "km": "昆明", "lz": "兰州", "xn": "西宁",
    "yc": "银川", "wlmq": "乌鲁木齐"
}

# ─── Source Whitelist ────────────────────────────────────────────

SOURCE_WHITELIST = [
    ".gov.cn",
    "mp.weixin.qq.com",
    "xinhuanet.com",
    "people.com.cn",
    "cctv.com",
    "chinanews.com",
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
        f"{city_name} 收购存量商品房 保障房 site:gov.cn",
        f"{city_name} 收购已建成存量商品房 用作保障性住房",
        f"{city_name} 保障性住房 征集公告 收购",
    ]


def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


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
    return run_cmd(["browser-use", "open", url])


def browser_eval(js):
    output = run_cmd(["browser-use", "eval", js])
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
    stages = [
        ("改造完成", ["竣工", "交付", "配租", "配售", "入住"]),
        ("签约收购", ["签约", "签署", "落地", "首单", "首例"]),
        ("成交公示", ["中标", "成交", "公示"]),
        ("正式招标", ["招标", "比选", "采购"]),
        ("房源征集", ["征集", "公告", "公开征集"]),
        ("政策表态", ["方案", "通知", "意见", "政策", "推进", "部署", "要求"]),
    ]
    for stage, keywords in stages:
        for kw in keywords:
            if kw in text:
                return stage
    return "政策表态"


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
        time.sleep(3)

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
        time.sleep(3)

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

def scan_city(city_id, city_name):
    """Scan a city and return candidates for agent verification."""
    log(f"\n{'='*60}")
    log(f"Scanning: {city_name} ({city_id})")
    log(f"{'='*60}")

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
        stage = classify_stage(text)
        date = extract_date(text)

        # Source type
        if ".gov.cn" in final_url:
            source_type = "gov_official"
            confidence = 95
        elif "mp.weixin.qq.com" in final_url:
            source_type = "gov_wechat"
            confidence = 90
        else:
            source_type = "state_media"
            confidence = 85

        candidate = {
            "title": item["title"],
            "raw_url": raw_url,
            "final_url": final_url,
            "resolve_status": resolve_status,
            "abstract": item["abstract"],
            "source_type": source_type,
            "confidence": confidence,
            "suggested_stage": stage,
            "suggested_date": date,
            "city_match": city_match,
            "engine": item.get("engine", "unknown"),
            "needs_verification": True,
        }
        candidates.append(candidate)
        log(f"  CANDIDATE: {item['title'][:60]}... [{source_type}]")

    log(f"  Candidates for review: {len(candidates)}")
    return candidates


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Storage Event Scanner v2.0")
    parser.add_argument("--city", help="City ID to scan (e.g., bj, sh)")
    parser.add_argument("--all", action="store_true", help="Scan all cities")
    args = parser.parse_args()

    log("=" * 60)
    log("Storage Event Scanner v2.0")
    log("=" * 60)
    log("Mode: Search → Filter → Resolve → Output candidates")
    log("Does NOT auto-import. Agent verifies each candidate.\n")

    if args.city:
        cities = {args.city: CITIES[args.city]}
    elif args.all:
        cities = CITIES
    else:
        log("Usage: scanner.py --city <id> | --all")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total_candidates = 0

    for i, (city_id, city_name) in enumerate(cities.items(), 1):
        try:
            log(f"\n[{i}/{len(cities)}] {city_name}")
            candidates = scan_city(city_id, city_name)
            total_candidates += len(candidates)

            # Save candidates
            out_file = os.path.join(OUTPUT_DIR, f"{city_id}_candidates.json")
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(candidates, f, ensure_ascii=False, indent=2)

            if candidates:
                log(f"  → Saved {len(candidates)} candidates to {out_file}")
            else:
                log(f"  → No candidates found")

        except KeyboardInterrupt:
            log("\nInterrupted by user.", "WARN")
            break
        except Exception as e:
            log(f"  Error: {e}", "ERROR")
            continue

    log(f"\n{'='*60}")
    log(f"Scan complete. Total candidates: {total_candidates}")
    log(f"Next: Agent verifies each candidate before importing.")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
