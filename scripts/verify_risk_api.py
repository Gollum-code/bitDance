"""端到端验证脚本：验证 risk_metrics 已接入 API。

用法：python scripts/verify_risk_api.py
会构造一段合成日线写入 vn.py 本地库，然后打真实 HTTP 接口，结束后自动清理。
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "trader"))

import importlib.util

_spec = importlib.util.spec_from_file_location("main", ROOT / "trader" / "main.py")
_main = importlib.util.module_from_spec(_spec)
sys.modules["main"] = _main
_spec.loader.exec_module(_main)

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database
from vnpy.trader.object import BarData


def seed_bars(symbol: str, exchange: Exchange, days: int = 400, seed: int = 42):
    """写入一段确定性合成日线到 vn.py 数据库。"""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0004, 0.012, days)
    price = 50.0
    bars = []
    start = datetime(2023, 1, 2)
    for i in range(days):
        price *= (1.0 + rets[i])
        dt = start + timedelta(days=i)
        o = price * (1.0 + rng.normal(0, 0.004))
        h = max(price, o) * (1.0 + abs(rng.normal(0, 0.005)))
        low = min(price, o) * (1.0 - abs(rng.normal(0, 0.005)))
        bars.append(
            BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                interval=Interval.DAILY,
                volume=float(rng.integers(10000, 50000)),
                turnover=float(rng.integers(10000, 50000)) * price,
                open_price=round(o, 3),
                high_price=round(h, 3),
                low_price=round(low, 3),
                close_price=round(price, 3),
                gateway_name="SEED",
            )
        )
    db = get_database()
    db.save_bar_data(bars)
    print(f"[seed] {symbol}.{exchange.value} -> {len(bars)} bars, last close {bars[-1].close_price}")


def cleanup_bars(symbol: str, exchange: Exchange) -> None:
    """删除本脚本写入的测试数据，避免污染本地库。"""
    try:
        get_database().delete_bar_data(symbol, exchange, Interval.DAILY)
        print(f"[cleanup] removed {symbol}.{exchange.value}")
    except Exception as e:
        print(f"[cleanup] {symbol}.{exchange.value} not removed: {e}")


def main():
    seed_bars("600999", Exchange.SSE, days=400)
    try:
        _run_checks()
    finally:
        cleanup_bars("600999", Exchange.SSE)


def _run_checks():

    from fastapi.testclient import TestClient

    app = _main.app
    client = TestClient(app)

    print("\n=== 1) 单策略回测（应带 risk_metrics / monthly_returns / risk_gate） ===")
    r = client.get(
        "/strategy/01",
        params={"vt_symbol": "600999.SSE", "start": "2023-01-01", "end": "2024-12-31", "capital": 100000},
    )
    print("status:", r.status_code)
    body = r.json()
    print("success:", body.get("success"), "| message:", body.get("message"))
    rm = body.get("risk_metrics") or {}
    print("risk_metrics keys:", sorted(rm.keys())[:12])
    print("sharpe:", rm.get("sharpe_ratio"), "| sortino:", rm.get("sortino_ratio"), "| calmar:", rm.get("calmar_ratio"))
    print("max_dd:", rm.get("max_drawdown_pct"), "| var95:", rm.get("var_95_pct"), "| cvar95:", rm.get("cvar_95_pct"))
    print("max_position_pct:", rm.get("max_position_pct"), "| exposure_days_ratio:", rm.get("exposure_days_ratio"))
    print("monthly_returns rows:", len(body.get("monthly_returns") or []))
    gate = body.get("risk_gate") or {}
    print("risk_gate verdict:", gate.get("verdict"), "| reasons:", gate.get("reasons"))

    print("\n=== 2) 参数网格寻优（objective=sharpe + 风控闸门） ===")
    r = client.post(
        "/analytics/grid",
        json={
            "strategy_id": "01",
            "param_name": "fast_window",
            "values": [5, 10, 15, 20, 30],
            "vt_symbol": "600999.SSE",
            "start": "2023-01-01",
            "end": "2024-12-31",
            "capital": 100000,
            "objective": "sharpe",
            "apply_risk_gate": True,
        },
    )
    print("status:", r.status_code)
    body = r.json()
    print("message:", body.get("message"))
    print("objective:", body.get("objective"), "| risk_gate_applied:", body.get("risk_gate_applied"),
          "| rejected:", body.get("risk_gate_rejected"))
    print("best:", body.get("best"))
    for c in (body.get("cells") or [])[:5]:
        if c.get("ok"):
            print(f"  fast_window={c['value']}: ret={c.get('total_return')}% sharpe={c.get('sharpe')} "
                  f"sortino={c.get('sortino')} dd={c.get('max_drawdown')} var95={c.get('var_95_pct')} "
                  f"gate_ok={c.get('gate_ok')}")

    print("\n=== 3) 多策略对比（应带 risk_summary） ===")
    r = client.post(
        "/analytics/compare",
        json={
            "strategy_ids": ["01", "09", "13"],
            "vt_symbol": "600999.SSE",
            "start": "2023-01-01",
            "end": "2024-12-31",
        },
    )
    print("status:", r.status_code)
    body = r.json()
    print("message:", body.get("message"))
    print("risk_summary:", body.get("risk_summary"))


if __name__ == "__main__":
    main()
