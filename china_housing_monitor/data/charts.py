"""Chart-related data assembly and analysis helpers.

Contains functions that compute chart visibility, evidence grades,
risk levels, signal strength, and other analytical metrics used
by the data payload to enrich city entries for the HTML report.
"""


def compute_chart_visibility(transaction_history, market_history):
    """Determine which charts have enough valid data points to display.

    A chart is visible if it has at least 3 valid (non-suppressed, non-demo) data points.

    Returns:
        dict: {"transaction": bool, "listings": bool, "price": bool}
    """
    tx_valid_count = 0
    for tx in transaction_history:
        val = tx.get("resale_online_sign_units")
        if val is not None and val != -1 and val != 0 and not isinstance(val, str):
            tx_valid_count += 1

    listings_valid_count = 0
    for m in market_history:
        val = m.get("listings")
        status = m.get("listings_status", "scraped")
        if val is not None and val != -1 and val != 0 and status not in ["demo", "synthetic", "estimated"]:
            listings_valid_count += 1

    price_valid_count = 0
    for m in market_history:
        val = m.get("price_sqm")
        status = m.get("price_status", "scraped")
        if val is not None and val != -1 and val != 0 and status not in ["demo", "synthetic", "estimated"]:
            price_valid_count += 1

    return {
        "transaction": tx_valid_count >= 3,
        "listings": listings_valid_count >= 3,
        "price": price_valid_count >= 3
    }


def compute_suppressed_metrics(chart_visibility):
    """Build list of metric labels that are hidden due to insufficient data.

    Returns:
        list[str]: Chinese labels of suppressed metrics
    """
    suppressed_metrics = []
    if not chart_visibility["transaction"]:
        suppressed_metrics.append("网签成交数据")
    if not chart_visibility["listings"]:
        suppressed_metrics.append("前台挂牌数据")
    suppressed_metrics.append("去化周期数据")
    return suppressed_metrics


def compute_signal_validation_coverage(chart_visibility, price_index_history, storage_execution_history):
    """Compute signal coverage and validation coverage percentages.

    Core signals: PBOC (always 1), price index, storage events
    Validation signals: transaction chart, listings chart, (price chart not counted)

    Returns:
        tuple: (signal_coverage_pct, validation_coverage_pct)
    """
    num_core_signals = 1  # PBOC always available
    if len(price_index_history) > 0:
        num_core_signals += 1
    if len(storage_execution_history) > 0:
        num_core_signals += 1
    signal_coverage_pct = round((num_core_signals / 3.0) * 100, 2)

    num_validation_signals = 0
    if chart_visibility["transaction"]:
        num_validation_signals += 1
    if chart_visibility["listings"]:
        num_validation_signals += 1
    validation_coverage_pct = round((num_validation_signals / 3.0) * 100, 2)

    return signal_coverage_pct, validation_coverage_pct


def compute_evidence_grade(signal_coverage_pct, validation_coverage_pct,
                           estimated_demo_ratio, num_core_signals, pboc_is_stale):
    """Resolve the evidence grade (A-E) based on coverage and data quality.

    Grades:
        A: High signal + high validation + no estimated data
        B: High signal + medium validation + low estimated
        C: Good signal + low validation + low estimated
        D: Partial signal or only 2 core signals
        E: Low signal or <2 core signals or high estimated

    PBOC staleness caps the grade at C.

    Returns:
        str: Single letter grade A-E
    """
    if signal_coverage_pct >= 90.0 and validation_coverage_pct >= 80.0 and estimated_demo_ratio == 0:
        evidence_grade = "A"
    elif signal_coverage_pct >= 90.0 and 40.0 <= validation_coverage_pct < 80.0 and estimated_demo_ratio < 10:
        evidence_grade = "B"
    elif signal_coverage_pct >= 80.0 and validation_coverage_pct < 40.0 and estimated_demo_ratio < 20:
        evidence_grade = "C"
    elif (40.0 <= signal_coverage_pct < 80.0) or num_core_signals == 2:
        evidence_grade = "D"
    elif signal_coverage_pct < 40.0 or num_core_signals < 2 or estimated_demo_ratio >= 20:
        evidence_grade = "E"
    else:
        evidence_grade = "E"

    # PBOC stale caps evidence grade at C
    if pboc_is_stale:
        grade_order = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1}
        evidence_grade = min(evidence_grade, "C", key=lambda g: grade_order.get(g, 1))

    return evidence_grade


