"""Agent 层（P3.1）：统一 Agent Router 与执行编排

- router.py：路由决策（normal_chat / rag / order_query / logistics_query / human_service）
  + prepare_agent_plan 编排（RAG 检索 / Tool 参数 / LLM 上下文组装）；
- 未来多 Agent / Tool Calling 扩展直接替换或增强本层，调用方（API 层）不感知。
"""
