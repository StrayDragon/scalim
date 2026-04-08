from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from scalim.ob.observer import EventDispatchObserver
from scalim_misc.examples.oracle import diff_first_mismatch, stable_sort_rows

_SLA_BREACH_THRESHOLD_MINUTES = 60


def _to_csv_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def calc_risky_score(*, ticket_id: object) -> float:
    """示例: 用于演示 `guardrails.compute.on_error` 的可控异常.

    - ticket_id=1001 时触发除零异常,用于验证 guardrails 信号与兜底行为.
    """
    # 故意让非 int 输入暴露为可观测错误(例如: 上游把 id 解析成了字符串/小数).
    tid = int(ticket_id)
    return 100 / (tid - 1001)


def is_valid_group(*, group_name: object, **_kw: object) -> bool:
    """演示: keyword-only 参数的 call_by 绑定.

    该函数故意使用 `(*, group_name, **kw)` 签名,用于回归:
    - YAML `call_by: "...:is_valid_group(group_name)"` 会被解析成位置参数,应在编译期 fast-fail
    - 正确写法: `call_by: "...:is_valid_group(group_name=group_name)"`
    """
    text = str(group_name or "").strip()
    return bool(text)


def normalize_identity(result: Mapping[object, Mapping[str, Any]], ctx: object) -> Mapping[object, Mapping[str, Any]]:
    """normalize.call_by 示例: identity normalize,用于 notebooks 回归门禁.

    约束:
    - MUST 接受 `(result, ctx)` 或等价形态
    - MUST 返回 `Mapping`
    """

    _ = ctx
    return result


def normalize_kwonly_result(*, result: Mapping[object, Mapping[str, Any]]) -> Mapping[object, Mapping[str, Any]]:
    """normalize.call_by 反例: keyword-only result(不接受任何位置参数),必须编译期 fail-fast."""

    return result


# -----------------------------------------------------------------------------
# Deterministic fixtures (loaders)
# -----------------------------------------------------------------------------

_SUPPORT_TICKETS: List[Dict[str, Any]] = [
    {
        "ticket_id": 1001,
        "customer_id": 1,
        "agent_id": 11,
        "category": "refund",
        "priority": "P1",
        "first_response_minutes": 5,
        "resolve_minutes": 30,
        "csat": 5,
    },
    {
        "ticket_id": 1002,
        "customer_id": 2,
        "agent_id": 11,
        "category": "delivery",
        "priority": "P2",
        "first_response_minutes": 15,
        "resolve_minutes": 80,  # SLA breach
        "csat": 2,
    },
    {
        "ticket_id": 1003,
        "customer_id": 3,
        "agent_id": 12,
        "category": "bug",
        "priority": "P2",
        "first_response_minutes": 8,
        "resolve_minutes": 55,
        "csat": 4,
    },
    {
        "ticket_id": 1004,
        "customer_id": 4,
        "agent_id": None,  # guardrails: required_fields + relations.null_key
        "category": "account",
        "priority": "P3",
        "first_response_minutes": 2,
        "resolve_minutes": 20,
        "csat": 5,
    },
    {
        "ticket_id": 1005,
        "customer_id": 5,  # row_gap: customers missing
        "agent_id": 99,  # row_gap: agents missing
        "category": "delivery",
        "priority": "P2",
        "first_response_minutes": 25,
        "resolve_minutes": 65,  # SLA breach
        "csat": 3,
    },
]

_SUPPORT_CUSTOMERS: Dict[int, Dict[str, Any]] = {
    1: {"customer_id": 1, "customer_segment": "new"},
    2: {"customer_id": 2, "customer_segment": "vip"},
    3: {"customer_id": 3, "customer_segment": "vip"},
    4: {"customer_id": 4, "customer_segment": "new"},
    # 5 intentionally missing -> row_gap
}

_SUPPORT_AGENTS: Dict[int, Dict[str, Any]] = {
    11: {"agent_id": 11, "agent_team": "team-a"},
    12: {"agent_id": 12, "agent_team": "team-b"},
    # 99 intentionally missing -> row_gap
}

# -----------------------------------------------------------------------------
# Dirty-key fixtures: lookup_cast=sep_first + relations.type_error guardrails
# -----------------------------------------------------------------------------

