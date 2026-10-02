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
