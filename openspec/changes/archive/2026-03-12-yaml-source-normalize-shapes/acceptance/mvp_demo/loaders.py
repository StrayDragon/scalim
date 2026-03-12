from __future__ import print_function

from datetime import datetime
from typing import Dict, List, Optional


def _dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


# -----------------------------
# Sanitized in-memory dataset
# -----------------------------
# 目标:提供一个“无需 DB、可复现实例”的最小样本.
#
# 真实业务中行规模可能很大;这里用极小数据,只用于验证口径/语义/normalize 行为与确定性.

_ORDERS = [
    {
        "order_id": 10001,
        "user_id": 501,
        "cs_id": 9001,
        "institution_code": "INS_A",
        "channel": "direct",
        "pay_datetime": _dt("2026-01-01 10:00:00"),
        "amount_cent": 12000,
        "is_quick_pay": 1,
    },
    {
        "order_id": 10002,
        "user_id": 502,
        "cs_id": 9001,
        "institution_code": "INS_A",
        "channel": "partner",
        "pay_datetime": _dt("2026-01-02 09:30:00"),
        "amount_cent": 8000,
        "is_quick_pay": 0,
    },
    {
        "order_id": 10003,
        "user_id": 501,
        "cs_id": 9002,
        "institution_code": "INS_B",
        "channel": "direct",
        "pay_datetime": _dt("2026-01-03 18:15:00"),
        "amount_cent": 30000,
        "is_quick_pay": 1,
    },
]

_INSTITUTIONS = {
    "INS_A": {"institution_code": "INS_A", "institution_name": "Inst A", "is_pay_by_card": 1},
    "INS_B": {"institution_code": "INS_B", "institution_name": "Inst B", "is_pay_by_card": 0},
}

_CUSTOM_SERVICES = {
    9001: {"cs_id": 9001, "cs_name": "CS Alice", "group_name": "Group 1", "wechat_name": "wx_alice"},
    9002: {"cs_id": 9002, "cs_name": "CS Bob", "group_name": "Group 2", "wechat_name": "wx_bob"},
}


def load_paid_orders_rows(*, params: Dict[str, object]) -> List[Dict[str, object]]:
    """主事实流:支付订单宽表(脱敏版).

    约定:按 pay_datetime 落窗过滤,返回 list[dict] 行.
    """
    start_dt = params.get("start_datetime")
    end_dt = params.get("end_datetime")
    if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime):
        raise TypeError("params.start_datetime/end_datetime must be datetime")
    rows = [r for r in _ORDERS if start_dt <= r["pay_datetime"] < end_dt]
    # 保持稳定排序,便于对拍
    rows.sort(key=lambda x: (x.get("pay_datetime"), x.get("order_id")))
    return rows


def load_institutions_dict(*, params: Optional[Dict[str, object]] = None) -> Dict[str, Dict[str, object]]:
    """小表:机构信息."""
    _ = params
    return dict(_INSTITUTIONS)


def load_custom_services_dict(*, params: Optional[Dict[str, object]] = None) -> Dict[int, Dict[str, object]]:
    """小表:客服信息."""
    _ = params
    return dict(_CUSTOM_SERVICES)


# -----------------------------
# “非理想形状”示例(不用于当前 demo demand)
# -----------------------------


def example_loader_order_recommends_list(*, params: Dict[str, object]) -> List[Dict[str, object]]:
    """形状:list[dict],需要 normalize/list_to_map 才能变成 keyed mapping."""
    order_id_set = set(params.get("order_id_set") or [])
    return (
        [
            {"order_id": 10001, "recommend_cs_id": 9002},
            {"order_id": 10001, "recommend_cs_id": 9002},  # duplicate row
            {"order_id": 10003, "recommend_cs_id": 9001},
        ]
        if order_id_set
        else []
    )


def example_loader_clearn_reason_nested_dict(*, params: Dict[str, object]) -> Dict[int, Dict[object, object]]:
    """形状:dict[order_id] -> dict[int(role_key)] -> dict[...],需要 project_fields 才能拍平."""
    order_id_set = set(params.get("order_id_set") or [])
    if not order_id_set:
        return {}
    # role key 在真实业务中可能是 int enum value,例如 1/2.
    return {
        10001: {
            1: {"clearn_reason_level": 2},
            2: {"clearn_reason_level": 1},
            "review_status": 3,
        }
    }


def example_loader_recommend_candidates_by_order_id(*, params: Dict[str, object]) -> Dict[int, List[Dict[str, object]]]:
    """形状:dict[order_id] -> list[row],需要 take_first 才能落地为单条 row."""
    order_id_set = set(params.get("order_id_set") or [])
    if not order_id_set:
        return {}
    return {
        10001: [
            {"recommend_cs_id": 9002, "recommend_score": 0.95},
            {"recommend_cs_id": 9002, "recommend_score": 0.94},
        ],
        10002: [],
    }
