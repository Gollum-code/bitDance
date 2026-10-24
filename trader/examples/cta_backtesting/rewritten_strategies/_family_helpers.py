"""族策略公共指标库。

为 rewritten_strategies 下各 family_*.py 提供统一的自定义指标实现，
复用 numpy/pandas，避免每个策略重复粘贴计算代码。
本文件内函数全部为纯函数，输入 numpy 数组，输出标量/数组。
"""
from __future__ import annotations

import numpy as np


def sma(arr: np.ndarray, window: int) -> float:
    """简单移动平均（数组尾部窗口均值）。"""
    if len(arr) < window:
        return float(np.nan)
    return float(np.mean(arr[-window:]))


def sma_series(arr: np.ndarray, window: int) -> np.ndarray:
    """简单移动平均序列，前 window-1 个为 nan。"""
    if len(arr) < window:
        return np.full(len(arr), np.nan)
    out = np.full(len(arr), np.nan)
    cum = np.cumsum(np.insert(arr, 0, 0.0))
    out[window - 1:] = (cum[window:] - cum[:-window]) / window
    return out


def ema_series(arr: np.ndarray, window: int) -> np.ndarray:
    """指数移动平均序列。"""
    if len(arr) < 2:
        return arr.astype(float)
    alpha = 2.0 / (window + 1.0)
    out = np.empty(len(arr))
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def zscore(arr: np.ndarray, window: int) -> float:
    """滚动窗口 z-score（尾值相对窗口均值/标准差）。"""
    if len(arr) < window:
        return float(np.nan)
    window_data = arr[-window:]
    std = float(np.std(window_data))
    if std < 1e-12:
        return 0.0
    return float((arr[-1] - np.mean(window_data)) / std)


def rolling_zscore_series(arr: np.ndarray, window: int) -> np.ndarray:
    """滚动 z-score 序列。"""
    out = np.full(len(arr), np.nan)
    if len(arr) < window:
        return out
    for i in range(window - 1, len(arr)):
        seg = arr[i - window + 1:i + 1]
        std = float(np.std(seg))
        if std < 1e-12:
            out[i] = 0.0
        else:
            out[i] = (seg[-1] - np.mean(seg)) / std
    return out


def rsrs_slope(high: np.ndarray, low: np.ndarray, window: int) -> float:
    """RSRS：用高/低点回归斜率的标准分。返回 (斜率, 决定系数)。"""
    if len(high) < window or len(low) < window:
        return float(np.nan), 0.0
    y = high[-window:]
    x = low[-window:]
    # 最小二乘：y = a + b*x
    xm = np.mean(x)
    ym = np.mean(y)
    num = float(np.sum((x - xm) * (y - ym)))
    den = float(np.sum((x - xm) ** 2))
    if abs(den) < 1e-12:
        return float(np.nan), 0.0
    beta = num / den
    alpha = ym - beta * xm
    yhat = alpha + beta * x
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - ym) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    return beta, r2


def kdj_stoch(high: np.ndarray, low: np.ndarray, close: np.ndarray,
              n: int = 9, m1: int = 3, m2: int = 3) -> tuple[float, float]:
    """KDJ 的 K、D 值（尾值）。"""
    if len(close) < n:
        return float(np.nan), float(np.nan)
    k = 50.0
    d = 50.0
    for i in range(max(1, len(close) - 60), len(close)):
        seg_h = high[max(0, i - n + 1):i + 1]
        seg_l = low[max(0, i - n + 1):i + 1]
        hn = float(np.max(seg_h))
        ln = float(np.min(seg_l))
        if hn - ln < 1e-12:
            rsv = 50.0
        else:
            rsv = (close[i] - ln) / (hn - ln) * 100.0
        k = (m1 - 1) / m1 * k + 1.0 / m1 * rsv
        d = (m2 - 1) / m2 * d + 1.0 / m2 * k
    return k, d


