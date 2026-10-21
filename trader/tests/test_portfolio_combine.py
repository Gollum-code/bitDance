"""组合回测的核心纯函数测试。

重点覆盖两个曾经出过错的地方：
  1. 名义金额 → 股数换算（固定股数会让不同价位的标的权重失真）
  2. sleeve 收益合成（名义金额模式下不能再乘权重，否则权重被平方）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routers.analytics import combine_sleeve_returns, shares_for_notional  # noqa: E402


class TestSharesForNotional:
    def test_equal_notional_different_prices(self):
        """不同价位的标的必须得到相近的名义金额，而不是相近的股数。"""
        symbols = ["A", "B", "C"]
        prices = [7.0, 70.0, 1750.0]
        notionals = [125_000.0] * 3

        shares = shares_for_notional(symbols, notionals, prices)

        assert set(shares) == {"A", "B", "C"}
        for s, px in zip(symbols, prices):
            assert abs(shares[s] * px - 125_000.0) / 125_000.0 < 0.01

    def test_skips_invalid_price(self):
        assert shares_for_notional(["A", "B"], [1000.0, 1000.0], [10.0, None]) == {"A": 100}

    def test_skips_non_positive_price(self):
        assert shares_for_notional(["A", "B"], [1000.0, 1000.0], [10.0, 0.0]) == {"A": 100}

    def test_skips_non_positive_notional(self):
        assert shares_for_notional(["A"], [0.0], [10.0]) == {}
        assert shares_for_notional(["A"], [-5.0], [10.0]) == {}

    def test_minimum_one_share(self):
        """名义金额很小或价格极高时至少 1 股，避免 0 股导致策略不下单。"""
        assert shares_for_notional(["A"], [100.0], [1750.0]) == {"A": 1.0}


class TestCombineSleeveReturns:
    def test_sum_mode_equals_equal_weight_portfolio(self):
        """名义金额模式：每个 sleeve 的收益已含 1/n 权重，直接求和即组合收益。"""
        n = 4
        date_rets = {
            "A": {"d1": 0.01 / n, "d2": 0.02 / n},
            "B": {"d1": 0.03 / n, "d2": -0.01 / n},
            "C": {"d1": -0.02 / n, "d2": 0.04 / n},
            "D": {"d1": 0.00 / n, "d2": 0.01 / n},
        }
        weights = {s: 1.0 / n for s in date_rets}

        _, port = combine_sleeve_returns(date_rets, weights, use_sum=True)

        assert port[0] == pytest.approx((0.01 + 0.03 - 0.02 + 0.00) / n)
        assert port[1] == pytest.approx((0.02 - 0.01 + 0.04 + 0.01) / n)

    def test_sum_mode_does_not_square_weights(self):
        """回归：如果求和模式再乘一次权重，结果会被压成 1/n（旧的错误）。"""
        date_rets = {"A": {"d1": 0.5}, "B": {"d1": 0.5}}
        weights = {"A": 0.5, "B": 0.5}

        _, port = combine_sleeve_returns(date_rets, weights, use_sum=True)

        assert port[0] == pytest.approx(1.0)
        assert port[0] != pytest.approx(0.5)

    def test_weighted_mode_keeps_legacy_behavior(self):
        date_rets = {"A": {"d1": 0.10}, "B": {"d1": 0.20}}
        weights = {"A": 0.25, "B": 0.75}

        _, port = combine_sleeve_returns(date_rets, weights, use_sum=False)

        assert port[0] == pytest.approx(0.25 * 0.10 + 0.75 * 0.20)

    def test_missing_dates_fill_zero(self):
        date_rets = {"A": {"d1": 0.1}, "B": {"d2": 0.2}}
        weights = {"A": 0.5, "B": 0.5}

        dates, port = combine_sleeve_returns(date_rets, weights, use_sum=True)

        assert dates == ["d1", "d2"]
        assert port == pytest.approx([0.1, 0.2])

    def test_dates_sorted_and_union(self):
        date_rets = {"A": {"2024-01-02": 0.1}, "B": {"2024-01-01": 0.2}}
        _, port = combine_sleeve_returns(date_rets, {"A": 0.5, "B": 0.5}, use_sum=True)

        assert port == pytest.approx([0.2, 0.1])

    def test_empty_input(self):
        assert combine_sleeve_returns({}, {}, use_sum=True) == ([], [])
        assert combine_sleeve_returns({}, {}, use_sum=False) == ([], [])
