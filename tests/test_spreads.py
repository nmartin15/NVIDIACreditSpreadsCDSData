from datetime import date

import pandas as pd
import pytest

from analytics.spreads import (
    approx_par_spread_bp,
    coupon_bp_from_fixed_rate,
    daily_bond_yields,
    g_spread_bp,
    parse_notional,
    upfront_points,
    years_to_maturity,
)


def test_g_spread_converts_a_percent_gap_into_basis_points():
    assert g_spread_bp(5.5, 4.0) == pytest.approx(150)


def test_years_to_maturity_uses_365_25_day_years():
    years = years_to_maturity(date(2027, 1, 1), date(2026, 1, 1))
    assert years == pytest.approx(365 / 365.25)


def test_fixed_rate_decimal_is_a_coupon_in_basis_points():
    assert coupon_bp_from_fixed_rate(0.01) == pytest.approx(100)
    assert coupon_bp_from_fixed_rate(0.05) == pytest.approx(500)


def test_capped_notional_is_not_treated_as_a_real_size():
    assert parse_notional("5,000,000+") is None
    assert parse_notional("1,000,000") == 1_000_000


def test_odd_lots_are_dropped_and_the_rest_are_weighted():
    prints = pd.DataFrame(
        [
            {
                "trade_date": date(2026, 11, 1),
                "ticker": "NVDA",
                "label": "A",
                "maturity": date(2036, 1, 1),
                "yield_percent": 6.0,
                "size_par": 50_000,
                "price": 90,
            },
            {
                "trade_date": date(2026, 11, 1),
                "ticker": "NVDA",
                "label": "A",
                "maturity": date(2036, 1, 1),
                "yield_percent": 5.0,
                "size_par": 100_000,
                "price": 95,
            },
            {
                "trade_date": date(2026, 11, 1),
                "ticker": "NVDA",
                "label": "A",
                "maturity": date(2036, 1, 1),
                "yield_percent": 7.0,
                "size_par": 300_000,
                "price": 96,
            },
        ]
    )
    daily = daily_bond_yields(prints)
    assert len(daily) == 1
    assert daily.iloc[0]["yield_percent"] == pytest.approx((5 * 100_000 + 7 * 300_000) / 400_000)


def test_approx_par_spread_uses_points_and_a_4_5_year_duration():
    points = upfront_points(74_208, 5_000_000)
    assert points == pytest.approx(1.48416)
    assert approx_par_spread_bp(100, points) == pytest.approx(100 + (points * 100) / 4.5)
