"""模拟物流查询 Tool（P3.1）

- 纯内存 Mock 数据，不接第三方物流 API；
- 返回结构化数据（状态 + 轨迹），不生成自然语言；
- 与订单查询共用订单号维度（模拟场景：一个订单一个包裹）。
"""
from typing import Any, Dict

# 模拟物流数据（key 为订单号字符串）
MOCK_LOGISTICS: Dict[str, Dict[str, Any]] = {
    "10001": {
        "order_id": "10001",
        "carrier": "顺丰速运",
        "tracking_no": "SF1234567890",
        "status": "运输中",
        "trail": [
            {"time": "2026-08-27 16:20", "event": "商家已发货，包裹已揽收"},
            {"time": "2026-08-28 09:12", "event": "包裹已从上海转运中心发出"},
            {"time": "2026-08-28 21:40", "event": "到达杭州转运中心"},
            {"time": "2026-08-29 07:05", "event": "快件派送中，派送员：张师傅 138****0000"},
        ],
    },
    "10003": {
        "order_id": "10003",
        "carrier": "圆通速递",
        "tracking_no": "YT9876543210",
        "status": "已签收",
        "trail": [
            {"time": "2026-08-19 10:00", "event": "商家已发货"},
            {"time": "2026-08-20 14:30", "event": "到达收件城市转运中心"},
            {"time": "2026-08-21 09:15", "event": "快件已签收，签收人：本人"},
        ],
    },
}


def query_logistics(order_id: Any = None, **_) -> Dict[str, Any]:
    """查询物流轨迹。args: {order_id: str|int}；返回结构化数据。"""
    oid = str(order_id or "").strip()
    if not oid:
        return {
            "ok": False,
            "error": "missing_order_id",
            "message": "用户未提供订单号，需要引导用户提供订单号",
        }
    record = MOCK_LOGISTICS.get(oid)
    if not record:
        return {
            "ok": False,
            "error": "not_found",
            "order_id": oid,
            "message": "未找到该订单的物流信息",
        }
    return {"ok": True, "logistics": dict(record)}
