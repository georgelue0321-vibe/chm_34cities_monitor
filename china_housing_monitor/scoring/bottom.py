"""Bottom score computation, warnings, and city status timeline.

Contains functions that build on the scoring factors to determine city status:
- compute_bottom_score(): Read-only wrapper to fetch pre-computed scores
- generate_warnings(): Analytical False Bottom Warning Flags
- decide_city_status_timeline(): Full historical timeline of scores
"""


def compute_bottom_score(conn, city_id, month):
    """Read-only wrapper: fetch pre-computed score from bottom_score_monthly."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT score_final, factor_policy AS storage, factor_price AS price,
               pboc_score AS pboc, validation_status, calculated_at,
               scoring_mode, scoring_formula_version
        FROM bottom_score_monthly
        WHERE city_id = ? AND month = ?
    """, (city_id, month))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "score": row[0],
        "storage": row[1],
        "price": row[2],
        "pboc": row[3],
        "validation_status": row[4],
        "calculated_at": row[5],
        "scoring_mode": row[6],
        "scoring_formula_version": row[7],
    }


def generate_warnings(city, timeline):
    """Generate analytical False Bottom Warning Flags based on actual datastore rules."""
    warnings = []
    latest = timeline[-1]

    factors = latest["factors"]
    tx_missing = city.get("tx_missing", False)
    listings_missing = city.get("listings_missing", False)

    # A. Market Signal Warnings
    # 1. 价格上涨但成交下跌 (Price Up, Volume Down) — only in full-data mode
    demand_score = factors.get("demand")
    supply_score = factors.get("supply")
    if not tx_missing and factors["price"] > 60 and demand_score is not None and demand_score < 50:
        warnings.append({
            "category": "signal",
            "type": "warning",
            "title": "假底预警：挂牌价格微弹，但网签交易底气不足",
            "desc": "本月该城市挂牌价略有回暖折返，但官方网签成交量未能实现同步修复，通常属于低价房源消耗后的统计反弹，缺乏量能支撑，周期性反弹未能确认。"
        })

    # 2. 成交上涨但挂牌暴增 (Volume Up, Inventory Surging) — only in full-data mode
    if not listings_missing and demand_score is not None and demand_score > 70 and supply_score is not None and supply_score < 40:
        warnings.append({
            "category": "signal",
            "type": "caution",
            "title": "假底预警：网签成交回升，但二手房挂牌抛售压力积压",
            "desc": "虽然地方降息刺激网签温和放量，但房东降价出逃意愿强烈，导致二手住宅新增挂牌总量同步暴增，去化压力不降反升，需警惕虚假反弹信号。"
        })

    # 3. 收储阶段提示
    highest_stage = city.get("highest_storage_stage", "无收储进驻")
    if highest_stage == "政策表态":
        warnings.append({
            "category": "signal",
            "type": "info",
            "title": "提示：收储仅政策表态，无实质签约进展",
            "desc": "该城市收储停留在政策表态阶段，尚未进入房源征集或招标流程，更无实质签约划款。建议关注是否有征集公告发布。"
        })
    elif highest_stage in ["房源征集", "正式招标"]:
        warnings.append({
            "category": "signal",
            "type": "info",
            "title": "提示：收储停留在征集/招标阶段，尚无签约",
            "desc": "该城市已有收储征集或招标动作，但尚未产生成交公示或签约收购。政策端有推进，交易闭环仍待确认。"
        })
    elif highest_stage in ["成交公示", "签约收购", "改造完成/配租配售"]:
        warnings.append({
            "category": "signal",
            "type": "positive",
            "title": "积极信号：收储已进入签约执行阶段",
            "desc": "该城市收储已产生实质签约或成交，政策资金正在落地。需持续关注签约规模和改造交付进度。"
        })

    # PBOC progress low
    if factors.get("pboc", 29.2) < 40.0:
        warnings.append({
            "category": "signal",
            "type": "caution",
            "title": "资金预警：全国保障房再贷款额度使用进展偏低",
            "desc": "当前全国保障房再贷款实际额度使用比率尚在 40% 以下低位温度区间，资金投放对核心城市的兜底规模有待进一步扩容。"
        })

    # 5. 价格环比转正但同比仍深跌
    mom_stabilized = factors["price"] > 75
    yoy_deep_drop = any(e.get("resale_home_yoy", 100.0) < 92.0 for e in city.get("price_index_history", [])[-2:])
    if mom_stabilized and yoy_deep_drop:
        warnings.append({
            "category": "signal",
            "type": "info",
            "title": "价格警示：住宅环比降幅收窄，但同比跌幅依旧深企",
            "desc": "虽然官方二手房住宅环比跌幅持续收窄，但由于近两年存量压力积重难返，同比依然深陷 8% 以上的深跌区间，周期寻底尚未画上句号。"
        })

    # B. Data Coverage Warnings
    # 4. 估算数据占比过高 (High Estimated Data)
    est_ratio = latest.get("estimated_demo_ratio", 0)
    if est_ratio >= 20.0:
        warnings.append({
            "category": "coverage",
            "type": "warning",
            "title": "数据可信度预警：估算及测试数据占比过高，触发状态封顶",
            "desc": "本月该市数据估算及拟真指标占比超过 20%，评分可信度受限，仅作参考。"
        })

    # Data Coverage: combined missing data warning
    missing_parts = []
    if tx_missing:
        missing_parts.append("网签成交")
    if listings_missing:
        missing_parts.append("挂牌量")
    missing_ratio = latest.get("missing_ratio", 0)
    if missing_parts:
        title = "数据缺失预警：" + "、".join(missing_parts) + "数据未接入"
        desc = f"本月该市{'、'.join(missing_parts)}数据缺失或未接入（缺失占比 {missing_ratio:.0f}%），价格信号缺乏成交验证，供给侧缓释难以判定，建议谨慎参考。"
        warnings.append({
            "category": "coverage",
            "type": "warning",
            "title": title,
            "desc": desc
        })
    elif missing_ratio >= 20.0:
        warnings.append({
            "category": "coverage",
            "type": "warning",
            "title": "数据覆盖不足预警",
            "desc": f"本月该市数据缺失占比达到 {missing_ratio:.0f}%，建议谨慎参考评估结果。"
        })
    # Always append inventory cycle warning since cycle data is not integrated
    warnings.append({
        "category": "coverage",
        "type": "info",
        "title": "去化周期数据未接入，周期底部确认度受限",
        "desc": "该市目前的住宅去化周期与存量积压周期数据未接入，周期底部供需平衡转折点的确认度受到限制。"
    })
    return warnings


