"""模拟订单查询 Tool（P3.1）

- 纯内存 Mock 数据，不接真实订单系统；
- 返回结构化数据，不生成自然语言；最终回答由 LLM 生成；
- 查不到 / 未提供订单号也返回结构化结论，供 LLM 引导用户补充信息。
"""
from typing import Any, Dict

# 模拟订单库（key 为订单号字符串）
MOCK_ORDERS: Dict[str, Dict[str, Any]] = {
    "10001": {
        "order_id": "10001",
        "status": "已发货",
        "product": "无线耳机",
        "amount": "¥299.00",
        "created_at": "2026-08-25",
        "tracking_no": "SF1234567890",
    },
    "10002": {
        "order_id": "10002",
        "status": "待付款",
        "product": "机械键盘",
        "amount": "¥549.00",
        "created_at": "2026-08-29",
        "tracking_no": None,
    },
    "10003": {
        "order_id": "10003",
        "status": "已完成",
        "product": "USB-C 数据线",
        "amount": "¥39.00",
        "created_at": "2026-08-18",
        "tracking_no": "YT9876543210",
    },
    "10004": {
        "order_id": "10004",
        "status": "已取消",
        "product": "蓝牙音箱",
        "amount": "¥199.00",
        "created_at": "2026-08-20",
        "tracking_no": None,
    },
}


def query_order(order_id: Any = None, **_) -> Dict[str, Any]:
    """查询订单状态。args: {order_id: str|int}；返回结构化数据。"""
    oid = str(order_id or "").strip()
    if not oid:
        return {
            "ok": False,
            "error": "missing_order_id",
            "message": "用户未提供订单号，需要引导用户提供订单号",
        }
    order = MOCK_ORDERS.get(oid)
    if not order:
        return {
            "ok": False,
            "error": "not_found",
            "order_id": oid,
            "message": "订单不存在",
        }
    return {"ok": True, "order": dict(order)}
