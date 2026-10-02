from openai import OpenAI
from ai.config import *
from datetime import datetime
import json
from datetime import datetime, date
import numpy as np

def _json_serializable(obj):
    """把无法 JSON 序列化的类型转为 Python 原生类型"""
    # 处理日期时间
    if isinstance(obj, (datetime, date)):
        return obj.strftime("%Y-%m-%d")

    # 处理 numpy 类型
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)

    raise TypeError(f"Type {type(obj)} not serializable")

def generate_backtest_report(
    stats: dict,
    vt_symbol: str,
    interval,
    start,
    end,
    rate: float,
    slippage: float,
    size: int,
    pricetick: float,
    capital: float,
    strategy: str
) -> str | None:
    """
        生成回测报告

        Parameters
        ----------
        stats : dict
            回测统计结果字典
        vt_symbol : str
            合约代码，如 "IF2406.CFFEX"
        interval : Interval
            K线周期，如 Interval.DAILY
        start : datetime
            回测开始日期
        end : datetime
            回测结束日期
        rate : float
            手续费率
        slippage : float
            滑点
        size : int
            合约乘数
        pricetick : float
            最小变动价位
        capital : float
            初始资金
        strategy : str
            策略名称或策略类路径

        Returns
        -------
        str | None
            生成的 Markdown 报告文本；调用失败返回 None
        """
    if not token:
        print("AI 问答未配置：请设置环境变量 MOONSHOT_API_KEY")
        return None

    client = OpenAI(
        api_key=token,
        base_url=kimi_url,
    )

    # 系统提示词
    system_prompt = f"""现在你是股票量化分析大师，你将以 markdown 格式生成对于该股票使用某种量化策略的分析报告。今天的日期是 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}。"""

    # 构建参数配置部分
    config = {
        "description": "回测参数配置",
        "parameters": {
            "vt_symbol": {
                "type": "string",
                "description": "合约代码",
                "value": vt_symbol
            },
            "interval": {
                "type": "Interval",
                "description": "K线周期",
                "value": str(interval)
            },
            "start": {
                "type": "datetime",
                "description": "回测开始日期",
                "value": start.strftime("%Y-%m-%d %H:%M:%S") if isinstance(start, datetime) else str(start)
            },
            "end": {
                "type": "datetime",
                "description": "回测结束日期",
                "value": end.strftime("%Y-%m-%d %H:%M:%S") if isinstance(end, datetime) else str(end)
            },
            "rate": {
                "type": "float",
                "description": "手续费率",
                "value": str(rate)
            },
            "slippage": {
                "type": "float",
                "description": "滑点",
                "value": str(slippage)
            },
            "size": {
                "type": "integer",
                "description": "合约乘数",
                "value": str(size)
            },
            "pricetick": {
                "type": "float",
                "description": "最小变动价位",
                "value": str(pricetick)
            },
            "capital": {
                "type": "float",
                "description": "初始资金",
                "value": str(capital)
            },
            "strategy": {
                "type": "string",
                "description": "策略名称或策略类路径",
                "value": strategy
            }
        }
    }

    # 构建回测结果部分
    results = {
        "description": "回测结果",
        "results": stats  # stats 已经是字典，保持原样
    }

    # 合并为完整的 user prompt，使用 json.dumps 确保格式正确
    user_prompt = (
            json.dumps(config, ensure_ascii=False, indent=2)
            + ",\n"
            + json.dumps(results, ensure_ascii=False, indent=2, default=_json_serializable)
    )

    # 调用 Kimi API 生成报告
    try:
        completion = client.chat.completions.create(
            model="kimi-k2.5",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2048,
        )
        report = completion.choices[0].message.content
        return report if isinstance(report, str) else str(report)
    except Exception as exc:
        print(f"调用 Kimi API 生成报告失败：{exc}")
        return None
