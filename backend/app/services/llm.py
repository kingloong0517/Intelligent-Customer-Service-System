"""
LLM 服务层：封装 DeepSeek（OpenAI 兼容协议）的流式对话调用。

设计要点：
- 与 chat API 完全解耦：只接收 messages，返回文本片段的异步生成器；
- API Key 从环境变量读取（core/config），绝不写死在代码中；
- 所有异常统一转换为 LLMError，由上层决定降级策略（模板回复）；
- 通过 DEEPSEEK_BASE_URL / DEEPSEEK_MODEL 环境变量即可切换其他 OpenAI 兼容模型服务。
"""
import inspect
import logging
import time
from typing import AsyncGenerator, List, Dict, Optional

from app.core.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)

logger = logging.getLogger("llm")


class LLMError(Exception):
    """LLM 调用失败（网络/超时/鉴权/无 Key 等），上层据此走降级逻辑"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code  # 可获得时记录 HTTP 状态码（如 402），绝不包含 Key


# AsyncOpenAI 客户端惰性单例（首次调用时创建，避免 import 期连接开销）
_client = None


def _get_client():
    global _client
    if _client is None:
        if not DEEPSEEK_API_KEY:
            raise LLMError("未配置 DEEPSEEK_API_KEY")
        from openai import AsyncOpenAI

        _client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=LLM_TIMEOUT,
            max_retries=0,  # 重试策略交给上层降级逻辑，避免叠加超时
        )
    return _client


async def stream_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """
    流式对话：逐段 yield 模型生成的文本增量。

    :param messages: OpenAI 兼容的 messages 数组 [{"role": ..., "content": ...}]
    :raises LLMError: 无 Key、连接失败、超时、HTTP 错误等任何调用异常
    """
    client = _get_client()
    stream = None
    model_name = model or DEEPSEEK_MODEL
    started = time.perf_counter()
    # P4.1 可观测性：只记录 provider/model/状态/耗时，绝不记录 Key 与完整 Header
    logger.info("provider=deepseek model=%s stream=start", model_name)
    try:
        stream = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=LLM_TEMPERATURE if temperature is None else temperature,
            max_tokens=LLM_MAX_TOKENS if max_tokens is None else max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
        logger.info(
            "provider=deepseek model=%s stream=done duration_ms=%d",
            model_name, int((time.perf_counter() - started) * 1000),
        )
    except Exception as e:  # 统一收敛为 LLMError，屏蔽 SDK 异常类型差异
        status_code = getattr(e, "status_code", None)
        logger.warning(
            "provider=deepseek model=%s stream=error error_type=%s status_code=%s duration_ms=%d",
            model_name, type(e).__name__, status_code,
            int((time.perf_counter() - started) * 1000),
        )
        raise LLMError(f"LLM 调用失败: {type(e).__name__}: {e}", status_code=status_code) from e
    finally:
        # 客户端断开时正确关闭上游流，避免连接泄漏
        if stream is not None:
            try:
                closed = stream.close()
                if inspect.isawaitable(closed):
                    await closed
            except Exception:
                pass
