"""用真实行情（腾讯公开源）跑回测，产出可写进简历的真实指标。

策略：
  1. 拉取真实前复权日线（不覆盖你库里已有的标的，只新增）
  2. 写入 vn.py 本地库
  3. 批量回测多个策略族，输出完整风险指标
  4. 打印同期买入持有基准，便于算超额收益

用法：python scripts/collect_real_metrics.py
"""
import sys
import importlib.util
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "trader"))

_spec = importlib.util.spec_from_file_location("main", ROOT / "trader" / "main.py")
_main = importlib.util.module_from_spec(_spec)
sys.modules["main"] = _main
_spec.loader.exec_module(_main)

from routers.analytics import _run_backtest  # noqa: E402
from routers.free_market import fetch_daily, tx_to_vt  # noqa: E402
from routers.tushare_bars import bars_from_tushare_daily_df, save_bars_to_database  # noqa: E402

SYMBOL_TX = "sh601318"
SYMBOL_VT = "601318.SSE"
CAPITAL = 100_000
FIXED_SIZE = 500
STRATEGIES = ["27", "08", "09", "04", "13", "37", "22", "15"]


def main():
    df = fetch_daily(SYMBOL_TX, "2022-01-01", "2026-10-09")
    if df is None or df.empty:
        print("无法获取行情，退出")
        return
    df = df.sort_values("trade_date").reset_index(drop=True)
    start_d = str(df["trade_date"].iloc[0])
    end_d = str(df["trade_date"].iloc[-1])
    start = f"{start_d[:4]}-{start_d[4:6]}-{start_d[6:]}"
    end = f"{end_d[:4]}-{end_d[4:6]}-{end_d[6:]}"

    closes = df["close"].astype(float).to_numpy()
    print(f"REAL_DATA {SYMBOL_VT} {start} ~ {end} rows={len(df)} "
          f"first={closes[0]:.3f} last={closes[-1]:.3f} min={closes.min():.3f} max={closes.max():.3f}")

    save_bars_to_database(bars_from_tushare_daily_df(df))
    print(f"SAVED to vn.py db: {len(df)} bars")

    # 基准：同期买入持有
    bh = closes[-1] / closes[0] - 1.0
    yrs = len(closes) / 252.0
    bh_ann = (1 + bh) ** (1 / yrs) - 1 if yrs > 0 else 0.0
    rets = np.diff(closes) / closes[:-1]
    bh_vol = float(np.std(rets, ddof=1) * np.sqrt(252))
    bh_dd = float(np.min(closes / np.maximum.accumulate(closes) - 1))
    print(f"BENCHMARK buyhold total={bh*100:.2f}% ann={bh_ann*100:.2f}% "
          f"vol={bh_vol*100:.2f}% maxdd={bh_dd*100:.2f}%")

    print(f"\n{'id':>3} {'class':<16} {'ret%':>8} {'ann%':>7} {'sharpe':>7} {'sortino':>8} "
          f"{'calmar':>7} {'dd%':>8} {'var95%':>7} {'maxpos%':>8} {'n':>4} gate")
    print("-" * 110)
    rows = []
    for sid in STRATEGIES:
        cfg = {"vt_symbol": SYMBOL_VT, "start": start, "end": end,
               "capital": CAPITAL, "fixed_size": FIXED_SIZE}
        r = _run_backtest(sid, cfg)
        if not r.get("ok"):
            print(f"{sid:>3} FAIL {r.get('error')}")
            continue
        rm = (r.get("risk_metrics") or {}).get("risk_metrics") or {}
        gate = (r.get("risk_metrics") or {}).get("risk_gate") or {}
        rows.append((sid, rm, gate, r))
        print(f"{sid:>3} {str(r.get('class_name')):<16} "
              f"{rm.get('total_return_pct', 0):>8.2f} {rm.get('annual_return_pct', 0):>7.2f} "
              f"{rm.get('sharpe_ratio', 0):>7.2f} {rm.get('sortino_ratio', 0):>8.2f} "
              f"{rm.get('calmar_ratio', 0):>7.2f} {rm.get('max_drawdown_pct', 0):>8.2f} "
              f"{rm.get('var_95_pct', 0):>7.3f} {rm.get('max_position_pct', 0):>8.2f} "
              f"{r.get('trade_count'):>4} {gate.get('verdict')}")

    if rows:
        sh = sorted(x[1].get("sharpe_ratio", 0) for x in rows)
        an = sorted(x[1].get("annual_return_pct", 0) for x in rows)
        dd = sorted(x[1].get("max_drawdown_pct", 0) for x in rows)
        print(f"\nSUMMARY strategies={len(rows)} "
              f"sharpe[{sh[0]:.2f},{sh[-1]:.2f}] med={sh[len(sh)//2]:.2f} "
              f"ann[{an[0]:.2f},{an[-1]:.2f}]% med={an[len(an)//2]:.2f}% "
              f"dd[{dd[0]:.2f},{dd[-1]:.2f}]%")


if __name__ == "__main__":
    main()
