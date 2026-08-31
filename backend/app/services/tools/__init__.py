"""Tool 层（P3.1）：独立封装的客服工具

- 每个 Tool 一个模块，返回结构化数据（dict），不生成自然语言；
- 自然语言回答由 LLM 基于 Tool 结果生成（chat_service 编排）；
- registry 提供统一执行入口与 LLM system prompt 组装。
"""
