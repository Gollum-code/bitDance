"""行情：TuShare 拉取 A 股列表与日线，可选同步到 vn.py 本地库供回测引擎读取。"""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import tushare as ts
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from routers.tushare_bars import bars_from_tushare_daily_df, save_bars_to_database

router = APIRouter()

# TuShare 配置：通过环境变量注入（避免把真实 token / 私有网关提交到仓库）。
#   TUSHARE_TOKEN       TuShare 官方 token（可选；配置后直连官方接口）
#   TUSHARE_HTTP_URL    自建/镜像网关地址（可选；配置后覆盖默认官方地址）
_DEFAULT_TOKEN = ""
_DEFAULT_HTTP_URL = ""

_stocks_cache: dict[str, Any] = {"df": None, "loaded_at": 0.0}
_STOCKS_TTL_SEC = 3600


def _token() -> str:
    return os.environ.get("TUSHARE_TOKEN", _DEFAULT_TOKEN)


def _http_url() -> str | None:
    raw = os.environ.get("TUSHARE_HTTP_URL", _DEFAULT_HTTP_URL)
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def get_pro():
    token = _token()
    if not token:
        raise RuntimeError("未配置 TuShare：请设置环境变量 TUSHARE_TOKEN")
    pro = ts.pro_api(token)
    url = _http_url()
    if url:
        pro._DataApi__http_url = url.rstrip("/") + "/"
    return pro


def ts_code_to_vt_symbol(ts_code: str) -> str:
    """600000.SH -> 600000.SSE ; 000001.SZ -> 000001.SZSE"""
    code, suf = ts_code.upper().split(".")
    if suf == "SH":
        return f"{code}.SSE"
    if suf == "SZ":
        return f"{code}.SZSE"
    if suf == "BJ":
        return f"{code}.BSE"
    return f"{code}.{suf}"


def _normalize_yyyymmdd(d: str) -> str:
    s = d.strip().replace("-", "")
    if len(s) != 8 or not s.isdigit():
        raise ValueError(f"日期格式应为 YYYYMMDD 或 YYYY-MM-DD: {d}")
    return s


class SyncVnpyRequest(BaseModel):
    ts_code: str = Field(..., description="TuShare 代码，如 600000.SH")
    start_date: str = Field(..., description="开始 YYYYMMDD 或 YYYY-MM-DD")
    end_date: str = Field(..., description="结束 YYYYMMDD 或 YYYY-MM-DD")


def _load_all_listed_stocks(pro) -> pd.DataFrame:
    now = time.time()
    cached = _stocks_cache["df"]
    loaded_at = float(_stocks_cache["loaded_at"] or 0)
    if cached is not None and (now - loaded_at) < _STOCKS_TTL_SEC:
        return cached

    df = pro.stock_basic(
        list_status="L",
        fields="ts_code,symbol,name,area,industry,list_date",
    )
    if df is None:
        df = pd.DataFrame()
    _stocks_cache["df"] = df
    _stocks_cache["loaded_at"] = now
    return df


@router.get("/stocks")
def search_stocks(
    q: str | None = Query(None, description="代码或名称关键字，空则返回前若干条"),
    limit: int = Query(80, ge=1, le=500),
):
    try:
        pro = get_pro()
        df = _load_all_listed_stocks(pro)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TuShare stock_basic 失败: {e}") from e

    if df is None or df.empty:
        return {"items": [], "message": "未返回股票基础数据"}

    work = df.copy()
    qq = (q or "").strip()
    if qq:
        mask = work["ts_code"].str.contains(qq.upper(), na=False) | work["name"].astype(str).str.contains(
            qq, case=False, na=False
        )
        work = work.loc[mask]
    work = work.sort_values("ts_code").head(limit)

    records = work.to_dict(orient="records")
    for r in records:
        r["vt_symbol"] = ts_code_to_vt_symbol(str(r["ts_code"]))
    return {"items": records, "count": len(records)}


@router.get("/daily")
def get_daily_bars(
    ts_code: str = Query(..., description="如 600000.SH"),
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
):
    ts_code = ts_code.strip().upper()
    try:
        s, e = _normalize_yyyymmdd(start_date), _normalize_yyyymmdd(end_date)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    try:
        pro = get_pro()
        df = pro.query("daily", ts_code=ts_code, start_date=s, end_date=e)
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"TuShare daily 失败: {ex}") from ex

    if df is None or df.empty:
        return {
            "ts_code": ts_code,
            "vt_symbol": ts_code_to_vt_symbol(ts_code),
            "bars": [],
            "message": "该区间无日线数据（或代码无效）",
        }

    df = df.sort_values("trade_date")
    bars: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        td = row["trade_date"]
        if isinstance(td, str):
            td_str = td.replace("-", "")[:8]
        else:
            td_str = str(int(td))
        bars.append(
            {
                "date": f"{td_str[:4]}-{td_str[4:6]}-{td_str[6:8]}",
                "trade_date": td_str,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "vol": float(row["vol"]),
                "amount": float(row["amount"]),
            }
        )

    last = bars[-1] if bars else None
    return {
        "ts_code": ts_code,
        "vt_symbol": ts_code_to_vt_symbol(ts_code),
        "bars": bars,
        "last": last,
        "count": len(bars),
    }


@router.post("/sync-vnpy")
def sync_bars_to_vnpy(body: SyncVnpyRequest):
    """从 TuShare 拉日线并写入 vn.py 数据库，供 CTA 回测 load_data() 使用。"""
    ts_code = body.ts_code.strip().upper()
    try:
        s, e = _normalize_yyyymmdd(body.start_date), _normalize_yyyymmdd(body.end_date)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err

    try:
        pro = get_pro()
        df = pro.query("daily", ts_code=ts_code, start_date=s, end_date=e)
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"TuShare daily 失败: {ex}") from ex

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="该区间无数据，无法同步")

    df = df.sort_values("trade_date")
    try:
        bars = bars_from_tushare_daily_df(df)
        n = save_bars_to_database(bars)
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"写入 vn.py 数据库失败: {ex}") from ex

    return {
        "status": "ok",
        "ts_code": ts_code,
        "vt_symbol": ts_code_to_vt_symbol(ts_code),
        "imported_count": n,
        "start_date": s,
        "end_date": e,
        "message": f"已写入 {n} 条日线到本地库，可在「我的策略」用 vt_symbol={ts_code_to_vt_symbol(ts_code)} 回测",
    }
