from datetime import date

import pandas as pd
import pytest

from analytics.curve import curve_nodes, interpolate_yield

NODES = {1: 4.0, 2: 4.2, 3: 4.3, 5: 4.4, 7: 4.6, 10: 4.8, 20: 5.0, 30: 5.2}


def test_exact_node_returns_that_yield():
    assert interpolate_yield(NODES, 5) == 4.4


def test_midpoint_is_linear():
    assert interpolate_yield(NODES, 6) == pytest.approx(4.5)


def test_clamps_below_one_year_and_above_thirty():
    assert interpolate_yield(NODES, 0.25) == 4.0
    assert interpolate_yield(NODES, 40) == 5.2


def test_skips_a_missing_middle_node():
    sparse = {key: value for key, value in NODES.items() if key != 7}
    assert interpolate_yield(sparse, 7.5) == pytest.approx(4.4 + (4.8 - 4.4) * (2.5 / 5))


def test_curve_nodes_use_the_latest_print_on_or_before_the_date():
    yields = pd.DataFrame(
        [
            {"date": date(2026, 11, 10), "maturity_years": 1, "yield_percent": 4.0},
            {"date": date(2026, 11, 12), "maturity_years": 1, "yield_percent": 4.1},
            {"date": date(2026, 11, 13), "maturity_years": 1, "yield_percent": 9.9},
            {"date": date(2026, 11, 12), "maturity_years": 30, "yield_percent": 5.0},
        ]
    )
    assert curve_nodes(yields, date(2026, 11, 12)) == {1.0: 4.1, 30.0: 5.0}