_SUPPORT_TICKETS_DIRTY_AGENT_ID: List[Dict[str, Any]] = [
    {
        "ticket_id": 2001,
        "agent_id": "11,legacy",
        "category": "refund",
    },
    {
        "ticket_id": 2002,
        # 空字符串不是 `null_key`,会触发 `lookup_cast` 返回 None -> type_error.
        "agent_id": "",
        "category": "delivery",
    },
    {
        "ticket_id": 2003,
        "agent_id": "12,legacy",
        "category": "bug",
    },
]


def load_support_tickets(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> List[Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if not ids:
        return list(_SUPPORT_TICKETS)
    wanted = {int(x) for x in ids}
    return [r for r in _SUPPORT_TICKETS if int(r.get("ticket_id", -1)) in wanted]


def load_support_tickets_dirty_agent_id(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> List[Dict[str, Any]]:
    """dirty-key 场景: agent_id 可能来自 CSV/Excel 导出,带后缀或为空字符串."""
    _ = field_keys
    _ = is_ref_loader
    if not ids:
        return list(_SUPPORT_TICKETS_DIRTY_AGENT_ID)
    wanted = {int(x) for x in ids}
    return [r for r in _SUPPORT_TICKETS_DIRTY_AGENT_ID if int(r.get("ticket_id", -1)) in wanted]


def load_support_customers(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if ids is None:
        return dict(_SUPPORT_CUSTOMERS)
    return {int(k): dict(_SUPPORT_CUSTOMERS[int(k)]) for k in ids if int(k) in _SUPPORT_CUSTOMERS}


def load_support_agents_str_keys(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """返回 string key 的 agents 维表,用于演示 `lookup_cast.sep_first` 的真实 join 场景."""
    _ = field_keys
    _ = is_ref_loader
    if ids is None:
        return {str(k): dict(v) for k, v in _SUPPORT_AGENTS.items()}
    wanted = {str(int(k)) for k in ids}
    return {str(k): dict(_SUPPORT_AGENTS[int(k)]) for k in wanted if int(k) in _SUPPORT_AGENTS}


def load_support_agents(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if ids is None:
        return dict(_SUPPORT_AGENTS)
    return {int(k): dict(_SUPPORT_AGENTS[int(k)]) for k in ids if int(k) in _SUPPORT_AGENTS}


# -----------------------------------------------------------------------------
# Pure-Python oracle signals (guardrails/errors + CSV-level correctness)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class GuardrailSignal:
    code: str
    source_id: str
    payload: Dict[str, Any]


class GuardrailCaptureObserver(EventDispatchObserver):
    def __init__(self) -> None:
        self.signals: List[GuardrailSignal] = []

    def on_error(self, event: Any) -> None:
        # payload is `ErrorEvent(error, context)`
        context = getattr(event, "context", None)
        if not isinstance(context, dict):
            return
        if not context.get("guardrail"):
            return
        code = str(context.get("guardrail_code") or "")
        source_id = str(context.get("source_id") or "")
        self.signals.append(GuardrailSignal(code=code, source_id=source_id, payload=dict(context)))


def build_support_expected_outputs_csv_rows() -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    detail_rows: List[Dict[str, str]] = []
    for t in _SUPPORT_TICKETS:
        ticket_id = int(t["ticket_id"])
        customer_id = int(t["customer_id"])
        agent_id_raw = t.get("agent_id")
        agent_id = int(agent_id_raw) if agent_id_raw is not None else None

        customer = _SUPPORT_CUSTOMERS.get(customer_id) or {}
        agent = _SUPPORT_AGENTS.get(agent_id) if agent_id is not None else None
        agent = agent or {}

        resolve_minutes = int(t["resolve_minutes"])
        is_sla_breach = bool(resolve_minutes >= _SLA_BREACH_THRESHOLD_MINUTES)

        row: Dict[str, Any] = {
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "agent_id": agent_id,
            "category": t.get("category") or "",
            "priority": t.get("priority") or "",
            "first_response_minutes": int(t["first_response_minutes"]),
            "resolve_minutes": resolve_minutes,
            "csat": int(t["csat"]),
            "customer_segment": customer.get("customer_segment") or "",
            "agent_team": agent.get("agent_team") or "",
            "is_sla_breach": is_sla_breach,
        }
        detail_rows.append({k: _to_csv_cell(v) for k, v in row.items()})

    # metrics by agent_team (filter empty team via where in YAML)
    by_team: Dict[str, Dict[str, Any]] = {}
    for r in detail_rows:
        team = r.get("agent_team") or ""
        if not team:
            continue
        acc = by_team.setdefault(team, {"agent_team": team, "ticket_cnt": 0, "sla_breach_cnt": 0, "sum_resolve_minutes": 0})
        acc["ticket_cnt"] = int(acc["ticket_cnt"]) + 1
        acc["sla_breach_cnt"] = int(acc["sla_breach_cnt"]) + (1 if r.get("is_sla_breach") == "True" else 0)
        acc["sum_resolve_minutes"] = int(acc["sum_resolve_minutes"]) + int(r.get("resolve_minutes") or 0)

    metrics_rows: List[Dict[str, str]] = []
    for acc in by_team.values():
        ticket_cnt = int(acc["ticket_cnt"]) or 1
        avg_resolve = Decimal(int(acc["sum_resolve_minutes"])) / Decimal(ticket_cnt)
        row = {
            "agent_team": acc["agent_team"],
            "ticket_cnt": int(acc["ticket_cnt"]),
            "sla_breach_cnt": int(acc["sla_breach_cnt"]),
            "avg_resolve_minutes": avg_resolve,
        }
        metrics_rows.append({k: _to_csv_cell(v) for k, v in row.items()})

    return detail_rows, metrics_rows


def verify_support_outputs_csv_rows(
    *,
    actual_detail: Sequence[Mapping[str, Any]],
    actual_metrics_by_team: Sequence[Mapping[str, Any]],
) -> Tuple[bool, str, Dict[str, Any]]:
    exp_detail, exp_metrics = build_support_expected_outputs_csv_rows()

    detail_fields = [
        "ticket_id",
        "customer_id",
        "agent_id",
        "category",
        "priority",
        "first_response_minutes",
        "resolve_minutes",
        "csat",
        "customer_segment",
        "agent_team",
        "is_sla_breach",
    ]
    metrics_fields = [
        "agent_team",
        "ticket_cnt",
        "sla_breach_cnt",
        "avg_resolve_minutes",
    ]

    act_detail = stable_sort_rows(actual_detail, by=("ticket_id",))
    act_metrics = stable_sort_rows(actual_metrics_by_team, by=("agent_team",))
    exp_detail_sorted = stable_sort_rows(exp_detail, by=("ticket_id",))
    exp_metrics_sorted = stable_sort_rows(exp_metrics, by=("agent_team",))

    ok_d, msg_d = diff_first_mismatch(act_detail, exp_detail_sorted, fields=detail_fields)
    ok_m, msg_m = diff_first_mismatch(act_metrics, exp_metrics_sorted, fields=metrics_fields)

    ok = bool(ok_d and ok_m)
    summary = "detail={} metrics={}".format(msg_d, msg_m)
    details: Dict[str, Any] = {
        "detail": {"actual": len(act_detail), "expected": len(exp_detail_sorted), "first_mismatch": msg_d},
        "metrics_by_team": {"actual": len(act_metrics), "expected": len(exp_metrics_sorted), "first_mismatch": msg_m},
    }
    return ok, summary, details


def expected_support_row_gap_totals() -> Dict[str, int]:
    # When `batch_size: null`, each ref loader is called once with unique `$keys`.
    expected_customers = len({int(r["customer_id"]) for r in _SUPPORT_TICKETS})
    actual_customers = len(_SUPPORT_CUSTOMERS)
    expected_agents = len({int(r["agent_id"]) for r in _SUPPORT_TICKETS if r.get("agent_id") is not None})
    actual_agents = len(_SUPPORT_AGENTS)
    return {
        "total_expected": expected_customers + expected_agents,
        "total_actual": actual_customers + actual_agents,
        "total_missing": (expected_customers - actual_customers) + (expected_agents - actual_agents),
    }


def expected_support_guardrail_codes() -> Tuple[str, ...]:
    # - `loader_required_field_missing`: `agent_id` is None on ticket 1004
    # - `relation_null_key_rate_exceeded`: relation lookup sees null_key for agents step (guardrails.relations.null_key_max_rate=0)
    return (
        "loader_required_field_missing",
        "relation_null_key_rate_exceeded",
    )


__all__ = [
    "GuardrailCaptureObserver",
    "GuardrailSignal",
    "expected_support_guardrail_codes",
    "expected_support_row_gap_totals",
    "load_support_agents",
    "load_support_agents_str_keys",
    "load_support_customers",
    "load_support_tickets",
    "load_support_tickets_dirty_agent_id",
    "verify_support_outputs_csv_rows",
]