def get_highest_storage_stage(storage_history):
    """Find the most advanced storage execution stage from event history.

    Returns:
        str: Chinese label of the highest stage, or "无收储进驻" if no events
    """
    if not storage_history:
        return "无收储进驻"
    stage_weights = {
        "政策表态": 10,
        "房源征集": 25,
        "正式招标": 45,
        "成交公示": 70,
        "签约收购": 90,
        "改造完成/配租配售": 100
    }
    highest_stage = "政策表态"
    highest_weight = 0
    for event in storage_history:
        stage = event.get("stage", "政策表态")
        weight = stage_weights.get(stage, 0)
        if weight > highest_weight:
            highest_weight = weight
            highest_stage = stage
    return highest_stage


def compute_risk_level(status, pboc_is_stale):
    """Resolve objective risk level based on bottom status.

    Returns:
        str: Chinese risk level label
    """
    risk_level = "极高风险"
    if status == "底数据强信号观察": risk_level = "较低风险"
    elif status == "政策价格共振": risk_level = "中等风险"
    elif status == "价格止跌观察": risk_level = "中等风险"
    elif status == "政策底观察": risk_level = "高风险"

    # PBOC stale raises risk floor
    if pboc_is_stale:
        risk_order = {"较低风险": 1, "中等风险": 2, "中高风险": 3, "高风险": 4, "极高风险": 5}
        current_risk_val = risk_order.get(risk_level, 5)
        if current_risk_val < 3:
            risk_level = "中高风险"

    return risk_level


def compute_signal_strength(score_val):
    """Map score value to signal strength label.

    Returns:
        str: Chinese signal strength label
    """
    signal_strength = "极弱"
    if score_val >= 85: signal_strength = "极强"
    elif score_val >= 75: signal_strength = "强"
    elif score_val >= 60: signal_strength = "中等"
    elif score_val >= 40: signal_strength = "弱"
    return signal_strength


def generate_signal_interpretation(city, rank, total_cities, pboc_is_stale):
    """Generate human-readable signal interpretation for a city.

    Returns:
        dict with keys: position, rank_str, positives, negatives, next_steps
    """
    factors = city.get("factors", {})
    price_score = factors.get("price", 0)
    storage_score = factors.get("storage", 0)
    pboc_score = factors.get("pboc", 0)
    status = city.get("bottom_status", "")
    risk_level = city.get("risk_level", "")
    signal_strength = city.get("signal_strength", "")
    evidence_grade = city.get("evidence_grade", "E")
    tx_missing = city.get("indicators", {}).get("tx_missing", True)
    listings_missing = city.get("indicators", {}).get("listings_missing", True)
    highest_stage = city.get("highest_storage_stage", "无收储进驻")
    price_history = city.get("price_index_history", [])

    # Position summary
    position = f"{status} · {risk_level} · 信号{signal_strength}"
    rank_str = f"{rank}/{total_cities}"

    # Positives
    positives = []
    if price_score >= 75:
        positives.append("二手房价格环比企稳，降幅持续收窄")
    elif price_score >= 60:
        positives.append("二手房环比降幅收窄，价格边际改善")
    if storage_score >= 60:
        positives.append(f"收储进入「{highest_stage}」阶段，有实质签约")
    elif storage_score >= 25:
        positives.append(f"已有收储进驻（{highest_stage}），政策端有动作")
    if not pboc_is_stale and pboc_score >= 55:
        positives.append("央行保障房再贷款资金温度充足")
    if not positives:
        positives.append("暂无明显积极信号")

    # Negatives
    negatives = []
    if storage_score < 40:
        if highest_stage in ["政策表态", "房源征集"]:
            negatives.append(f"收储仅「{highest_stage}」，无实质签约划款")
        elif highest_stage == "无收储进驻":
            negatives.append("尚无收储事件进驻")
    if tx_missing:
        negatives.append("网签成交数据缺失，价格未经成交量验证")
    if listings_missing:
        negatives.append("挂牌量数据源失效，供给端无法追踪")
    if price_score < 50:
        negatives.append("二手房价格仍在下行通道")
    if pboc_is_stale:
        negatives.append("央行资金温度数据已过期，仅作历史参考")

    # Next steps
    next_steps = []
    if storage_score < 60:
        next_steps.append("收储从征集/表态进入「签约收购」阶段")
    if tx_missing:
        next_steps.append("当地住建局披露官方网签成交数据")
    if listings_missing:
        next_steps.append("链家/贝壳挂牌数据恢复可查")
    if price_score < 75:
        next_steps.append("NBS 二手房环比连续 3 个月 ≥ 100")
    if pboc_is_stale:
        next_steps.append("央行披露最新季度再贷款使用数据")
    if not next_steps:
        next_steps.append("当前数据已较完整，持续跟踪即可")

    return {
        "position": position,
        "rank_str": rank_str,
        "evidence_grade": evidence_grade,
        "positives": positives,
        "negatives": negatives,
        "next_steps": next_steps
    }

