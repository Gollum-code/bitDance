import argparse
import os
from typing import Optional

import pandas as pd
import tushare as ts


DEFAULT_TOKEN = os.getenv("TUSHARE_TOKEN", "")
DEFAULT_CUSTOM_URL = os.getenv("TUSHARE_HTTP_URL", "")


def get_daily_kline(
    ts_code: str,
    start_date: str,
    end_date: str,
    token: Optional[str] = None,
    custom_url: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch daily K-line data from TuShare Pro.

    Args:
        ts_code: Security code, e.g. 600031.SH
        start_date: Start date in YYYYMMDD
        end_date: End date in YYYYMMDD
        token: TuShare token. If None, use TUSHARE_TOKEN env var.
        custom_url: Optional TuShare-compatible endpoint. Defaults to env TUSHARE_HTTP_URL.

    Returns:
        DataFrame sorted by trade_date ascending.
    """
    token = token or DEFAULT_TOKEN or os.getenv("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("Missing token. Set TUSHARE_TOKEN or pass --token.")

    pro = ts.pro_api(token)

    # 仅在显式配置了自定义网关时覆盖默认地址
    effective_url = custom_url or DEFAULT_CUSTOM_URL
    if effective_url:
        pro._DataApi__http_url = effective_url

    df = pro.query(
        "daily",
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    return df.sort_values("trade_date").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch daily K-line data via TuShare")
    parser.add_argument("--ts-code", default="600031.SH", help="Security code, e.g. 600031.SH")
    parser.add_argument("--start", default="20250101", help="Start date YYYYMMDD")
    parser.add_argument("--end", default="20250409", help="End date YYYYMMDD")
    parser.add_argument("--token", default=None, help="TuShare token (optional)")
    parser.add_argument("--custom-url", default=DEFAULT_CUSTOM_URL, help="TuShare-compatible endpoint")
    parser.add_argument("--out", default="daily_kline.csv", help="Output CSV path")
    args = parser.parse_args()

    df = get_daily_kline(
        ts_code=args.ts_code,
        start_date=args.start,
        end_date=args.end,
        token=args.token,
        custom_url=args.custom_url,
    )

    if df.empty:
        print("No data returned.")
        return

    print(df.head())
    print(df.tail())
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"Saved: {args.out} (rows={len(df)})")


if __name__ == "__main__":
    main()
