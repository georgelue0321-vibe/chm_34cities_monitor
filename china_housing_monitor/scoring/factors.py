"""Scoring factor calculations for the Bottom Signal Score.

Contains core functions for computing individual scoring factors:
- Price factor (S_Price): Based on resale home MoM index series
- Storage factor (S_Storage): Based on government acquisition event stages
- PBOC factor (S_PBOC): Based on PBOC re-lending facility progress

Also includes the main compute_and_store_all_scores() function that
calculates and persists monthly scores for all cities.
"""
from datetime import datetime, timedelta
from ..config import (
    CORE_CITIES,
    PBOC_SCORE_MAP,
    PBOC_STALE_CAP,
    PBOC_STALE_MONTHS_THRESHOLD,
    WEEKLY_SCORE_HISTORY_START,
)

PRICE_IMPROVEMENT_EPSILON = 0.001


def resolve_current_month(conn, cli_month=None):
    """Resolve the current month for scoring.

    Priority:
    1. CLI override if provided
    2. Latest month from official/scraped price index data
    3. Fallback to current calendar month
    """
    if cli_month:
        return cli_month
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(month) FROM city_price_index_monthly
        WHERE data_status IN ('official', 'scraped')
    """)
    row = cursor.fetchone()
    if row and row[0]:
        return row[0]
    return datetime.now().strftime("%Y-%m")


def month_diff(m1, m2):
    """Calculate absolute month difference between two YYYY-MM strings."""
    y1, mm1 = map(int, m1.split('-'))
    y2, mm2 = map(int, m2.split('-'))
    return abs((y2 - y1) * 12 + (mm2 - mm1))


def storage_recency_multiplier(event_date, target_month):
    """Calculate recency decay multiplier for a storage event.

    Args:
        event_date: YYYY-MM-DD or YYYY-MM string
        target_month: YYYY-MM string

    Returns:
        float: decay multiplier between 0.25 and 1.00
    """
    if not event_date or len(event_date) < 7:
        return 0.50
    event_month = event_date[:7]
    if '-' not in event_month:
        return 0.50
    months = month_diff(event_month, target_month)
    if months <= 3:
        return 1.00
    elif months <= 6:
        return 0.85
    elif months <= 12:
        return 0.65
    elif months <= 18:
        return 0.45
    else:
        return 0.25


def map_pboc_pct_to_score(pboc_pct, stale_months):
    """Map PBOC percentage to a 0-100 score.

    Args:
        pboc_pct: Raw PBOC percentage (e.g., 5.4)
        stale_months: Number of months since last PBOC disclosure

    Returns:
        int: Score capped at 30 if data is stale (>=6 months)
    """
    if pboc_pct is None:
        return 0
    score = 0
    for threshold, s in PBOC_SCORE_MAP:
        if pboc_pct < threshold:
            score = s
            break
    if score == 0:
        score = 95
    if stale_months >= PBOC_STALE_MONTHS_THRESHOLD:
        score = min(score, PBOC_STALE_CAP)
    return score


def calc_pboc_freshness(pboc_latest_date_str, current_month):
    """Calculate PBOC data freshness metrics.

    Returns dict with stale_months, is_stale, data_status.
    """
    if not pboc_latest_date_str:
        return {"stale_months": 999, "is_stale": True, "data_status": "missing"}
    pboc_month = pboc_latest_date_str[:7]
    stale_months = month_diff(pboc_month, current_month)
    is_stale = stale_months >= PBOC_STALE_MONTHS_THRESHOLD
    data_status = "stale" if is_stale else "fresh"
    return {"stale_months": stale_months, "is_stale": is_stale, "data_status": data_status}


def calc_s_price(resale_mom_series):
    """Calculate S_Price based on resale home MoM index series.

    Args:
        resale_mom_series: List of resale_home_mom values (上月=100), chronological order.

    Returns:
        tuple: (score int, status str)
    """
    if len(resale_mom_series) < 6:
        return 0, "insufficient_data"

    last_3 = resale_mom_series[-3:]
    prev_3 = resale_mom_series[-6:-3]
    ma3 = sum(last_3) / 3.0
    prev_ma3 = sum(prev_3) / 3.0
    improvement = ma3 - prev_ma3
    min_last3 = min(last_3)

    if ma3 >= 100.2 and min_last3 >= 100.0:
        base = 90
    elif ma3 >= 100.0 and min_last3 >= 99.8:
        base = 78
    elif ma3 >= 99.7 and improvement > PRICE_IMPROVEMENT_EPSILON:
        base = 65
    elif ma3 >= 99.3 and improvement > PRICE_IMPROVEMENT_EPSILON:
        base = 52
    elif ma3 >= 99.0:
        base = 40
    else:
        base = 25

    if improvement > 0.2 + PRICE_IMPROVEMENT_EPSILON:
        base += 5
    if min_last3 >= 100.0:
        base += 5

    return min(base, 95), "ok"


def derive_city_qualification(conn, city_id, month):
    """Determine city qualification tier for a given month.

    Returns:
        'scored' if official/scraped price data exists for the month
               or for the most recent month within 1 month of the requested month
        'excluded' otherwise
    """
    cursor = conn.cursor()
    # First try exact month
    cursor.execute("""
        SELECT 1 FROM city_price_index_monthly
        WHERE city_id = ? AND month = ? AND data_status IN ('official', 'scraped')
    """, (city_id, month))
    if cursor.fetchone():
        return 'scored'
    # Fall back: check if city has recent data (within 1 month)
    cursor.execute("""
        SELECT month FROM city_price_index_monthly
        WHERE city_id = ? AND data_status IN ('official', 'scraped')
        ORDER BY month DESC LIMIT 1
    """, (city_id,))
    row = cursor.fetchone()
    if row:
        latest_month = row[0]
        # Parse months and check if within 1 month
        try:
            ym_req = [int(x) for x in month.split('-')]
            ym_latest = [int(x) for x in latest_month.split('-')]
            diff = (ym_req[0] - ym_latest[0]) * 12 + (ym_req[1] - ym_latest[1])
            if diff <= 1:
                return 'scored'
        except (ValueError, IndexError):
            pass
    return 'excluded'


def compute_and_store_all_scores(conn):
    """Compute and store all monthly Bottom Signal Scores using Low-Data Mode formula."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bottom_score_monthly")
    cursor.execute("DELETE FROM bottom_score_monthly WHERE city_id IN ('su', 'dg')")
    conn.commit()

    cursor.execute("SELECT id FROM cities")
    cities = [row[0] for row in cursor.fetchall()]

    months = []
    for year in [2024, 2025]:
        for month in range(1, 13):
            months.append(f"{year}-{month:02d}")
    for month in range(1, 7):
        months.append(f"2026-{month:02d}")

    stage_base_scores = {
        "政策表态": 10,
        "房源征集": 25,
        "正式招标": 45,
        "成交公示": 70,
        "签约收购": 90,
        "改造完成/配租配售": 100
    }
    stage_order = {"政策表态": 1, "房源征集": 2, "正式招标": 3, "成交公示": 4, "签约收购": 5, "改造完成/配租配售": 6}

    for cid in cities:
        if cid not in CORE_CITIES:
            continue

        for m in months:
            cursor.execute("SELECT listings, price_sqm FROM market_index WHERE city_id = ? AND date = ?", (cid, m))
            m_row = cursor.fetchone()
            listings_val = m_row[0] if m_row else -1
            listings_missing = (listings_val == -1)

            cursor.execute("SELECT resale_online_sign_units FROM city_transaction_monthly WHERE city_id = ? AND month = ?", (cid, m))
            tx_row = cursor.fetchone()
            tx_val = tx_row[0] if tx_row else None
            tx_missing = (tx_val is None or tx_val == 0)

            cursor.execute("""
                SELECT event_stage, event_date, discount_to_market, is_score_eligible
                FROM storage_execution_events
                WHERE city_id = ? AND substr(event_date, 1, 7) <= ?
            """, (cid, m))
            events = cursor.fetchall()

            storage_score = 0
            max_stage_val = 0
            discount_bonus = 0
            has_active_contract = False
            ev_stages = []

            if events:
                for ev_stage, ev_date, ev_discount, ev_eligible in events:
                    ev_stages.append(ev_stage)
                    if ev_eligible != 1 or ev_stage == "政策表态":
                        continue
                    base = stage_base_scores.get(ev_stage, 0)
                    decay = storage_recency_multiplier(ev_date, m)
                    weighted = base * decay
                    if weighted > storage_score:
                        storage_score = weighted
                    sv = stage_order.get(ev_stage, 0)
                    if sv > max_stage_val:
                        max_stage_val = sv
                    if ev_discount and 0.5 <= ev_discount <= 0.68:
                        discount_bonus = 10
                    if ev_eligible == 1 and ev_stage in ["签约收购", "改造完成/配租配售"] and ev_date and len(ev_date) >= 7 and '-' in ev_date[:7]:
                        md = month_diff(ev_date[:7], m)
                        if 0 <= md <= 6:
                            has_active_contract = True

            storage_score = int(storage_score + discount_bonus)
            storage_score = min(100, max(0, storage_score))

            cursor.execute("""
                SELECT date, percentage FROM pboc_global
                WHERE substr(date, 1, 7) <= ? ORDER BY date DESC LIMIT 1
            """, (m,))
            pboc_row = cursor.fetchone()
            pboc_pct = pboc_row[1] if pboc_row else 0.0
            pboc_date = pboc_row[0] if pboc_row else None

            pboc_fresh = calc_pboc_freshness(pboc_date, m)
            pboc_score = map_pboc_pct_to_score(pboc_pct, pboc_fresh["stale_months"])

            cursor.execute("""
                SELECT resale_home_mom FROM city_price_index_monthly
                WHERE city_id = ? AND month <= ?
                GROUP BY month
                ORDER BY month ASC
            """, (cid, m))
            price_rows = cursor.fetchall()
            resale_mom_series = [r[0] for r in price_rows if r[0] is not None]
            price_score, _ = calc_s_price(resale_mom_series)

            score_raw = 0.60 * price_score + 0.30 * storage_score + 0.10 * pboc_score
            score_raw = round(min(100.0, max(0.0, score_raw)), 2)
            score_final = score_raw

            status_raw = "下跌通道"
            if score_raw >= 85: status_raw = "底数据强信号观察"
            elif score_raw >= 75: status_raw = "政策价格共振"
            elif score_raw >= 60: status_raw = "价格止跌观察"
            elif score_raw >= 40: status_raw = "政策底观察"

            max_allowed_status = "底数据强信号观察"
            if not ev_stages:
                max_allowed_status = "价格止跌观察"
            else:
                if max_stage_val in [1, 2]:
                    max_allowed_status = "政策底观察"
                elif max_stage_val == 3:
                    max_allowed_status = "价格止跌观察"

            status_final = status_raw
            status_order_map = {"下跌通道": 1, "政策底观察": 2, "价格止跌观察": 3, "政策价格共振": 4, "底数据强信号观察": 5}
            if status_order_map.get(status_final, 0) > status_order_map.get(max_allowed_status, 0):
                status_final = max_allowed_status

            transaction_validation = "未验证 / 数据缺失" if tx_missing else "通过需求验证"
            supply_validation = "未验证" if listings_missing else "通过"
            storage_validation = "已通过签约执行" if has_active_contract else ("政策表态" if len(ev_stages) > 0 else "未验证")
            price_validation = "通过" if price_score >= 75 else "未通过"

            if tx_missing:
                validation_status = "未通过"
            elif listings_missing or not has_active_contract or price_score < 75:
                validation_status = "部分通过"
            else:
                validation_status = "通过需求验证"

            validation_reasons = []
            if not ev_stages:
                validation_reasons.append("无实质收储事件")
            elif max_stage_val in [1, 2]:
                validation_reasons.append("收储仅政策表态，缺少成交/签约执行")
            elif max_stage_val == 3:
                validation_reasons.append("收储仅招标阶段，缺少成交/签约执行")

            if tx_missing and listings_missing:
                validation_reasons.append("网签成交与挂牌供给缺失")
            else:
                if tx_missing:
                    validation_reasons.append("缺少网签成交、成交面积或去化周期验证")
                if listings_missing:
                    validation_reasons.append("挂牌量数据源失效或被隐藏")

            validation_reason = "；".join(validation_reasons) if validation_reasons else ""
            cap_reason = validation_reason

            pos_list = []
            neg_list = []
            if storage_score >= 75: pos_list.append("收储执行")
            elif storage_score < 40: neg_list.append("收储执行不力")

            if price_score >= 75: pos_list.append("价格止跌确认")
            elif price_score < 50: neg_list.append("价格止跌未确认")

            if pboc_score >= 70: pos_list.append("全国资金温度")
            elif pboc_score < 40: neg_list.append("全国资金温度不足")

            positive_drivers = ", ".join(pos_list) if pos_list else "无明显拉动项"
            negative_drivers = ", ".join(neg_list) if neg_list else "无明显拖累项"

            if validation_status == "通过需求验证":
                explanation = "底部信号多项共振，收储执行闭环，价格止跌得到验证。"
            elif status_final == "底数据强信号观察":
                explanation = "政策及价格信号偏强，但由于缺少完整网签/挂牌等需求侧支撑，列入底数据强信号观察。"
            elif status_final == "政策价格共振":
                explanation = "市场价格环比降幅收窄，且收储工作正在稳步推进，呈现政策与价格温和共振迹象。"
            elif status_final == "价格止跌观察":
                explanation = "核心挂牌价降幅边际收窄，但官方网签和收储实际落地仍需进一步确认观察。"
            elif status_final == "政策底观察":
                explanation = "收储及保障房支持政策相继出台，政策面触底清晰，但市场真实供求基本面仍待修复。"
            else:
                explanation = "价格环比持续承压下探，挂牌存量压力积压，周期底部筑底信号尚不明显。"

            city_qualification = derive_city_qualification(conn, cid, m)

            cursor.execute("""
                INSERT INTO bottom_score_monthly (
                    city_id, month, score_raw, score_final, status_raw, status_final,
                    is_true_bottom_candidate, cap_reason, positive_drivers, negative_drivers, explanation,
                    factor_policy, factor_supply, factor_demand, factor_price, factor_quality,
                    data_status, confidence_score, is_score_eligible, methodology_note,
                    validation_status, validation_reason, transaction_validation, supply_validation, storage_validation, price_validation,
                    scoring_mode, scoring_formula_version, formula_disclosure,
                    pboc_score, pboc_pct, pboc_stale_months, pboc_is_stale, pboc_data_status,
                    city_qualification, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cid, m, score_raw, score_final, status_raw, status_final, 0, cap_reason,
                  positive_drivers, negative_drivers, explanation,
                  storage_score, None, None, price_score, None,
                  "official", 80, 1, 'Low-Data Mode 三因子评分',
                  validation_status, validation_reason, transaction_validation, supply_validation, storage_validation, price_validation,
                  'low_data', 'BSS_LOW_DATA_V1', '0.60*S_Price + 0.30*S_Storage + 0.10*S_PBOC',
                  pboc_score, pboc_pct, pboc_fresh["stale_months"], 1 if pboc_fresh["is_stale"] else 0, pboc_fresh["data_status"],
                  city_qualification, datetime.now().isoformat()))

    conn.commit()


def compute_and_store_weekly_scores(conn):
    """Compute and store weekly Bottom Signal Scores (Monday-week grain).

    Strategy: carry over latest monthly BSS factors. If a city has new
    storage events within the current ISO week, recompute the storage
    factor and recompute the weekly score.
    """
    cursor = conn.cursor()
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")

    weekly_stage_scores = {
        "房源征集": 25,
        "正式招标": 45,
        "成交公示": 70,
        "签约收购": 90,
        "改造完成/配租配售": 100,
    }

    cursor.execute(
        "DELETE FROM weekly_bottom_score WHERE week_start < ?",
        (WEEKLY_SCORE_HISTORY_START,),
    )

    for cid in CORE_CITIES:
        cursor.execute("""
            SELECT score_final, factor_price, factor_policy, pboc_score
            FROM bottom_score_monthly
            WHERE city_id = ? ORDER BY month DESC LIMIT 1
        """, (cid,))
        row = cursor.fetchone()
        if not row:
            continue
        _, price_score, monthly_storage, pboc_score = row

        cursor.execute("""
            SELECT event_stage, event_date, is_score_eligible
            FROM storage_execution_events
            WHERE city_id = ? AND substr(event_date, 1, 10) >= ?
              AND substr(event_date, 1, 10) < date(?, '+7 days')
        """, (cid, week_start, week_start))
        events = cursor.fetchall()

        weekly_storage = 0
        for ev_stage, ev_date, ev_eligible in events:
            if ev_eligible != 1:
                continue
            base = weekly_stage_scores.get(ev_stage, 0)
            if base == 0:
                continue
            weighted = base * storage_recency_multiplier(ev_date, week_start)
            if weighted > weekly_storage:
                weekly_storage = weighted
        weekly_storage = int(weekly_storage)

        final_storage = max(monthly_storage or 0, weekly_storage)
        weekly_score = round(
            min(100.0, max(0.0, 0.60 * price_score + 0.30 * final_storage + 0.10 * pboc_score)),
            2,
        )
        data_source = "weekly_refresh" if events else "monthly_carryover"

        cursor.execute("""
            INSERT OR REPLACE INTO weekly_bottom_score
              (city_id, week_start, score, data_source, calculated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (cid, week_start, weekly_score, data_source, datetime.now().isoformat()))

    conn.commit()