def decide_city_status_timeline(conn, city_id, target_month):
    """Retrieve full historical timeline of pre-calculated scores and statuses from bottom_score_monthly."""
    cursor = conn.cursor()
    cursor.execute("""
    SELECT month, score_raw, score_final, status_raw, status_final,
           cap_reason, positive_drivers, negative_drivers, explanation,
           factor_policy, factor_price, pboc_score, pboc_pct,
           data_status, confidence_score, is_score_eligible,
           validation_status, validation_reason, transaction_validation, supply_validation, storage_validation, price_validation,
           scoring_mode, scoring_formula_version, formula_disclosure,
           pboc_stale_months, pboc_is_stale, city_qualification, calculated_at
    FROM bottom_score_monthly
    WHERE city_id = ? AND month <= ?
    ORDER BY month ASC
    """, (city_id, target_month))
    rows = cursor.fetchall()

    timeline = []
    for r in rows:
        m = r[0]
        cursor.execute("SELECT value_status FROM data_quality_log WHERE city_id = ? AND period = ?", (city_id, m))
        qual_rows = cursor.fetchall()
        qual_statuses = [qr[0] for qr in qual_rows]
        est_missing_count = sum(1 for s in qual_statuses if s in ["estimated", "demo", "missing", "abnormal", "synthetic"])
        est_missing_pct = (est_missing_count / len(qual_statuses) * 100) if qual_statuses else 0.0

        timeline.append({
            "date": m,
            "score": r[2],
            "status": r[4],
            "is_capped": (r[5] != ""),
            "cap_reason": r[5],
            "positive_drivers": r[6],
            "negative_drivers": r[7],
            "explanation": r[8],
            "est_pct": est_missing_pct,
            "validation_status": r[16],
            "validation_reason": r[17],
            "transaction_validation": r[18],
            "supply_validation": r[19],
            "storage_validation": r[20],
            "price_validation": r[21],
            "scoring_mode": r[22],
            "scoring_formula_version": r[23],
            "formula_disclosure": r[24],
            "pboc_stale_months": r[25],
            "pboc_is_stale": bool(r[26]),
            "city_qualification": r[27],
            "calculated_at": r[28],
            "factors": {
                "storage": r[9] if r[9] is not None else 0,
                "price": r[10] if r[10] is not None else 0,
                "pboc": r[11] if r[11] is not None else 0,
                "pboc_pct": r[12] if r[12] is not None else 0,
                "score": r[2]
            }
        })
    return timeline
