"""轻量级 Tool Orchestrator（P3.2）

职责：
- 管理一次 Agent Task 的多步 Tool 调用；
- 维护结构化 Tool History（tool / arguments / result）；
- 依据上一步结构化结果决定是否继续调用下一个 Tool；
- 把前置 Tool 的结构化结果作为后续 Tool 的参数
  （如 order_query 返回 order_id/tracking_no → logistics_query）；
- 不生成自然语言：最终回答由 LLM 基于完整 Tool History 生成。

执行循环由 chat_service 驱动（SSE 渲染层），本模块只做纯决策：
  next_step() → 执行方执行 → record() → 内部决定下一步 → next_step() ...
不引入任何 Agent 框架。
"""
from typing import Any, Dict, List, Optional

from app.core.config import MAX_TOOL_STEPS


class ToolStep:
    """一次待执行的 Tool 调用计划"""

    __slots__ = ("tool", "arguments")

    def __init__(self, tool: str, arguments: Optional[Dict[str, Any]] = None):
        self.tool = tool
        self.arguments = dict(arguments or {})


class ToolOrchestrator:
    """单次对话的 Tool 编排器

    - history 为结构化 Tool History：[{"tool", "arguments", "result"}, ...]
    - max_steps 上限防止 Tool 链无限循环（达到上限后停止继续调用，
      交给 LLM 基于已有结果回答）；
    - 任一步失败（ok=false）即停止链式调用，保留已有结果供 LLM 回答；
    - 链式规则（P3.2 最小实现，独立于 Router，不重写路由）：
        order_query 成功 且 status == "已发货" 且有 order_id/tracking_no
        → 继续 logistics_query(order_id)；否则停止。
      无 tracking_no 的订单不调用物流查询。
    """

    def __init__(
        self,
        route: str,
        first_tool: Optional[str] = None,
        first_args: Optional[Dict[str, Any]] = None,
        max_steps: Optional[int] = None,
    ):
        self.route = route
        self.max_steps = max_steps or MAX_TOOL_STEPS
        self.history: List[Dict[str, Any]] = []
        self.limit_hit = False
        self._pending: Optional[ToolStep] = (
            ToolStep(first_tool, first_args) if first_tool else None
        )

    def next_step(self) -> Optional[ToolStep]:
        """取出下一个待执行步骤（取出后置空，由执行方决定是否 record）"""
        step, self._pending = self._pending, None
        return step

    def record(self, tool: str, arguments: Dict[str, Any], result: Dict[str, Any]) -> None:
        """记录一步执行结果，并决策下一步"""
        self.history.append(
            {"tool": tool, "arguments": dict(arguments or {}), "result": result}
        )
        self._pending = self._decide_next()

    def _decide_next(self) -> Optional[ToolStep]:
        if len(self.history) >= self.max_steps:
            self.limit_hit = True
            return None

        last = self.history[-1]
        result = last.get("result") or {}
        if not result.get("ok"):
            # 上一步失败：停止 Tool 链，已有结果仍交给 LLM 回答
            return None

        if last["tool"] == "order_query":
            order = result.get("order") or {}
            if (
                order.get("status") == "已发货"
                and order.get("order_id")
                and order.get("tracking_no")
                and not any(h["tool"] == "logistics_query" for h in self.history)
            ):
                return ToolStep("logistics_query", {"order_id": order["order_id"]})
        return None