def donchian_break(high: np.ndarray, low: np.ndarray, window: int) -> tuple[float, float]:
    """唐奇安通道：上轨=最高高，下轨=最低低（不含当前 bar 则用 window-1）。"""
    if len(high) < window:
        return float(np.nan), float(np.nan)
    upper = float(np.max(high[-window:-1] if window > 1 else high[-window:]))
    lower = float(np.min(low[-window:-1] if window > 1 else low[-window:]))
    return upper, lower


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> float:
    """Wilder ATR（尾值）。"""
    if len(close) < 2:
        return float(np.nan)
    trs = np.empty(len(close) - 1)
    for i in range(1, len(close)):
        trs[i - 1] = max(high[i] - low[i],
                         abs(high[i] - close[i - 1]),
                         abs(low[i] - close[i - 1]))
    if len(trs) < window:
        return float(np.nan)
    return float(np.mean(trs[-window:]))


def bias_percent(close: np.ndarray, window: int) -> float:
    """乖离率 BIAS = (close - MA)/MA * 100。"""
    ma = sma(close, window)
    if np.isnan(ma) or ma < 1e-12:
        return float(np.nan)
    return float((close[-1] - ma) / ma * 100.0)


def true_range_ratio(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> float:
    """波动率代理：区间振幅均值 / 收盘。"""
    if len(close) < window:
        return float(np.nan)
    seg_h = high[-window:]
    seg_l = low[-window:]
    amp = np.mean((seg_h - seg_l) / np.maximum(np.abs(close[-window:]), 1e-9))
    return float(amp)


def kama(close: np.ndarray, window: int = 10) -> float:
    """Kaufman 自适应均线（尾值，简化）。"""
    if len(close) < window + 1:
        return float(np.nan)
    chg = abs(close[-1] - close[-window])
    volatility = float(np.sum(np.abs(np.diff(close[-window - 1:]))))
    if volatility < 1e-12:
        sc = 1.0
    else:
        er = chg / volatility
        sc = (er * (2.0 / (2.0 + 1.0) - 2.0 / (30.0 + 1.0)) + 2.0 / (30.0 + 1.0)) ** 2
    if len(close) <= window:
        return float(close[-1])
    # 近似：用加权 EMA 迭代
    alpha = max(sc, 0.01)
    val = float(close[-window])
    for i in range(-window + 1, 0):
        val = alpha * close[i] + (1 - alpha) * val
    return val


# ---------------- 止损 / 止盈 / 移动止损 ----------------

STOP_PARAMETERS = ("stop_loss_pct", "take_profit_pct", "trailing_stop_pct")


class StopManager:
    """持仓保护状态机：固定止损 + 固定止盈 + 移动止损。

    参数单位是**百分比**（5.0 表示 5%），0 表示该规则关闭。
    所有判断基于收盘价，保证回测可复现、不依赖盘中 tick。

    优先级：止损 > 移动止损 > 止盈。
    先判亏损保护，避免同一根 bar 同时触发止盈/止损时取错方向。
    """

    def __init__(
        self,
        stop_loss_pct: float = 0.0,
        take_profit_pct: float = 0.0,
        trailing_stop_pct: float = 0.0,
    ) -> None:
        self.stop_loss_pct = max(0.0, float(stop_loss_pct or 0.0))
        self.take_profit_pct = max(0.0, float(take_profit_pct or 0.0))
        self.trailing_stop_pct = max(0.0, float(trailing_stop_pct or 0.0))
        self.direction = 0          # 1 多 / -1 空 / 0 空仓
        self.entry_price = 0.0
        self.peak = 0.0             # 多头持仓期最高价
        self.trough = 0.0           # 空头持仓期最低价
        self.last_reason: str | None = None

    @property
    def enabled(self) -> bool:
        return any(v > 0 for v in (self.stop_loss_pct, self.take_profit_pct, self.trailing_stop_pct))

    def on_open(self, is_long: bool, price: float) -> None:
        self.direction = 1 if is_long else -1
        self.entry_price = float(price)
        self.peak = float(price)
        self.trough = float(price)
        self.last_reason = None

    def on_close(self) -> None:
        self.direction = 0
        self.entry_price = 0.0
        self.peak = 0.0
        self.trough = 0.0

    def check(self, price: float, pos: int) -> str | None:
        """返回触发原因（stop_loss / take_profit / trailing_stop），未触发返回 None。"""
        if not self.enabled or pos == 0 or price <= 0:
            return None
        direction = 1 if pos > 0 else -1
        if self.direction != direction or self.entry_price <= 0:
            # 容错：策略通过非 trade 回调直接改变持仓时，用首个可见价补记成本
            self.on_open(direction > 0, price)

        if direction > 0:
            pnl_pct = (price / self.entry_price - 1.0) * 100.0
            self.peak = max(self.peak, price)
            trail_pct = (price / self.peak - 1.0) * 100.0 if self.peak > 0 else 0.0
        else:
            pnl_pct = (self.entry_price / price - 1.0) * 100.0
            self.trough = min(self.trough, price) if self.trough > 0 else price
            trail_pct = (price / self.trough - 1.0) * 100.0 if self.trough > 0 else 0.0

        reason = None
        if self.stop_loss_pct > 0 and pnl_pct <= -self.stop_loss_pct:
            reason = "stop_loss"
        elif self.trailing_stop_pct > 0 and trail_pct <= -self.trailing_stop_pct:
            reason = "trailing_stop"
        elif self.take_profit_pct > 0 and pnl_pct >= self.take_profit_pct:
            reason = "take_profit"

        if reason:
            self.last_reason = reason
        return reason


def _trade_is_open(trade: object) -> bool:
    offset = getattr(trade, "offset", None)
    text = str(getattr(offset, "value", offset)).upper()
    return "OPEN" in text or "开" in str(offset)


def _trade_is_long(trade: object) -> bool:
    direction = getattr(trade, "direction", None)
    text = str(getattr(direction, "value", direction)).upper()
    return "LONG" in text or "多" in str(direction)


def make_stop_aware(strategy_cls: type) -> type:
    """给任意 CtaTemplate 族策略动态挂上 StopManager。

    不修改 23 个族策略源码，统一在加载时套一层子类：
      - 新增 stop_loss_pct / take_profit_pct / trailing_stop_pct 参数（默认 0 = 关闭）
      - on_trade 记录开平仓成本
      - on_bar 在策略自身信号之前检查止损（亏损保护优先）
    默认全关闭时行为与原子策略**完全一致**。
    """

    existing = set(getattr(strategy_cls, "parameters", []) or [])
    base_vars = list(getattr(strategy_cls, "variables", []) or [])

    class StopAware(strategy_cls):  # type: ignore[misc, valid-type]
        stop_loss_pct = 0.0
        take_profit_pct = 0.0
        trailing_stop_pct = 0.0

        parameters = list(getattr(strategy_cls, "parameters", []) or []) + [
            p for p in STOP_PARAMETERS if p not in existing
        ]
        variables = base_vars + ["stop_state"]

        def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
            super().__init__(cta_engine, strategy_name, vt_symbol, setting)
            self._stop = StopManager(
                getattr(self, "stop_loss_pct", 0.0),
                getattr(self, "take_profit_pct", 0.0),
                getattr(self, "trailing_stop_pct", 0.0),
            )
            self.stop_state = "idle"

        def on_trade(self, trade) -> None:
            parent = getattr(super(), "on_trade", None)
            if callable(parent):
                parent(trade)
            price = float(getattr(trade, "price", 0) or 0)
            if _trade_is_open(trade):
                self._stop.on_open(_trade_is_long(trade), price)
            else:
                self._stop.on_close()

        def on_bar(self, bar) -> None:
            if self.pos != 0:
                reason = self._stop.check(bar.close_price, self.pos)
                if reason:
                    self.cancel_all()
                    self.stop_state = reason
                    price = bar.close_price
                    if self.pos > 0:
                        self.sell(price, abs(self.pos))
                    else:
                        self.cover(price, abs(self.pos))
                    self.put_event()
                    return
            super().on_bar(bar)

    StopAware.__name__ = f"StopAware{strategy_cls.__name__}"
    StopAware.__qualname__ = StopAware.__name__
    StopAware.__doc__ = getattr(strategy_cls, "__doc__", None)
    return StopAware
