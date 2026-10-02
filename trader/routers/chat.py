# routers/chat.py
import os
import uuid
from openai import AsyncOpenAI
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

import ai.config as config

router = APIRouter()

# ==================== 配置 ====================
# API Key 由环境变量 MOONSHOT_API_KEY 注入；未配置时 AI 问答返回提示而非报错。
KIMI_MODEL = os.getenv("KIMI_MODEL", "kimi-k2.5")
client = AsyncOpenAI(
    api_key=config.token or "not-configured",
    base_url=config.kimi_url,
)


def _require_api_key() -> None:
    if not config.token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 问答未配置：请设置环境变量 MOONSHOT_API_KEY 后重启 trader 服务",
        )

# System Prompt（每次请求必带，不被截断）
SYSTEM_PROMPT = """你是 bitDance 平台的「资深量化研究与风险管理顾问」，面向专业交易者与策略开发者作答。

## 输出格式（强制）
- 所有对用户可见的回复必须使用 **GitHub Flavored Markdown** 排版。
- 结构：优先用 `##` / `###` 分层；结论与要点用有序/无序列表；可比指标优先用 Markdown **表格**；关键数字与结论用 **粗体**；代码或参数名用行内 `` ` ``；较长公式或代码片段用围栏代码块并标注语言（如 ```text）。
- 默认语气：**正式、克制、可复核**；避免口语化套话、emoji、以及“综上所述”式空洞收尾。

## 专业准则
- **证据约束**：仅基于用户明确提供的回测数据、参数或上下文推理；不得捏造净值、收益率、成交笔数等数值。缺数据时列出需要的最小数据清单。
- **风险披露**：任何绩效解读须区分样本内/外与过拟合风险；策略结论须附带适用条件与失效情景；不对未来收益作保证性表述。
- **分析深度**：涉及回撤、参数敏感性、信号质量时，说明度量口径（时间区间、基准、成本假设等）；多结论时给出优先级与相互制约关系。
- **术语**：中英术语首次出现可附简短中文释义或括号标注；避免无定义的英文缩写堆砌。

## 内部复核（不必写出）
逻辑一致性 → 假设是否显式 → 风险是否覆盖 → Markdown 结构是否便于扫读。

## 禁忌
禁止政治敏感、色情暴力内容；禁止违法投资建议。

## 回测报告类请求
当用户要求「生成报告」「回测报告」或消息中包含结构化回测 JSON 时：
1. 在报告中显式区分「来自数据的结论」与「基于假设的推断」。
2. 建议章节：**执行摘要** → **收益与风险指标**（含最大回撤、夏普等，仅引用提供数据）→ **持仓/敞口与集中度**（若数据支持）→ **交易统计**（笔数、胜率、盈亏分布等，仅引用提供数据）→ **逐期/逐笔层面解读与信号质量**（数据不足须声明）→ **局限性与风险提示**。
3. 若用户未附带任何回测结果数据，应简要说明需在客户端完成回测后再生成报告（勿编造数值）。
"""
SYSTEM_MESSAGES = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT,
    },
]

# ==================== 内存存储 ====================
# 结构: {conversation_id: [{"role": "user", "content": "..."}, ...]}
conversation_store: Dict[str, List[dict]] = {}


# ==================== 请求/响应模型 ====================
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(default=None, description="为空则创建新会话")
    message: str = Field(..., min_length=1, description="用户当前消息")
    model: Optional[str] = Field(default=None, description="覆盖默认模型")
    max_history: Optional[int] = Field(default=20, ge=1, le=100, description="保留的最大历史消息数")
    max_tokens: Optional[int] = Field(default=2048, ge=1, le=8192)


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    model: str
    usage: Optional[dict] = None


# ==================== 核心函数 ====================
def make_messages(conv_id: str, user_input: str, max_history: int = 20) -> tuple[List[dict], str]:
    """
    构建请求消息列表：
    1. 添加 system messages（必带）
    2. 追加用户新消息到历史
    3. 截断历史，仅保留最新 n 条
    4. 返回 (完整消息列表, 更新后的 conv_id)
    """
    # 获取历史（无则初始化）
    history = conversation_store.get(conv_id, [])

    # 追加用户新消息
    history.append({"role": "user", "content": user_input})

    # 截断：仅保留最新 max_history 条
    if len(history) > max_history:
        history = history[-max_history:]

    # 构建最终消息：system + 截断后的历史
    messages = []
    messages.extend(SYSTEM_MESSAGES)
    messages.extend(history)

    # 保存截断后的历史
    conversation_store[conv_id] = history

    return messages, conv_id


# ==================== 路由 ====================
@router.post(
    "/completions",
    response_model=ChatResponse,
    summary="多轮非流式对话",
    description="仿照官方多轮对话实现，自动维护上下文并控制长度"
)
async def chat(request: ChatRequest):
    _require_api_key()

    # 1. 确定/创建会话 ID
    conv_id = request.conversation_id or str(uuid.uuid4())

    # 2. 构建消息（自动截断历史）
    messages, conv_id = make_messages(conv_id, request.message, request.max_history)

    # 3. 调用 Kimi API（使用官方 openai SDK）
    try:
        completion = await client.chat.completions.create(
            model=request.model or KIMI_MODEL,
            messages=messages,
            max_tokens=request.max_tokens,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Kimi API 调用失败: {str(e)}"
        )

    # 4. 提取助手回复
    assistant_message = completion.choices[0].message
    print(assistant_message)
    assistant_content = assistant_message.content
    usage = completion.usage.model_dump() if completion.usage else None

    # 5. 将助手回复添加到历史（保持记忆）
    history = conversation_store.get(conv_id, [])
    history.append({
        "role": "assistant",
        "content": assistant_content,
    })
    conversation_store[conv_id] = history

    # 6. 返回
    return ChatResponse(
        conversation_id=conv_id,
        reply=assistant_content,
        model=request.model or KIMI_MODEL,
        usage=usage,
    )


@router.post(
    "/clear",
    summary="清空会话历史",
    description="传入 conversation_id 清空对应会话"
)
async def clear_conversation(conversation_id: str):
    if conversation_id in conversation_store:
        del conversation_store[conversation_id]
        return {"message": "会话已清空", "conversation_id": conversation_id}
    return {"message": "会话不存在或已过期", "conversation_id": conversation_id}


@router.get(
    "/history/{conversation_id}",
    summary="查看会话历史",
    description="调试用：查看某会话的当前消息列表"
)
async def get_history(conversation_id: str):
    history = conversation_store.get(conversation_id, [])
    return {
        "conversation_id": conversation_id,
        "message_count": len(history),
        "messages": history,
    }