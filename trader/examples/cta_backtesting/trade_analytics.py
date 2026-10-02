"""从 vn.py 回测成交与逐日结果构造可 JSON 化的分析字段。"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any

from vnpy.trader.constant import Direction, Offset
from vnpy.trader.object import TradeData


def _enum_name(x: Any) -> str | None:
    if x is None:
        return None
    return getattr(x, "name", type(x).__name__)


def _enum_value_str(x: Any) -> str:
    if x is None:
        return ""
    return str(getattr(x, "value", x))


def action_label(trade: TradeData) -> str:
    """可读开平仓说明（与 vn.py CTA 模板语义一致）。"""
    d, o = trade.direction, trade.offset
    if d == Direction.LONG and o == Offset.OPEN:
        return "买入 · 开多"
    if d == Direction.SHORT and o == Offset.CLOSE:
        return "卖出 · 平多"
    if d == Direction.SHORT and o == Offset.OPEN:
        return "卖出 · 开空"
    if d == Direction.LONG and o == Offset.CLOSE:
        return "买入 · 平空"
    return f"{_enum_value_str(d)}{_enum_value_str(o)}"


def serialize_trade_fills(trades: Any) -> list[dict[str, Any]]:
    """逐笔成交（回测撮合结果），含方向、开平、价格、数量。"""
    seq: list[TradeData]
    if isinstance(trades, dict):
        seq = list(trades.values())
    elif trades is None:
        seq = []
    else:
        seq = list(trades)

    seq.sort(key=lambda t: t.datetime or datetime.min)

    out: list[dict[str, Any]] = []
    for t in seq:
        dt = t.datetime
        out.append(
            {
                "vt_tradeid": t.vt_tradeid,
                "orderid": t.orderid,
                "tradeid": t.tradeid,
                "datetime": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None,
                "date": dt.strftime("%Y-%m-%d") if dt else None,
                "direction": _enum_value_str(t.direction),
                "direction_code": _enum_name(t.direction),
                "offset": _enum_value_str(t.offset),
                "offset_code": _enum_name(t.offset),
                "price": float(t.price),
                "volume": float(t.volume),
                "symbol": t.symbol,
                "exchange": getattr(t.exchange, "value", str(t.exchange)),
                "action_label": action_label(t),
            }
        )
    return out


def _holding_days(t0: datetime, t1: datetime) -> int:
    return max(0, (t1.date() - t0.date()).days)


def compute_fifo_rounds(trades: Any, size: float) -> dict[str, Any]:
    """
    按 FIFO 将「开多↔平多」「开空↔平空」配成完整回合，估算毛盈亏（不含手续费/滑点精算）。
    毛盈亏：多头 (exit-entry)*vol*size；空头 (entry-exit)*vol*size。
    """
    if isinstance(trades, dict):
        seq = list(trades.values())
    elif trades is None:
        seq = []
    else:
        seq = list(trades)
    seq.sort(key=lambda t: t.datetime or datetime.min)

    long_open: deque[tuple[float, float, datetime]] = deque()
    short_open: deque[tuple[float, float, datetime]] = deque()
    rounds: list[dict[str, Any]] = []

    for t in seq:
        if not t.direction or not t.offset:
            continue
        dt = t.datetime or datetime.min
        vol = float(t.volume)
        px = float(t.price)
        if t.direction == Direction.LONG and t.offset == Offset.OPEN:
            long_open.append((px, vol, dt))
        elif t.direction == Direction.SHORT and t.offset == Offset.CLOSE:
            rem = vol
            while rem > 1e-12 and long_open:
                ep, ev, edt = long_open[0]
                take = min(rem, ev)
                gross = (px - ep) * take * size
                rounds.append(
                    {
                        "side": "long",
                        "entry_datetime": edt.strftime("%Y-%m-%d %H:%M:%S"),
                        "exit_datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "holding_days": _holding_days(edt, dt),
                        "entry_price": round(ep, 6),
                        "exit_price": round(px, 6),
                        "volume": take,
                        "gross_pnl_approx": round(gross, 6),
                    }
                )
                rem -= take
                left = ev - take
                if left <= 1e-12:
                    long_open.popleft()
                else:
                    long_open[0] = (ep, left, edt)
        elif t.direction == Direction.SHORT and t.offset == Offset.OPEN:
            short_open.append((px, vol, dt))
        elif t.direction == Direction.LONG and t.offset == Offset.CLOSE:
            rem = vol
            while rem > 1e-12 and short_open:
                ep, ev, edt = short_open[0]
                take = min(rem, ev)
                gross = (ep - px) * take * size
                rounds.append(
                    {
                        "side": "short",
                        "entry_datetime": edt.strftime("%Y-%m-%d %H:%M:%S"),
                        "exit_datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "holding_days": _holding_days(edt, dt),
                        "entry_price": round(ep, 6),
                        "exit_price": round(px, 6),
                        "volume": take,
                        "gross_pnl_approx": round(gross, 6),
                    }
                )
                rem -= take
                left = ev - take
                if left <= 1e-12:
                    short_open.popleft()
                else:
                    short_open[0] = (ep, left, edt)

    unclosed_long = float(sum(v for _, v, _ in long_open))
    unclosed_short = float(sum(v for _, v, _ in short_open))
    return {
        "trade_rounds": rounds,
        "unclosed_long_volume": round(unclosed_long, 6),
        "unclosed_short_volume": round(unclosed_short, 6),
    }


def compute_signal_quality(rounds: list[dict[str, Any]]) -> dict[str, Any]:
    """基于回合毛盈亏近似：胜率、盈亏比、因子等。"""
    if not rounds:
        return {
            "round_count": 0,
            "win_rate": None,
            "profit_factor": None,
            "avg_win": None,
            "avg_loss": None,
            "payoff_ratio": None,
            "expectancy_per_round": None,
            "gross_pnl_sum": 0.0,
        }

    pnls = [float(r["gross_pnl_approx"]) for r in rounds]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    breakeven = sum(1 for p in pnls if p == 0)

    win_rate = len(wins) / len(pnls) if pnls else None
    sum_win = sum(wins) if wins else 0.0
    sum_loss = sum(losses) if losses else 0.0  # negative
    profit_factor = (sum_win / abs(sum_loss)) if sum_loss < 0 else None
    avg_win = (sum_win / len(wins)) if wins else None
    avg_loss = (sum_loss / len(losses)) if losses else None  # negative
    payoff_ratio = (avg_win / abs(avg_loss)) if wins and losses and avg_loss else None
    expectancy = (sum(pnls) / len(pnls)) if pnls else None

    return {
        "round_count": len(pnls),
        "breakeven_rounds": breakeven,
        "win_rate": round(win_rate, 6) if win_rate is not None else None,
        "profit_factor": round(profit_factor, 6) if profit_factor is not None else None,
        "avg_win": round(avg_win, 6) if avg_win is not None else None,
        "avg_loss": round(avg_loss, 6) if avg_loss is not None else None,
        "payoff_ratio": round(payoff_ratio, 6) if payoff_ratio is not None else None,
        "expectancy_per_round": round(expectancy, 6) if expectancy is not None else None,
        "gross_pnl_sum": round(sum(pnls), 6),
    }


def build_daily_position_exposure(result_df: Any, size: float) -> list[dict[str, Any]]:
    """
    基于 vn.py 逐日盯市 DataFrame：日末净持仓、名义敞口近似、占权益比。
    无行业/杠杆/保证金字段（单标的日线 CTA 回测本身不产出）。
    """
    if result_df is None or getattr(result_df, "empty", True):
        return []

    rows: list[dict[str, Any]] = []
    for idx, row in result_df.iterrows():
        date_s = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)
        end_pos = float(row.get("end_pos", 0) or 0)
        close_p = float(row.get("close_price", 0) or 0)
        balance = float(row.get("balance", 0) or 0)
        notional = abs(end_pos) * close_p * size
        pct = (notional / balance * 100.0) if balance > 1e-9 else None
        rows.append(
            {
                "date": date_s,
                "end_position": end_pos,
                "close_price": round(close_p, 6),
                "balance": round(balance, 6),
                "position_notional_approx": round(notional, 6),
                "position_to_equity_pct_approx": round(pct, 6) if pct is not None else None,
                "trade_count": int(row.get("trade_count", 0) or 0),
                "net_pnl": float(row.get("net_pnl", 0) or 0),
                "turnover": float(row.get("turnover", 0) or 0),
                "commission": float(row.get("commission", 0) or 0),
            }
        )
    return rows


def build_data_scope(
    *,
    vt_symbol: str,
    has_sector_data: bool,
    has_margin_fields: bool,
) -> dict[str, Any]:
    """明确哪些指标已提供、哪些仍不可用（避免报告误读）。"""
    return {
        "engine": "vn.py CTA BacktestingEngine · 日线 Bar",
        "vt_symbol": vt_symbol,
        "provided": [
            "逐笔成交回报 trade_fills：方向、开平、价格、数量、时间（来自 TradeData）",
            "FIFO 配对的完整开平仓回合 trade_rounds 及回合级 gross_pnl_approx（未扣双边手续费/滑点精算）",
            "基于回合毛盈亏的信号质量指标 signal_quality（胜率、盈亏比等近似）",
            "逐日 end_position、名义敞口与占权益比近似 daily_position_exposure（由日终持仓×收盘价×合约乘数）",
        ],
        "not_available_in_this_pipeline": [
            "交易所真实逐笔委托/逐笔成交明细（仅回测撮合结果）",
            "单笔净盈亏（含精确费率、印花税、分红除权）需对接清算规则另行计算",
            "行业/板块集中度、多标的组合权重（当前为单标的回测）",
            "杠杆倍数、保证金占用率、强平线（股票现货 CTA 模板未建模融资融券）",
            "日内路径风险（仅日线 Bar，无 intraday 持仓路径）",
        ],
        "flags": {
            "sector_concentration": has_sector_data,
            "margin_or_leverage": has_margin_fields,
        },
    }


def build_trade_extensions(trades: Any, result_df: Any, config: dict[str, Any]) -> dict[str, Any]:
    """供 API 挂载：成交明细、FIFO 回合、信号质量、日度敞口、数据边界说明。"""
    size = float(config.get("size", 1))
    fills = serialize_trade_fills(trades)
    fifo = compute_fifo_rounds(trades, size)
    rounds = fifo["trade_rounds"]
    signal_quality = compute_signal_quality(rounds)
    daily_exposure = build_daily_position_exposure(result_df, size)
    scope = build_data_scope(
        vt_symbol=str(config.get("vt_symbol", "")),
        has_sector_data=False,
        has_margin_fields=False,
    )
    return {
        "trade_fills": fills,
        "trade_rounds": rounds,
        "fifo_unclosed": {
            "long_volume": fifo["unclosed_long_volume"],
            "short_volume": fifo["unclosed_short_volume"],
        },
        "signal_quality": signal_quality,
        "daily_position_exposure": daily_exposure,
        "data_scope": scope,
    }
