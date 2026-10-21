"""体检并修复 vn.py 本地库中的损坏行情数据。

背景：部分标的的日线出现非正收盘价 / OHLC 不自洽 / 异常跳变，
这类数据会让回测输出看似精确但完全无意义的指标（例如夏普 -1291 万）。

核心逻辑已抽到 `trader/examples/cta_backtesting/market_data_tools.py`，
本脚本只负责 CLI 与报告打印。

用法：
  python scripts/repair_market_data.py            # 只修复 BAD 标的
  python scripts/repair_market_data.py --dry-run  # 只体检，不修改
  python scripts/repair_market_data.py --all      # 所有标的全部重拉
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "trader"))

from vnpy.trader.database import get_database  # noqa: E402

from examples.cta_backtesting.market_data_tools import (  # noqa: E402
    diagnose_all,
    sync_symbol,
)


def print_diagnosis(rows: list[dict], title: str) -> None:
    print(f"\n=== {title} ===")
    for r in rows:
        flag = "BAD" if r["bad"] else "OK "
        if r["n"] == 0:
            print(f"{flag} {r['symbol']}.{r['exchange'].value} n=0（库中无数据）")
            continue
        print(
            f"{flag} {r['symbol']}.{r['exchange'].value} n={r['n']} "
            f"range={r['lo']:.3f}~{r['hi']:.3f} "
            f"nonpos={r['nonpos']} ohlc_bad={r['ohlc_bad']} jumps>50%={r['jumps']} "
            f"max_gap={r['max_gap_days']}d"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只体检不修改")
    parser.add_argument("--all", action="store_true", help="所有标的全部重拉")
    args = parser.parse_args()

    db = get_database()
    before = diagnose_all(db)
    print_diagnosis(before, "修复前体检")

    if args.dry_run:
        return

    targets = before if args.all else [r for r in before if r["bad"]]
    if not targets:
        print("\n没有需要修复的标的。")
        return

    print(f"\n将修复 {len(targets)} 个标的：{', '.join(r['symbol'] for r in targets)}")
    repaired = 0
    for row in targets:
        try:
            sync_symbol(db, row["symbol"], row["exchange"])
            repaired += 1
        except Exception as e:
            print(f"  [FAIL] {row['symbol']}.{row['exchange'].value}: {e}")

    after = diagnose_all(db)
    print_diagnosis(after, "修复后体检")

    remaining = [r for r in after if r["bad"]]
    print(f"\nRESULT repaired={repaired}/{len(targets)} remaining_bad={len(remaining)}")
    if remaining:
        print("仍不合格：" + ", ".join(f"{r['symbol']}.{r['exchange'].value}" for r in remaining))


if __name__ == "__main__":
    main()
