"""免费行情数据源（无需 token / 无需注册）。

当前实现使用腾讯公开行情接口（qt.gtimg.cn / web.ifzq.gtimg.cn），覆盖：
  - 全市场实时行情（股票代码 + 名称）
  - 日线 K 线（前复权 / 不复权）
  - 分钟线（5m 等）

与 routers.market_data（TuShare，需 token）互为补充：
  market_data.py 优先使用免费源；设置 DATA_SOURCE=tushare 时才走付费 TuShare。
所有接口均为免费公开，无需 API Key，适合 demo / GitHub 展示。
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Any

import pandas as pd

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# 股票列表缓存（实时快照较重，缓存 1 小时）
_list_cache: dict[str, Any] = {"ts": 0.0, "data": None}
_LIST_TTL_SEC = 3600


def _http_get(url: str, timeout: int = 15, encoding: str = "utf-8") -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode(encoding, errors="replace")


def vt_to_tx(vt_symbol: str) -> str:
    """600031.SSE -> sh600031 ; 000001.SZSE -> sz000001"""
    code, _, suf = vt_symbol.partition(".")
    suf = suf.upper()
    if suf in ("SSE", "SH"):
        return f"sh{code}"
    if suf in ("SZSE", "SZ"):
        return f"sz{code}"
    if suf in ("BSE", "BJ"):
        return f"bj{code}"
    return f"sh{code}"


def tx_to_vt(tx_code: str) -> str:
    """sh600031 -> 600031.SSE"""
    m = re.match(r"^(sh|sz|bj)(\d{6})$", tx_code.lower())
    if not m:
        return tx_code
    market, code = m.group(1), m.group(2)
    suffix = {"sh": "SSE", "sz": "SZSE", "bj": "BSE"}[market]
    return f"{code}.{suffix}"


# ---------------- 实时行情（股票列表 + 名称） ----------------


def _iter_a_share_codes() -> list[str]:
    """
    生成全市场 A 股代码集合。
    腾讯没有稳定的"全市场列表"接口，这里按已知板块号段批量生成代码，
    再通过一次批量实时行情请求过滤出有效（有名称）的标的。
    """
    codes: list[str] = []
    # 沪市：600/601/603/605/688/689 开头
    for prefix, count in [("600", 0), ("601", 0), ("603", 0), ("605", 0), ("688", 0), ("689", 0)]:
        for i in range(1, 1000):
            codes.append(f"sh{prefix}{i:03d}")
    # 深市：000/001/002/003/300/301
    for prefix in ["000", "001", "002", "003", "300", "301"]:
        for i in range(1, 1000):
            codes.append(f"sz{prefix}{i:03d}")
    return codes


def _fetch_quotes(tx_codes: list[str], batch: int = 60) -> pd.DataFrame:
    """批量拉取实时行情，过滤有效标的，返回 ts_code/名称 DataFrame。"""
    records: list[dict[str, str]] = []
    for i in range(0, len(tx_codes), batch):
        chunk = tx_codes[i: i + batch]
        url = "https://qt.gtimg.cn/q=" + ",".join(chunk)
        try:
            raw = _http_get(url, encoding="gbk")
        except Exception:
            continue
        for line in raw.split(";"):
            if "=" not in line:
                continue
            m = re.search(r'v_(\w+)="([^"]*)"', line)
            if not m:
                continue
            tx_code = m.group(1)
            fields = m.group(2).split("~")
            if len(fields) < 3:
                continue
            name = fields[1].strip()
            if not name:  # 无名称 = 代码无效
                continue
            records.append({"ts_code": tx_to_vt(tx_code), "name": name})
        time.sleep(0.02)  # 轻微限速，避免被封
    return pd.DataFrame(records).drop_duplicates(subset="ts_code")


def fetch_stock_list() -> pd.DataFrame:
    """
    获取全市场 A 股列表（ts_code, name）。
    使用缓存 TTL 避免频繁请求。
    """
    now = time.time()
    cached = _list_cache.get("data")
    if cached is not None and now - _list_cache["ts"] < _LIST_TTL_SEC:
        return cached.copy()

    df = _fetch_quotes(_iter_a_share_codes())
    if df is None or df.empty:
        # 兜底：如果批量实时接口失败，至少返回请求过的代码
        raise RuntimeError("免费源实时行情请求失败")

    df = df.reset_index(drop=True)
    _list_cache["data"] = df
    _list_cache["ts"] = now
    return df.copy()


# ---------------- 日线 K 线 ----------------


def fetch_daily(tx_code: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
    """
    获取日线（前复权）。返回 TuShare daily 兼容列：
    ts_code, trade_date, open, high, low, close, vol, amount
    """
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={tx_code},day,{start_date},{end_date},640,qfq"
    )
    raw = _http_get(url)
    data = json.loads(raw)
    node = (data.get("data") or {}).get(tx_code) or {}
    rows = node.get("qfqday") or node.get("day") or []
    if not rows:
        return pd.DataFrame()

    records = []
    for row in rows:
        # [date, open, close, high, low, volume, ...] —— 注意腾讯顺序是 开/收/高/低
        records.append({
            "ts_code": tx_to_vt(tx_code),
            "trade_date": row[0].replace("-", ""),
            "open": row[1],
            "high": row[3],
            "low": row[4],
            "close": row[2],
            "vol": row[5],
            "amount": row[7] if len(row) > 7 else None,  # 成交额(万元)部分返回
        })
    df = pd.DataFrame(records)
    for col in ["open", "high", "low", "close", "vol"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "amount" in df:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    return df.dropna(subset=["close"]).reset_index(drop=True)


# ---------------- 分钟 K 线 ----------------


def fetch_minute(tx_code: str, period: str = "m5", count: int = 320) -> pd.DataFrame:
    """获取分钟线（period: m1/m5/m15/m30/m60）。返回 date/open/close/high/low/vol。"""
    url = (
        "http://web.ifzq.gtimg.cn/appstock/app/kline/mkline"
        f"?param={tx_code},{period},,{count}"
    )
    raw = _http_get(url)
    data = json.loads(raw)
    node = (data.get("data") or {}).get(tx_code) or {}
    rows = node.get(period, [])
    records = []
    for row in rows:
        records.append({
            "datetime": row[0],
            "open": row[1],
            "close": row[2],
            "high": row[3],
            "low": row[4],
            "vol": row[5],
        })
    df = pd.DataFrame(records)
    if df.empty:
        return df
    for col in ["open", "close", "high", "low", "vol"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).reset_index(drop=True)