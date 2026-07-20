#!/usr/bin/env python3
"""Regression test for price-score floating point boundaries."""

import os
import sys
from math import inf, nextafter

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)
from china_housing_monitor.scoring.factors import calc_s_price


def test_flat_three_month_average_does_not_count_as_improvement():
    series = [
        nextafter(99.6, -inf),
        nextafter(99.8, -inf),
        nextafter(99.7, -inf),
        99.9,
        99.6,
        99.6,
    ]

    score, status = calc_s_price(series)

    assert status == "ok"
    assert score == 40


if __name__ == "__main__":
    test_flat_three_month_average_does_not_count_as_improvement()
    print("✓ flat three-month average remains at the non-improving price score")
