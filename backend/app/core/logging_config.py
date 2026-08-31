"""统一日志配置（P4.1）

- Python 标准库 logging，不引入第三方日志框架；
- request_id 通过 contextvars 贯穿整个请求链路，日志 Filter 自动注入，
  业务代码无需手动传参；
- 开发环境输出到控制台；格式：时间 级别 logger名 [request_id=xxx] 消息；
- 敏感信息约定：任何地方禁止打印 API Key / JWT Secret / 密码 / Authorization；
  配置类信息只记录 configured=true/false 或脱敏标识。
"""
import logging
import sys
from contextvars import ContextVar

# 当前请求的 request_id（无请求上下文时为 None，日志中显示 -）
request_id_var: ContextVar = ContextVar("request_id", default=None)

# 日志中不使用的敏感字段黑名单（仅作文档化约定，防止后续误用）
SENSITIVE_KEYS = ("api_key", "authorization", "password", "secret", "token")


def get_request_id() -> str:
    """获取当前请求 request_id；无请求上下文返回 '-'"""
    return request_id_var.get() or "-"


class RequestIdFilter(logging.Filter):
    """把 contextvar 中的 request_id 注入每条日志记录"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [request_id=%(request_id)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """初始化根 logger（幂等：重复调用不重复挂 handler）"""
    root = logging.getLogger()
    if getattr(root, "_p41_configured", False):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)
    root.setLevel(level)
    # 收敛第三方库噪声
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    root._p41_configured = True
