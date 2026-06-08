"""Main data payload assembly for the HTML report.

Queries SQLite and builds the complete nested dict structure consumed by the
HTML SPA. Delegates chart-related analysis to the charts module.
"""
import sqlite3
import json
from datetime import datetime, timedelta

from ..config import DB_PATH, CORE_CITIES, BSS_LOW_DATA_V1
from ..scoring.factors import resolve_current_month, calc_pboc_freshness
from ..scoring.bottom import decide_city_status_timeline, generate_warnings
from .charts import (
    compute_chart_visibility,
    compute_suppressed_metrics,
    compute_signal_validation_coverage,
    compute_evidence_grade,
    get_highest_storage_stage,
    compute_risk_level,
    compute_signal_strength,
    generate_signal_interpretation,
)


def _get_last_crawl_date(cursor, fallback_month):
    """Get the date of the last data crawl from data_quality_log."""
    cursor.execute("SELECT MAX(collected_at) FROM data_quality_log")
    row = cursor.fetchone()
    if row and row[0]:
        return row[0][:10]  # Extract YYYY-MM-DD from timestamp
    return fallback_month + "-01"


def fetch_data_payload():
    """Retrieve full unified upgraded multi-city data payload from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    current_month = resolve_current_month(conn)

    # 1. Fetch PBOC global re-lending data
    cursor.execute("SELECT date, balance_billion, percentage, source FROM pboc_global ORDER BY date ASC")
    pboc_rows = cursor.fetchall()
    pboc_history = []
    for r in pboc_rows:
        pboc_history.append({
            "date": r[0],
            "balance_billion": r[1],
            "percentage": r[2],
            "source": r[3]
        })

    latest_pboc = pboc_history[-1]
    total_quota = 3000
    latest_balance = latest_pboc["balance_billion"] * 10
    remaining_quota = total_quota - latest_balance
    remaining_percentage = round((remaining_quota / total_quota) * 100, 1)

    quarter_increase = 0
    quarter_increase_percentage = 0.0
    if len(pboc_history) >= 2:
        prev_balance = pboc_history[-2]["balance_billion"] * 10
        quarter_increase = latest_balance - prev_balance
        if prev_balance > 0:
            quarter_increase_percentage = round((quarter_increase / prev_balance) * 100, 1)

    # Calculate active storage cities (only those with signed acquisition deals)
    cursor.execute("""
    SELECT COUNT(DISTINCT city_id) FROM storage_execution_events
    WHERE substr(event_date, 1, 7) <= ? AND event_stage IN ('签约收购', '成交公示', '改造完成', '改造完成/配租配售')
    """, (current_month,))
    active_cities_count = cursor.fetchone()[0]

    cursor.execute("""
    SELECT SUM(units_planned), SUM(units_acquired) FROM storage_execution_events WHERE substr(event_date, 1, 7) <= ?
    """, (current_month,))
    planned, acquired = cursor.fetchone()
    units_acquired = int(acquired) if acquired else 0

    # Double-Criteria Governance: Calculate bottom-up implied landed funds from SQLite local storage events
    cursor.execute("""
    SELECT id, city_id, event_date, title, units_acquired, area_sqm_acquired, acquisition_price_total, local_resale_avg_price_sqm, discount_to_market
    FROM storage_execution_events
    WHERE event_stage IN ('成交公示', '签约收购', '改造完成/配租配售') AND substr(event_date, 1, 7) <= ?
    """, (current_month,))
    landed_rows = cursor.fetchall()

    event_contributions = []
    total_landed_wan = 0.0
    for row_id, city, date, title, u_acq, a_acq, p_tot, resale_p, discount in landed_rows:
        contrib = 0.0
        if p_tot and p_tot > 0:
            contrib = p_tot
        elif a_acq and a_acq > 0 and resale_p and resale_p > 0:
            d = discount if (discount and 0.1 <= discount <= 1.0) else 0.6
            contrib = a_acq * resale_p * d
        elif u_acq and u_acq > 0:
            contrib = u_acq * 55.0  # 55 万元/套
        event_contributions.append((row_id, city, date, title or "", contrib))
        total_landed_wan += contrib

    # Outlier defense: if any single event accounts for >50% of total, flag for LLM verification
    outlier_threshold = 0.50
    if total_landed_wan > 0:
        for rid, city, date, title, c in event_contributions:
            if c / total_landed_wan > outlier_threshold:
                pct = c / total_landed_wan * 100
                print(f"⚠️  OUTLIER: event #{rid} ({city} {date}) accounts for {pct:.1f}% of implied landed ({c/10000:.1f}亿). LLM verification required.")
                print(f"   Title: {title[:80]}")

    pboc_implied_landed = round(total_landed_wan / 10000.0, 2)

    pboc_fresh = calc_pboc_freshness(latest_pboc["date"], current_month)
    pboc_payload = {
        "latest_percentage": latest_pboc["percentage"],
        "latest_balance": latest_balance,
        "remaining_quota": remaining_quota,
        "remaining_percentage": remaining_percentage,
        "quarter_increase": quarter_increase,
        "quarter_increase_percentage": quarter_increase_percentage,
        "active_cities_count": active_cities_count,
        "units_acquired": units_acquired,
        "history": pboc_history,
        "pboc_official_latest": latest_balance,
        "pboc_official_percentage": latest_pboc["percentage"],
        "pboc_official_date": latest_pboc["date"],
        "pboc_implied_landed": pboc_implied_landed,
        "pboc_is_stale": pboc_fresh["is_stale"],
        "pboc_stale_months": pboc_fresh["stale_months"],
        "pboc_data_status": pboc_fresh["data_status"]
    }

    # 2. Fetch Cities specific details
    cities_payload = {}
    scored_cities = []
    watch_only_cities = []
    excluded_cities = []
    cursor.execute("SELECT id, name, level, quota_billion FROM cities")
    cities_rows = cursor.fetchall()

    rankings_list = []

    for crow in cities_rows:
        cid, name, level, quota = crow

        # Calculate full historical scores and status timeline up to target month
        score_timeline = decide_city_status_timeline(conn, cid, current_month)
        if not score_timeline:
            continue
        latest_timeline = score_timeline[-1]

        # Market listings & price timeline
        cursor.execute("SELECT date, listings, price_sqm FROM market_index WHERE city_id = ? ORDER BY date ASC", (cid,))
        m_rows = cursor.fetchall()
        market_history = []
        for mr in m_rows:
            cursor.execute("SELECT value_status FROM data_quality_log WHERE city_id = ? AND period = ? AND metric_name = 'listings'", (cid, mr[0]))
            list_q = cursor.fetchone()
            cursor.execute("SELECT value_status FROM data_quality_log WHERE city_id = ? AND period = ? AND metric_name = 'price'", (cid, mr[0]))
            price_q = cursor.fetchone()

            market_history.append({
                "date": mr[0],
                "listings": mr[1],
                "listings_status": list_q[0] if list_q else "scraped",
                "price_sqm": mr[2],
                "price_status": price_q[0] if price_q else "scraped"
            })

        # Official NBS Price Index timeline
        cursor.execute("""
        SELECT month, new_home_mom, new_home_yoy, resale_home_mom, resale_home_yoy
        FROM city_price_index_monthly WHERE city_id = ? ORDER BY month ASC
        """, (cid,))
        idx_rows = cursor.fetchall()
        price_index_history = []
        seen_months = set()
        for ir in idx_rows:
            if ir[0] not in seen_months:
                seen_months.add(ir[0])
                price_index_history.append({
                    "date": ir[0],
                    "new_home_mom": ir[1],
                    "new_home_yoy": ir[2],
                    "resale_home_mom": ir[3],
                    "resale_home_yoy": ir[4]
                })

        # Official transaction volume timeline
        cursor.execute("""
        SELECT month, new_home_sales_area, new_home_sales_units, resale_sales_area, resale_sales_units, resale_online_sign_units
        FROM city_transaction_monthly WHERE city_id = ? ORDER BY month ASC
        """, (cid,))
        tx_rows = cursor.fetchall()
        transaction_history = []
        for tr in tx_rows:
            transaction_history.append({
                "date": tr[0],
                "new_home_sales_area": tr[1],
                "new_home_sales_units": tr[2],
                "resale_sales_area": tr[3],
                "resale_sales_units": tr[4],
                "resale_online_sign_units": tr[5]
            })

        # Storage execution events list
        cursor.execute("""
        SELECT event_date, district, event_stage, title, details, buyer_entity, seller_entity, project_name,
               units_planned, units_acquired, area_sqm_planned, area_sqm_acquired,
               acquisition_price_total, acquisition_price_sqm, local_resale_avg_price_sqm, discount_to_market,
               funding_type, source_url
        FROM storage_execution_events WHERE city_id = ? ORDER BY event_date DESC
        """, (cid,))
        se_rows = cursor.fetchall()
        storage_execution_history = []
        for sr in se_rows:
            storage_execution_history.append({
                "date": sr[0],
                "district": sr[1],
                "stage": sr[2],
                "title": sr[3],
                "details": sr[4],
                "buyer": sr[5],
                "seller": sr[6],
                "project": sr[7],
                "units_planned": sr[8],
                "units_acquired": sr[9],
                "area_planned": sr[10],
                "area_acquired": sr[11],
                "price_total": sr[12],
                "price_sqm": sr[13],
                "resale_avg": sr[14],
                "discount": sr[15],
                "funding_type": sr[16],
                "source_url": sr[17]
            })

        # Brokerage Opinions
        cursor.execute("""
        SELECT date, institution, opinion, consensus
        FROM professional_opinions WHERE city_id = ? ORDER BY id ASC
        """, (cid,))
        op_rows = cursor.fetchall()
        opinions = []
        consensus = ""
        consensus_institution = ""
        for opr in op_rows:
            opinions.append({
                "date": opr[0],
                "institution": opr[1],
                "opinion": opr[2]
            })
            if opr[3]:
                consensus = opr[3]
                consensus_institution = opr[1]

        if not consensus and opinions:
            consensus = "分析师对该城市的收储进度保持谨慎，认为政策有兜底支撑但仍需成交恢复确认。"
            consensus_institution = opinions[0]["institution"]
        if not consensus:
            consensus = "暂无券商研报覆盖，建议关注当地住建局及统计局官方数据。"
            consensus_institution = ""

        # Generate estimated percentage stats for current month
        cursor.execute("SELECT listings FROM market_index WHERE city_id = ? AND date = ?", (cid, current_month))
        m_row = cursor.fetchone()
        listings_missing = (not m_row or m_row[0] == -1)

        cursor.execute("SELECT resale_online_sign_units FROM city_transaction_monthly WHERE city_id = ? AND month = ?", (cid, current_month))
        tx_row = cursor.fetchone()
        tx_missing = (not tx_row or tx_row[0] is None or tx_row[0] == 0)

        cursor.execute("SELECT metric_name, value_status FROM data_quality_log WHERE city_id = ? AND period = ?", (cid, current_month))
        dq_rows = cursor.fetchall()
        dq_dict = {row[0]: row[1] for row in dq_rows}

        price_index_status = "official"
        transaction_status = "missing" if tx_missing else "official"
        listings_status = "missing" if listings_missing else "scraped"
        price_status = dq_dict.get("price", "scraped")
        storage_status = "official" if len(storage_execution_history) > 0 else "missing"

        statuses = [price_index_status, transaction_status, listings_status, price_status, storage_status]

        official_price_count = 1 if price_index_status == "official" else 0
        official_transaction_count = 1 if transaction_status == "official" else 0
        scraped_count = sum(1 for s in [listings_status, price_status] if s == "scraped")
        estimated_demo_count = sum(1 for s in statuses if s in ["estimated", "demo"])
        missing_count = sum(1 for s in statuses if s == "missing")

        total_vars = 5
        official_price_ratio = int(official_price_count / total_vars * 100)
        official_transaction_ratio = int(official_transaction_count / total_vars * 100)
        scraped_ratio = int(scraped_count / total_vars * 100)
        estimated_demo_ratio = int(estimated_demo_count / total_vars * 100)
        missing_ratio = int(missing_count / total_vars * 100)

        quality_stats = {
            "official_price_ratio": official_price_ratio,
            "official_transaction_ratio": official_transaction_ratio,
            "scraped_ratio": scraped_ratio,
            "estimated_demo_ratio": estimated_demo_ratio,
            "missing_ratio": missing_ratio
        }

        # Enrich timeline with latest quality stats
        latest_timeline["official_price_ratio"] = official_price_ratio
        latest_timeline["official_transaction_ratio"] = official_transaction_ratio
        latest_timeline["scraped_ratio"] = scraped_ratio
        latest_timeline["estimated_demo_ratio"] = estimated_demo_ratio
        latest_timeline["missing_ratio"] = missing_ratio

        # Chart visibility & suppressed metrics (delegated to charts module)
        chart_visibility = compute_chart_visibility(transaction_history, market_history)
        suppressed_metrics = compute_suppressed_metrics(chart_visibility)

        # Compute Signal and Validation Coverage
        signal_coverage_pct, validation_coverage_pct = compute_signal_validation_coverage(
            chart_visibility, price_index_history, storage_execution_history
        )

        # Resolve Evidence Grade
        pboc_is_stale = latest_timeline.get("pboc_is_stale", False)
        num_core_signals = 1
        if len(price_index_history) > 0:
            num_core_signals += 1
        if len(storage_execution_history) > 0:
            num_core_signals += 1

        evidence_grade = compute_evidence_grade(
            signal_coverage_pct, validation_coverage_pct,
            estimated_demo_ratio, num_core_signals, pboc_is_stale
        )

        # Resolve highest storage stage
        highest_storage_stage = get_highest_storage_stage(storage_execution_history)

        # Warnings Generator
        warnings_payload = generate_warnings({
            "price_index_history": price_index_history,
            "tx_missing": tx_missing,
            "listings_missing": listings_missing,
            "highest_storage_stage": highest_storage_stage
        }, score_timeline)

        # Add PBOC stale warning if applicable
        if pboc_is_stale:
            warnings_payload.append({
                "category": "coverage",
                "type": "warning",
                "title": "PBOC 数据已过期，仅作历史参考",
                "desc": "央行尚未披露最新季度保障房再贷款使用数据，当前资金温度指标基于历史官方披露（2024-09-30），降权参与评分。"
            })

        # Decide risk level and signal strength
        risk_level = compute_risk_level(latest_timeline["status"], pboc_is_stale)
        signal_strength = compute_signal_strength(latest_timeline["score"])

        city_qual = latest_timeline.get("city_qualification", "scored")

        city_entry = {
            "name": name,
            "level": level,
            "quota_billion": quota,
            "lat": CORE_CITIES.get(cid, {}).get("lat"),
            "lng": CORE_CITIES.get(cid, {}).get("lng"),
            "bottom_score": latest_timeline["score"],
            "bottom_status": latest_timeline["status"],
            "risk_level": risk_level,
            "signal_strength": signal_strength,
            "factors": latest_timeline["factors"],
            "quality_stats": quality_stats,
            "market_history": market_history,
            "price_index_history": price_index_history,
            "transaction_history": transaction_history,
            "storage_execution_history": storage_execution_history,
            "score_history": [{"date": x["date"], "score": x["score"]} for x in score_timeline],
            "opinions": opinions,
            "consensus": consensus,
            "consensus_institution": consensus_institution,
            "warnings": warnings_payload,
            "positive_drivers": latest_timeline.get("positive_drivers", ""),
            "negative_drivers": latest_timeline.get("negative_drivers", ""),
            "cap_reason": latest_timeline.get("cap_reason", ""),
            "validation_status": latest_timeline.get("validation_status", "未通过"),
            "validation_reason": latest_timeline.get("validation_reason", ""),
            "transaction_validation": latest_timeline.get("transaction_validation", "未验证 / 数据缺失"),
            "supply_validation": latest_timeline.get("supply_validation", "未验证"),
            "storage_validation": latest_timeline.get("storage_validation", "政策表态"),
            "price_validation": latest_timeline.get("price_validation", "未通过"),
            "indicators": {
                "listings_missing": listings_missing,
                "tx_missing": tx_missing
            },
            "chart_visibility": chart_visibility,
            "suppressed_metrics": suppressed_metrics,
            "evidence_grade": evidence_grade,
            "signal_coverage": signal_coverage_pct,
            "validation_coverage": validation_coverage_pct,
            "estimated_demo_ratio": estimated_demo_ratio,
            "highest_storage_stage": highest_storage_stage,
            "scoring_mode": latest_timeline.get("scoring_mode", "low_data"),
            "scoring_formula_version": latest_timeline.get("scoring_formula_version", "BSS_LOW_DATA_V1"),
            "formula_disclosure": latest_timeline.get("formula_disclosure", "0.60*S_Price + 0.30*S_Storage + 0.10*S_PBOC"),
            "layer_a_factors": BSS_LOW_DATA_V1["factors"],
            "layer_b_gates": BSS_LOW_DATA_V1["gates"],
            "score_source": "bottom_score_monthly",
            "calculated_at": latest_timeline.get("calculated_at", ""),
            "city_qualification": city_qual
        }

        cities_payload[cid] = city_entry

        if city_qual == "scored":
            scored_cities.append(cid)
        elif city_qual == "watch_only":
            watch_only_cities.append(cid)
        else:
            excluded_cities.append(cid)

        score_change = 0
        if len(score_timeline) >= 2:
            score_change = round(score_timeline[-1]["score"] - score_timeline[-2]["score"], 2)

        rankings_list.append({
            "city_id": cid,
            "name": name,
            "level": level,
            "score": latest_timeline["score"],
            "status": latest_timeline["status"],
            "change": score_change,
            "evidence_grade": evidence_grade,
            "highest_storage_stage": highest_storage_stage
        })

    # Filter rankings to only scored cities
    rankings_list = [r for r in rankings_list if r["city_id"] in scored_cities]
    rankings_list.sort(key=lambda x: x["score"], reverse=True)

    # Build rank lookup and inject signal_interpretation
    rank_lookup = {r["city_id"]: i + 1 for i, r in enumerate(rankings_list)}
    total_cities = len(rankings_list)
    for cid, city in cities_payload.items():
        rank = rank_lookup.get(cid, 0)
        city["signal_interpretation"] = generate_signal_interpretation(
            city, rank, total_cities, pboc_is_stale
        )

    last_updated = _get_last_crawl_date(cursor, current_month)
    conn.close()

    # Baseline date = crawl date - 1 day (crawl runs past midnight, data is from prior day)
    try:
        crawl_date = datetime.strptime(last_updated, "%Y-%m-%d")
        baseline_date = (crawl_date - timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        baseline_date = last_updated

    # Next update: next Monday after baseline
    try:
        base_date = datetime.strptime(baseline_date, "%Y-%m-%d")
        days_until_monday = (7 - base_date.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_update = (base_date + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
        # If calculated next_update is in the past or today, roll forward by 7 days
        if next_update and next_update <= last_updated:
            next_date = datetime.strptime(next_update, "%Y-%m-%d")
            next_update = (next_date + timedelta(days=7)).strftime("%Y-%m-%d")
    except Exception:
        next_update = ""

    payload = {
        "pboc_global": pboc_payload,
        "cities": cities_payload,
        "rankings": rankings_list,
        "scored_cities": scored_cities,
        "watch_only_cities": watch_only_cities,
        "excluded_cities": excluded_cities,
        "scoring_mode": "low_data",
        "scoring_formula_version": "BSS_LOW_DATA_V1",
        "formula_disclosure": "0.60*S_Price + 0.30*S_Storage + 0.10*S_PBOC",
        "layer_a_factors": BSS_LOW_DATA_V1["factors"],
        "layer_b_gates": BSS_LOW_DATA_V1["gates"],
        "last_updated": baseline_date,
        "next_update": next_update
    }

    return payload
