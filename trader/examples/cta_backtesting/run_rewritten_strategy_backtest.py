from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
import importlib
from pathlib import Path
import sys

from vnpy.trader.constant import Interval
from vnpy_ctastrategy.backtesting import BacktestingEngine


# 默认回测配置：直接运行本文件即可使用，必要时再用命令行覆盖。
DEFAULT_CONFIG = {
    "strategy_id": "01",
    "vt_symbol": "600031.SSE",
    "start": "2024-01-01",
    "end": "2026-12-31",
    "rate": 0.0003,
    "slippage": 0.01,
    "size": 1,
    "pricetick": 0.01,
    "capital": 10_000,
}


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def load_strategy_class(strategy_id: str):
    folder = Path(__file__).resolve().parent / "rewritten_strategies"
    manifest = folder / "manifest.csv"

    with manifest.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["strategy_id"] == strategy_id:
                module_name = f"rewritten_strategies.{Path(row['target_file']).stem}"
                module = importlib.import_module(module_name)
                cls = getattr(module, row["class_name"])
                return cls, row

    raise ValueError(f"strategy_id {strategy_id} not found in {manifest}")


def build_setting(strategy_cls, manifest_row: dict, user_config: dict | None) -> dict:
    """族默认参数 + 用户覆盖。只保留策略类 parameters 中声明的键。"""
    setting: dict = {}
    if manifest_row.get("params"):
        try:
            setting = json.loads(manifest_row["params"])
        except (ValueError, TypeError):
            setting = {}

    if user_config:
        for key, value in user_config.items():
            if key in getattr(strategy_cls, "parameters", []) and value is not None:
                setting[key] = value

    # 保证必要的键存在（default 提供 all-a-round 默认）
    for key in getattr(strategy_cls, "parameters", []):
        if key not in setting:
            setting[key] = getattr(strategy_cls, key, None)
    return setting


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run rewritten strategy in local vn.py backtesting.")
    parser.add_argument("--strategy-id", default=DEFAULT_CONFIG["strategy_id"], help="e.g. 01, 02, 99")
    parser.add_argument("--vt-symbol", default=DEFAULT_CONFIG["vt_symbol"], help="vt_symbol, e.g. 600031.SSE")
    parser.add_argument("--start", default=DEFAULT_CONFIG["start"])
    parser.add_argument("--end", default=DEFAULT_CONFIG["end"])
    parser.add_argument("--rate", type=float, default=DEFAULT_CONFIG["rate"])
    parser.add_argument("--slippage", type=float, default=DEFAULT_CONFIG["slippage"])
    parser.add_argument("--size", type=float, default=DEFAULT_CONFIG["size"])
    parser.add_argument("--pricetick", type=float, default=DEFAULT_CONFIG["pricetick"])
    parser.add_argument("--capital", type=int, default=DEFAULT_CONFIG["capital"])

    # 策略参数：解析后仅保留该族类 parameters 中命名的键
    parser.add_argument("--fast-window", type=int, default=None)
    parser.add_argument("--slow-window", type=int, default=None)
    parser.add_argument("--signal-window", type=float, default=None)
    parser.add_argument("--atr-window", type=int, default=None)
    parser.add_argument("--atr-mult", type=float, default=None)
    parser.add_argument("--fixed-size", type=int, default=None)
    return parser


def main(config: dict | None = None):
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

    parser = build_parser()
    if config:
        parser.set_defaults(
            strategy_id=config.get("strategy_id", DEFAULT_CONFIG["strategy_id"]),
            vt_symbol=config.get("vt_symbol", DEFAULT_CONFIG["vt_symbol"]),
            start=config.get("start", DEFAULT_CONFIG["start"]),
            end=config.get("end", DEFAULT_CONFIG["end"]),
            rate=config.get("rate", DEFAULT_CONFIG["rate"]),
            slippage=config.get("slippage", DEFAULT_CONFIG["slippage"]),
            size=config.get("size", DEFAULT_CONFIG["size"]),
            pricetick=config.get("pricetick", DEFAULT_CONFIG["pricetick"]),
            capital=config.get("capital", DEFAULT_CONFIG["capital"]),
            fast_window=config.get("fast_window"),
            slow_window=config.get("slow_window"),
            signal_window=config.get("signal_window"),
            atr_window=config.get("atr_window"),
            atr_mult=config.get("atr_mult"),
            fixed_size=config.get("fixed_size"),
        )

    args = parser.parse_args([] if config else None)
    sid = args.strategy_id.zfill(2)
    strategy_cls, row = load_strategy_class(sid)

    print(f"加载策略: {row['class_name']} (来源: {row['source_file']}, 类型: {row['archetype']})")

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

    user_overrides = {
        "fast_window": args.fast_window,
        "slow_window": args.slow_window,
        "signal_window": args.signal_window,
        "atr_window": args.atr_window,
        "atr_mult": args.atr_mult,
        "fixed_size": args.fixed_size,
    }
    setting = build_setting(strategy_cls, row, user_overrides)
    print(f"策略参数: {setting}")
    engine.add_strategy(strategy_cls, setting)

    print("开始加载历史数据...")
    engine.load_data()
    if not engine.history_data:
        print(f"没有加载到历史数据，请检查数据库中是否存在 {args.vt_symbol} 的日线数据。")
        # 必须与正常返回同样是三元组，否则上层 stats, result_df, trades = main(...) 会解包崩溃 → HTTP 500
        return {}, None, {}

    print("开始执行回测...")
    engine.run_backtesting()

    print("开始计算结果...")
    result_df = engine.calculate_result()
    stats = engine.calculate_statistics()

    print("\n=== 回测统计 ===")
    for k, v in stats.items():
        print(f"{k}: {v}")

    print(f"\n成交笔数: {len(engine.trades)}")
    print(f"结果行数: {0 if result_df is None else len(result_df)}")

    return stats, result_df, engine.trades


if __name__ == "__main__":
    main()
