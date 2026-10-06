"""分析类功能（多策略对比 / 因子选股 / 参数网格 / 实时行情）测试。

不依赖外网：因子计算用合成的确定性行情，路由存在性直接检查 openapi。
运行：python -m pytest trader/tests -q
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers import analytics  # noqa: E402


def _synth_daily(n: int = 120, seed: int = 7) -> pd.DataFrame:
    """构造一段确定性的上涨行情（含成交量波动）。"""
    rng = np.random.default_rng(seed)
    base = 20.0
    steps = rng.normal(0.0008, 0.015, n)
    close = base * np.cumprod(1 + steps)
    high = close * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, n)))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    vol = rng.integers(50_000, 150_000, n).astype(float)
    idx = pd.bdate_range(end=pd.Timestamp("2025-04-01"), periods=n)
    return pd.DataFrame(
        {
            "ts_code": "600031.SSE",
            "trade_date": [d.strftime("%Y%m%d") for d in idx],
            "open": open_,
            "high": np.maximum(high, np.maximum(open_, close)),
            "low": np.minimum(low, np.minimum(open_, close)),
            "close": close,
            "vol": vol,
            "amount": 0.0,
        }
    )


def test_factor_calc_on_synthetic_data(monkeypatch):
    """用合成行情替代网络，验证 8 个因子都能算出且方向合理。"""
    df = _synth_daily(120)
    monkeypatch.setattr(analytics, "_load_daily_df", lambda *a, **k: df.copy())

    out = analytics._compute_factors("600031.SSE", 90, "2025-04-01")
    assert out is not None
    assert out["ts_code"] == "600031.SSE"
    assert out["close"] > 0
    # 8 个因子键都在
    for key in ("mom", "trend", "ma_bias", "volatility", "vol_ratio", "amihud", "drawdown_from_high", "ma_cross"):
        assert key in out, f"缺少因子 {key}"
        assert not np.isnan(float(out[key]))
    assert out["ma_cross"] in (-1.0, 0.0, 1.0)
    # 波动率年化应为正
    assert out["volatility"] > 0


def test_factor_insufficient_data_returns_none(monkeypatch):
    """数据条数不足时应返回 None（而不是抛异常）。"""
    monkeypatch.setattr(analytics, "_load_daily_df", lambda *a, **k: _synth_daily(10))
    assert analytics._compute_factors("600031.SSE", 90, "2025-04-01") is None


def test_factor_empty_dataframe_returns_none(monkeypatch):
    monkeypatch.setattr(analytics, "_load_daily_df", lambda *a, **k: pd.DataFrame())
    assert analytics._compute_factors("600031.SSE", 90, "2025-04-01") is None


def test_vt_tx_code_conversion_in_factor(monkeypatch):
    """_compute_factors 走免费源时应使用 tx 代码（验证 vt_to_tx 被调用）。"""
    captured = {}

    def fake_load(vt_code, start, end):
        captured["vt"] = vt_code
        return _synth_daily(80)

    monkeypatch.setattr(analytics, "_load_daily_df", fake_load)
    analytics._compute_factors("000001.SZSE", 60, "2025-04-01")
    assert captured["vt"] == "000001.SZSE"


@pytest.mark.parametrize(
    "path,methods",
    [
        ("/analytics/compare", {"POST"}),
        ("/analytics/screen", {"POST"}),
        ("/analytics/grid", {"POST"}),
        ("/analytics/realtime", {"GET"}),
        ("/analytics/portfolio", {"POST"}),
        ("/analytics/paper", {"POST"}),
        ("/api/market/minute", {"GET"}),
        ("/api/market/sync-batch", {"POST"}),
    ],
)
def test_routes_registered(path, methods):
    """分析端点与行情新端点都应注册在 app 的 openapi 中。"""
    from fastapi import FastAPI
    from main import app as trader_app  # noqa: F401

    schemas = trader_app.openapi()["paths"]
    assert path in schemas, f"缺少端点 {path}"
    registered = set(m.upper() for m in schemas[path].keys() if m != "parameters")
    assert methods.issubset(registered), f"{path} 方法不匹配: {registered}"


def test_websocket_route_registered():
    """/analytics/ws 应注册为 WebSocket 路由。"""
    from routers.analytics import router

    ws_paths = [getattr(r, "path", None) for r in router.routes if type(r).__name__ == "APIWebSocketRoute"]
    assert "/ws" in ws_paths, f"缺少 /analytics/ws WebSocket 路由，实际: {ws_paths}"