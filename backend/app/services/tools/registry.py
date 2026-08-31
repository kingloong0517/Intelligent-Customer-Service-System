"""Tool 注册表与统一执行入口（P3.1）

- 新增 Tool 只需实现「返回结构化 dict 的纯函数」并在 TOOLS 注册；
- execute_tool 绝不抛异常：异常兜底为结构化错误，保证 SSE 流不中断；
- build_tool_system_prompt：把 Tool 结构化结果注入 LLM system 上下文。
"""
import json
from typing import Any, Dict, List

from app.services.tools import logistics_tool, order_tool

# Tool 名称与 Agent Router 的 route 值保持一致
TOOLS: Dict[str, Dict[str, Any]] = {
    "order_query": {
        "func": order_tool.query_order,
        "description": "查询订单状态、商品、金额等信息",
    },
    "logistics_query": {
        "func": logistics_tool.query_logistics,
        "description": "查询物流 carrier、运单号、配送轨迹",
    },
}


def execute_tool(name: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
    """统一执行入口：结构化成功/失败结果，不抛异常、不产生自然语言"""
    try:
        entry = TOOLS.get(name)
        if not entry:
            return {"ok": False, "error": "unknown_tool", "message": f"未知工具: {name}"}
        return entry["func"](**(args or {}))
    except Exception as e:  # 兜底：工具异常不影响聊天主流程
        return {"ok": False, "error": "tool_exception", "message": f"{type(e).__name__}: {e}"}


def build_tool_history_system_prompt(history: List[Dict[str, Any]]) -> str:
    """把结构化 Tool History 注入 LLM system 上下文（P3.2 多步编排）

    history: [{"tool", "arguments", "result"}, ...]（保持结构化，不拼接自然语言）
    """
    steps = []
    for i, h in enumerate(history, 1):
        steps.append(
            f"步骤{i} 工具: {h['tool']}\n"
            f"参数: {json.dumps(h.get('arguments') or {}, ensure_ascii=False)}\n"
            f"结果: {json.dumps(h.get('result') or {}, ensure_ascii=False)}"
        )
    joined = "\n\n".join(steps)
    return (
        f"\n\n【工具查询结果】（共 {len(history)} 步，按执行顺序，均为本次实时查询的结构化数据）\n"
        f"```json\n{joined}\n```\n"
        "回答要求：\n"
        "1. 请综合全部步骤的结构化数据，用中文自然、专业地回答用户；\n"
        "2. ok=false 的步骤说明该次查询未成功：礼貌告知并按 message 引导用户补充信息"
        "（如提供订单号），不要编造数据，也不要使用历史对话中的旧订单号冒充本次查询结果；\n"
        "3. 不要输出 JSON 原文，不要提及「工具/函数/查询结果 JSON」等实现细节。\n"
    )
