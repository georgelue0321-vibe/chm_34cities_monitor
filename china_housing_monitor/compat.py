"""
Backward compatibility shim for tests.

This module re-exports all public APIs from the new submodules so that
existing code using `import china_housing_monitor` continues to work.
"""

# Re-export config
from .config import (
    SCRIPT_DIR, WORKSPACE, DB_PATH, REPORT_PATH,
    CORE_CITIES, BSS_LOW_DATA_V1, PBOC_SCORE_MAP,
    PBOC_STALE_CAP, PBOC_STALE_MONTHS_THRESHOLD,
    DATA_STATUS_LABELS, compute_event_hash
)

# Re-export DB functions
from .db.init import backup_db, add_column_if_not_exists, init_db
from .db.seed import seed_historical_data

# Re-export scoring functions
from .scoring.factors import (
    resolve_current_month, month_diff, storage_recency_multiplier,
    map_pboc_pct_to_score, calc_pboc_freshness, calc_s_price,
    derive_city_qualification, compute_and_store_all_scores
)
from .scoring.bottom import (
    compute_bottom_score, generate_warnings, decide_city_status_timeline
)

# Re-export crawler functions
from .crawler import crawl_city_market_data, update_all_cities_market_data

# Re-export data functions
from .data.payload import fetch_data_payload
from .data.charts import (
    compute_chart_visibility, compute_suppressed_metrics,
    compute_signal_validation_coverage, compute_evidence_grade,
    get_highest_storage_stage, compute_risk_level, compute_signal_strength
)

# Re-export report generator
from .report.generator import generate_html_report
