"""组合权重优化（纯 numpy，不依赖 scipy）。

现有组合回测只支持等权 / 手填权重。本模块补上三种最常用的规则化配置：
  - min_variance：最小方差组合
  - risk_parity：风险平价（每只标的对组合风险的贡献相等）
  - max_sharpe：最大夏普（long-only）

约束统一为 **long-only + 权重和为 1**（A 股组合回测的默认场景），
用单纯形投影 + 投影梯度 / 坐标下降实现，避免引入 scipy 这种重依赖。

重要口径：
  输入 mu / cov 必须是**年化**后的值（日收益 ×252 / 日协方差 ×252）。
  本模块不负责取数与对齐，保持纯函数可单测。
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np


def project_simplex(v: Sequence[float], total: float = 1.0) -> np.ndarray:
    """把任意向量投影到 {w >= 0, sum(w) = total} 单纯形（Duchi 算法）。"""
    w = np.asarray(v, dtype=float).ravel()
    if w.size == 0:
        return w
    u = np.sort(w)[::-1]
    css = np.cumsum(u)
    rho = np.nonzero(u * np.arange(1, w.size + 1) > (css - total))[0][-1]
    theta = (css[rho] - total) / (rho + 1.0)
    return np.maximum(w - theta, 0.0)


def _normalize(w: np.ndarray) -> np.ndarray:
    s = float(np.sum(w))
    if s <= 1e-15:
        return np.full(w.size, 1.0 / w.size)
    return w / s


def equal_weights(n: int) -> np.ndarray:
    return np.full(int(n), 1.0 / max(1, int(n)))


def min_variance_weights(
    cov: np.ndarray,
    *,
    max_iter: int = 2000,
    tol: float = 1e-12,
) -> np.ndarray:
    """long-only 最小方差组合：投影梯度下降最小化 w'Σw。"""
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    w = equal_weights(n)
    eig_max = float(np.max(np.linalg.eigvalsh(cov))) if n else 1.0
    if eig_max <= 1e-15:
        return w
    step = 0.5 / eig_max  # 2Σ 的 Lipschitz 常数约 2*eig_max，步长取保守值

    for _ in range(max_iter):
        grad = 2.0 * cov @ w
        w_new = project_simplex(w - step * grad)
        if np.max(np.abs(w_new - w)) < tol:
            w = w_new
            break
        w = w_new
    return _normalize(w)


def max_sharpe_weights(
    mu: Sequence[float],
    cov: np.ndarray,
    *,
    risk_free: float = 0.0,
    max_iter: int = 3000,
    tol: float = 1e-12,
) -> np.ndarray:
    """long-only 最大夏普：投影梯度上升 + 回溯线搜索。

    若所有标的超额收益都 <= 0，退化为最小方差（没有可追求的正夏普方向）。
    """
    mu_arr = np.asarray(mu, dtype=float).ravel()
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    if n == 0:
        return np.array([])
    if np.all(mu_arr - risk_free <= 0):
        return min_variance_weights(cov)

    w = equal_weights(n)
    for _ in range(max_iter):
        q = float(w @ cov @ w)
        if q <= 1e-18:
            break
        excess = float(w @ mu_arr - risk_free)
        # dSharpe/dw = mu/sqrt(q) - excess * Σw / q^(3/2)
        grad = mu_arr / np.sqrt(q) - excess * (cov @ w) / (q ** 1.5)
        step = 1.0
        improved = False
        for _ls in range(30):
            cand = project_simplex(w + step * grad)
            qc = float(cand @ cov @ cand)
            if qc > 1e-18:
                s_new = float(cand @ mu_arr - risk_free) / np.sqrt(qc)
                s_old = excess / np.sqrt(q)
                if s_new >= s_old - 1e-15:
                    improved = True
                    break
            step *= 0.5
        if not improved:
            break
        delta = np.max(np.abs(cand - w))
        w = cand
        if delta < tol:
            break
    return _normalize(w)


def risk_parity_weights(
    cov: np.ndarray,
    *,
    max_iter: int = 2000,
    tol: float = 1e-12,
) -> np.ndarray:
    """风险平价：让每只标的的风险贡献 w_i·(Σw)_i 相等。

    用坐标下降解 `a·w_i² + b·w_i - c = 0`，其中
      a = Σ_ii, b = Σ_{j≠i} w_j Σ_ij, c = 组合方差 / n。
    """
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    if n == 0:
        return np.array([])
    w = equal_weights(n)

    for _ in range(max_iter):
        port_var = float(w @ cov @ w)
        target = max(port_var / n, 1e-18)
        prev = w.copy()
        for i in range(n):
            a = float(cov[i, i])
            if a <= 1e-18:
                w[i] = 0.0
                continue
            b = float(np.dot(np.delete(cov[i, :], i), np.delete(w, i)))
            disc = b * b + 4.0 * a * target
            w[i] = (-b + np.sqrt(max(disc, 0.0))) / (2.0 * a)
        w = _normalize(w)
        if np.max(np.abs(w - prev)) < tol:
            break
    return _normalize(w)


def optimize_weights(
    method: str,
    mu: Sequence[float],
    cov: np.ndarray,
    *,
    risk_free: float = 0.0,
) -> np.ndarray:
    """统一入口：equal / risk_parity / min_variance / max_sharpe。"""
    mu_arr = np.asarray(mu, dtype=float).ravel()
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    if method == "equal":
        return equal_weights(n)
    if method == "risk_parity":
        return risk_parity_weights(cov)
    if method == "min_variance":
        return min_variance_weights(cov)
    if method == "max_sharpe":
        return max_sharpe_weights(mu_arr, cov, risk_free=risk_free)
    raise ValueError(f"未知 method: {method}")


def portfolio_performance(
    weights: Sequence[float],
    mu: Sequence[float],
    cov: np.ndarray,
    *,
    risk_free: float = 0.02,
) -> dict[str, Any]:
    """年化组合指标（输入 mu/cov 已年化）。"""
    w = np.asarray(weights, dtype=float).ravel()
    mu_arr = np.asarray(mu, dtype=float).ravel()
    cov = np.asarray(cov, dtype=float)
    ann_ret = float(w @ mu_arr)
    var = float(w @ cov @ w)
    ann_vol = float(np.sqrt(max(var, 0.0)))
    sharpe = (ann_ret - risk_free) / ann_vol if ann_vol > 1e-12 else 0.0

    # 分散化比率 = 加权平均波动 / 组合波动，越高说明分散效果越好
    asset_vol = np.sqrt(np.maximum(np.diag(cov), 0.0))
    weighted_vol = float(w @ asset_vol)
    div_ratio = weighted_vol / ann_vol if ann_vol > 1e-12 else 0.0

    # 风险贡献占比（用于验证风险平价是否真的平价）
    marginal = cov @ w
    rc = w * marginal
    total_rc = float(np.sum(rc))
    rc_pct = (rc / total_rc * 100.0) if abs(total_rc) > 1e-18 else np.zeros_like(w)

    return {
        "annual_return_pct": round(ann_ret * 100.0, 4),
        "annual_volatility_pct": round(ann_vol * 100.0, 4),
        "sharpe_ratio": round(sharpe, 4),
        "diversification_ratio": round(div_ratio, 4),
        "risk_contribution_pct": [round(float(v), 4) for v in rc_pct],
    }
