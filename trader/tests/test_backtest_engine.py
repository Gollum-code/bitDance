"""CTA 回测引擎与策略族加载的冒烟测试。

运行：python -m pytest trader/tests -q
需要：vnpy_ctastrategy、pandas（系统环境已装）。
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting"))

from run_rewritten_strategy_backtest import build_setting, load_strategy_class  # noqa: E402


def test_manifest_loads_99_rows(tmp_path):
    """manifest.csv 应包含 99 个策略映射，且全部可加载。"""
    folder = Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting" / "rewritten_strategies"
    import csv

    rows = list(csv.DictReader((folder / "manifest.csv").open(encoding="utf-8")))
    assert len(rows) == 99, f"期望 99 条映射，实际 {len(rows)}"

    loaded = 0
    for row in rows:
        cls, meta = load_strategy_class(row["strategy_id"])
        assert cls is not None
        assert meta["class_name"] == cls.__name__
        loaded += 1
    assert loaded == 99


@pytest.mark.parametrize("sid", ["01", "09", "90", "12", "99"])
def test_build_setting_fills_params(sid):
    """每个族的默认参数 + 用户覆盖都能正确生成 setting。"""
    cls, row = load_strategy_class(sid)
    setting = build_setting(cls, row, {})
    # 所有 parameters 必须存在值
    for key in cls.parameters:
        assert key in setting, f"{sid} 族缺少参数 {key}"
    # 用户覆盖生效
    setting2 = build_setting(cls, row, {"fixed_size": 999})
    assert setting2["fixed_size"] == 999


def test_family_imports_all_clean():
    """23 个族策略都能 import（无语法/依赖错误）。"""
    import importlib

    folder = Path(__file__).resolve().parent.parent / "examples" / "cta_backtesting" / "rewritten_strategies"
    sys.path.insert(0, str(folder.parent))
    family_files = sorted(folder.glob("family_*.py"))
    assert len(family_files) == 23, f"期望 23 个族策略，实际 {len(family_files)}"
    for f in family_files:
        mod = importlib.import_module(f"rewritten_strategies.{f.stem}")
        assert mod is not None
