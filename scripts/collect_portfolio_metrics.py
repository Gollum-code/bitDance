"""一篮子真实标的的组合回测（名义金额等权），产出可写进简历的真实组合指标。

可独立运行：库中缺少标的或数据覆盖不足时，会自动从腾讯公开源分段拉取
真实前复权日线并写入本地库（幂等，已满足则跳过）。

口径：
  - 组合：capital 总额按等权拆成名义金额分给各 sleeve，组合收益 = Σ sleeve 收益
  - 基准：同期每日再平衡等权买入持有

用法：
  python scripts/collect_portfolio_metrics.py              # 缺数据会自动同步
  python scripts/collect_portfolio_metrics.py --no-sync    # 只用本地已有数据
"""
import sys
import argparse
import importlib.util
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "trader"))

_spec = importlib.util.spec_from_file_location("main", ROOT / "trader" / "main.py")
_main = importlib.util.module_from_spec(_spec)
sys.modules["main"] = _main
_spec.loader.exec_module(_main)

from vnpy.trader.constant import Exchange, Interval  # noqa: E402
from vnpy.trader.database import get_database  # noqa: E402

from routers.analytics import PortfolioRequest, portfolio_backtest  # noqa: E402
from examples.cta_backtesting.market_data_tools import ensure_symbol_data  # noqa: E402

# 跨行业一篮子（银行 / 白酒 / 保险 / 家电 / 电力 / 资源）
BASKET = [
    ("601318", "SSE", "中国平安"), ("600036", "SSE", "招商银行"), ("000001", "SZSE", "平安银行"),
    ("600519", "SSE", "贵州茅台"), ("000858", "SZSE", "五粮液"), ("000333", "SZSE", "美的集团"),
    ("600900", "SSE", "长江电力"), ("601899", "SSE", "紫金矿业"),
]

CAPITAL = 1_000_000
START = "2021-01-04"
END = "2026-10-19"
STRATEGIES = ["08", "13", "27", "04", "09"]


def load_bars(sync: bool = True):
    db = get_database()
    out = []
    for code, ex, name in BASKET:
        exchange = {"SSE": Exchange.SSE, "SZSE": Exchange.SZSE}[ex]
        if sync:
            try:
                res = ensure_symbol_data(db, code, exchange, START, END)
                action = "SYNCED" if res.get("synced") else "CACHED"
                print(f"  [{action}] {code}.{ex} n={res.get('n')}")
            except Exception as e:
                print(f"  [WARN] {code}.{ex} 同步失败，尝试使用已有数据: {e}")
        o = [b for b in db.get_bar_overview()
             if b.symbol == code and b.exchange == exchange and b.interval == Interval.DAILY]
        bars = db.load_bar_data(code, exchange, Interval.DAILY, o[0].start, o[0].end) if o else []
        if not bars:
            print(f"  [SKIP] {code}.{ex} 本地无数据")
            continue
        out.append((f"{code}.{ex}", name, bars))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-sync", action="store_true", help="只用本地已有数据，不自动拉取")
    args = parser.parse_args()

    print("=== 准备行情数据 ===")
    loaded = load_bars(sync=not args.no_sync)
    vt_list = [v for v, _, _ in loaded]
    if len(vt_list) < 2:
        print("可用标的不足，退出")
        return

    notional = [CAPITAL / len(vt_list)] * len(vt_list)
    print(f"\n=== 组合回测（名义金额等权，{len(vt_list)} 标的，"
          f"每标的 {notional[0]:,.0f} 元，capital={CAPITAL:,}） ===")
    print(f"=== 区间 {START} ~ {END} ===")

    for sid in STRATEGIES:
        body = PortfolioRequest(
            strategy_id=sid,
            vt_symbols=vt_list,
            start=START,
            end=END,
            capital=CAPITAL,
            notional_per_symbol=notional,
        )
        try:
            r = portfolio_backtest(body)
        except Exception as e:
            print(f"{sid} ERROR {type(e).__name__} {e}")
            continue
        if not r.get("success"):
            print(f"{sid} FAIL {r.get('message')}")
            continue
        st = r.get("stats") or {}
        print(f"PORT {sid} {str(r.get('class_name')):<16} "
              f"ret={st.get('total_return')}% ann={st.get('annual_return')}% "
              f"sharpe={st.get('sharpe_ratio')} sortino={st.get('sortino_ratio')} "
              f"calmar={st.get('calmar_ratio')} dd={st.get('max_drawdown')}% "
              f"var95={st.get('var_95_pct')}% trades={st.get('total_trade_count')}")
        print(f"     {r.get('message')}")
        w = r.get("weights") or []
        for p in w:
            print(f"       {p.get('vt_symbol'):<12} w={p.get('weight')} "
                  f"notional={p.get('target_notional')} shares={p.get('fixed_size')} "
                  f"px={p.get('first_close')}")

    # 基准：等权买入持有
    print("\n=== 等权买入持有基准 ===")
    per_symbol = []
    for _, _, bars in loaded:
        c = np.array([b.close_price for b in bars], dtype=float)
        dts = [b.datetime.strftime("%Y-%m-%d") for b in bars]
        per_symbol.append({d: (c[i] / c[i - 1] - 1.0) for i, d in enumerate(dts) if i > 0})

    all_dates = sorted({d for s in per_symbol for d in s})
    all_dates = [d for d in all_dates if START <= d <= END]
    rets = np.array([sum(s.get(d, 0.0) for s in per_symbol) / len(per_symbol) for d in all_dates])
    navs = np.cumprod(1 + rets)
    total = navs[-1] - 1
    yrs = len(all_dates) / 252.0
    ann = (1 + total) ** (1 / yrs) - 1
    vol = float(np.std(rets, ddof=1) * np.sqrt(252))
    dd = float(np.min(navs / np.maximum.accumulate(navs) - 1))
    sharpe = (ann - 0.02) / vol if vol > 1e-12 else 0.0
    print(f"BENCH equal_weight_buyhold total={total*100:.2f}% ann={ann*100:.2f}% "
          f"vol={vol*100:.2f}% maxdd={dd*100:.2f}% sharpe={sharpe:.2f} days={len(all_dates)}")


if __name__ == "__main__":
    main()
