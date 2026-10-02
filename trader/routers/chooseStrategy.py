from datetime import date
from pathlib import Path
import csv
import logging

from fastapi import APIRouter, HTTPException
import numpy as np

from examples.cta_backtesting.run_rewritten_strategy_backtest import DEFAULT_CONFIG, main
from examples.cta_backtesting.trade_analytics import build_trade_extensions

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/list")
def get_strategy_list():
    manifest = (
        Path(__file__).resolve().parent.parent
        / "examples"
        / "cta_backtesting"
        / "rewritten_strategies"
        / "manifest.csv"
    )
    strategies = []
    with manifest.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            strategies.append(
                {
                    "strategy_id": row["strategy_id"],
                    "class_name": row["class_name"],
                    "archetype": row["archetype"],
                    "source_file": row["source_file"],
                }
            )
    return {"strategies": strategies}


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: str,
    vt_symbol: str = "600031.SSE",
    start: str = "2024-01-01",
    end: str | None = None,
    rate: float = 0.0003,
    slippage: float = 0.01,
    size: float = 1,
    pricetick: float = 0.01,
    capital: int = 10_000,
    fast_window: int | None = None,
    slow_window: int | None = None,
    signal_window: int | None = None,
    atr_window: int | None = None,
    atr_mult: float | None = None,
    fixed_size: int | None = None,
):
    from datetime import date as _date

    if not end:
        end = _date.today().isoformat()

    config = DEFAULT_CONFIG.copy()
    config["strategy_id"] = strategy_id
    config["vt_symbol"] = vt_symbol
    config["start"] = start
    config["end"] = end
    config["rate"] = rate
    config["slippage"] = slippage
    config["size"] = size
    config["pricetick"] = pricetick
    config["capital"] = capital
    config["fast_window"] = fast_window
    config["slow_window"] = slow_window
    config["signal_window"] = signal_window
    config["atr_window"] = atr_window
    config["atr_mult"] = atr_mult
    config["fixed_size"] = fixed_size

    try:
        stats, result_df, trades = main(config)
    except Exception as e:
        logger.exception("回测执行失败 strategy_id=%s vt_symbol=%s", strategy_id, vt_symbol)
        raise HTTPException(status_code=500, detail=f"回测执行失败: {e}") from e

    if stats is not None:
        for k, v in stats.items():
            if isinstance(v, np.generic):
                stats[k] = v.item()
            elif isinstance(v, date):
                stats[k] = v.isoformat()
    else:
        stats = {}

    series = {"dates": [], "balance": [], "drawdown": [], "benchmark": []}
    if result_df is not None and not result_df.empty:
        series["dates"] = [idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx) for idx in result_df.index]
        if "balance" in result_df.columns:
            series["balance"] = [float(v) for v in result_df["balance"].fillna(0).tolist()]
        if "drawdown" in result_df.columns:
            series["drawdown"] = [float(v) for v in result_df["drawdown"].fillna(0).tolist()]
        if "close_price" in result_df.columns:
            close_prices = [float(v) for v in result_df["close_price"].fillna(0).tolist()]
            if close_prices and close_prices[0] > 0:
                base = close_prices[0]
                series["benchmark"] = [round((price / base - 1) * 100, 4) for price in close_prices]

    trade_points = []
    if isinstance(trades, dict):
        trade_iter = trades.values()
    elif trades is None:
        trade_iter = []
    else:
        trade_iter = trades
    for trade in trade_iter:
        dt = getattr(trade, "datetime", None)
        direction = getattr(trade, "direction", None)
        offset = getattr(trade, "offset", None)
        if not dt or not direction:
            continue

        direction_text = getattr(direction, "value", str(direction))
        offset_text = getattr(offset, "value", str(offset)) if offset else ""
        side = "buy" if "多" in direction_text or "LONG" in direction_text.upper() else "sell"
        is_open = "开" in offset_text or "OPEN" in offset_text.upper()
        action = f"{side}_{'open' if is_open else 'close'}"
        trade_points.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "side": side,
                "action": action,
                "price": float(getattr(trade, "price", 0) or 0),
                "volume": float(getattr(trade, "volume", 0) or 0),
            }
        )

    has_series = len(series["dates"]) > 0 and len(series["balance"]) > 0
    trade_count = int(stats.get("total_trade_count", 0)) if stats else 0
    if not has_series:
        message = "未加载到可回测的数据，请检查vt_symbol和时间区间是否已有历史数据"
    elif trade_count == 0:
        message = "回测完成，但该策略在当前区间没有触发交易信号（成交次数=0）"
    else:
        message = "ok"

    trade_extensions = build_trade_extensions(trades, result_df, config)

    return {
        "success": has_series and trade_count > 0,
        "message": message,
        "params": config,
        "stats": stats,
        "series": series,
        "trade_points": trade_points,
        **trade_extensions,
    }

