from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

from vnpy.trader.constant import Interval
from vnpy_ctastrategy.backtesting import BacktestingEngine

from daily_ma_cross_strategy import DailyMACrossStrategy

import ai.SingleRound

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a simple CTA daily backtesting demo.")
    parser.add_argument("--vt-symbol", default="600031.SSE", help="vt_symbol, e.g. 600031.SSE")
    parser.add_argument("--start", default="2023-01-01", help="backtest start date: YYYY-MM-DD")
    parser.add_argument("--end", default="2025-12-31", help="backtest end date: YYYY-MM-DD")
    parser.add_argument("--rate", type=float, default=0.0003, help="commission rate")
    parser.add_argument("--slippage", type=float, default=0.01, help="slippage")
    parser.add_argument("--size", type=float, default=1, help="contract size")
    parser.add_argument("--pricetick", type=float, default=0.01, help="price tick")
    parser.add_argument("--capital", type=int, default=1_000_000, help="starting capital")
    parser.add_argument("--fast-window", type=int, default=5, help="fast MA window")
    parser.add_argument("--slow-window", type=int, default=10, help="slow MA window")
    parser.add_argument("--fixed-size", type=int, default=1, help="trade size")
    return parser


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def main() -> None:
    # 让脚本从 examples/cta_backtesting 目录运行时也能正确 import 本地策略文件。
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    args = build_parser().parse_args()

    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbol=args.vt_symbol,
        interval=Interval.DAILY,
        start=parse_date(args.start),
        end=parse_date(args.end),
        rate=args.rate,
        slippage=args.slippage,
        size=args.size,
        pricetick=args.pricetick,
        capital=args.capital,
    )

    setting = {
        "fast_window": args.fast_window,
        "slow_window": args.slow_window,
        "fixed_size": args.fixed_size,
    }
    engine.add_strategy(DailyMACrossStrategy, setting)

    print("开始加载历史数据...")
    engine.load_data()

    if not engine.history_data:
        print(f"没有加载到历史数据，请检查数据库中是否存在 {args.vt_symbol} 的日线数据。")
        return

    print("开始执行回测...")
    engine.run_backtesting()

    print("开始计算结果...")
    result_df = engine.calculate_result()
    stats = engine.calculate_statistics()

    print("\n=== 回测统计 ===")
    for key, value in stats.items():
        print(f"{key}: {value}")

    print(f"\n成交笔数: {len(engine.trades)}")
    print(f"结果行数: {0 if result_df is None else len(result_df)}")

    # 如果环境支持图形界面，可以取消下面这行看图；当前脚本只保证可运行和输出结果。
    # engine.show_chart()

    #调用ai
    ai.SingleRound.generate_backtest_report(
        stats=stats,
        vt_symbol=args.vt_symbol,
        interval=Interval.DAILY,
        start=parse_date(args.start),
        end=parse_date(args.end),
        rate=args.rate,
        slippage=args.slippage,
        size=args.size,
        pricetick=args.pricetick,
        capital=args.capital,
        strategy="DailyMACrossStrategy"
    )




if __name__ == "__main__":
    main()

