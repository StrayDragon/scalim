from typing import Any, Dict, List, Mapping, MutableMapping, Optional


CALL_COUNTS: MutableMapping[str, int] = {}
CALL_KWARGS: MutableMapping[str, List[Dict[str, object]]] = {}


def reset_calls() -> None:
    CALL_COUNTS.clear()
    CALL_KWARGS.clear()


def _record(loader_name: str, kwargs: Dict[str, object]) -> None:
    CALL_COUNTS[loader_name] = int(CALL_COUNTS.get(loader_name, 0)) + 1
    CALL_KWARGS.setdefault(loader_name, []).append(dict(kwargs))


def load_orders_main(**kwargs: object) -> List[Dict[str, object]]:
    _record("orders", dict(kwargs))
    return [
        {"order_id": 1, "customer_id": 101},
        {"order_id": 2, "customer_id": 102},
    ]


def load_customers_by_keys(**kwargs: object) -> Mapping[object, Dict[str, object]]:
    _record("customers_by_keys", dict(kwargs))

    # 支持 nested params: query.customer_ids
    query = kwargs.get("query")
    customer_ids: Optional[List[object]] = None
    if isinstance(query, dict):
        raw = query.get("customer_ids")
        if isinstance(raw, list):
            customer_ids = list(raw)

    if customer_ids is None:
        msg = "expected query.customer_ids list"
        raise ValueError(msg)

    out: Dict[object, Dict[str, object]] = {}
    for cid in customer_ids:
        out[cid] = {"customer_id": cid, "name": "c{}".format(cid), "level": "L{}".format(cid)}
    return out


def load_customers_static(**kwargs: object) -> Mapping[object, Dict[str, object]]:
    _record("customers_static", dict(kwargs))
    # 该 loader 不依赖 lookup keys,直接返回全量映射(测试静态 params 透传语义).
    return {
        101: {"customer_id": 101, "name": "c101", "level": "L101"},
        102: {"customer_id": 102, "name": "c102", "level": "L102"},
    }


def load_customers_by_rows(**kwargs: object) -> Mapping[object, Dict[str, object]]:
    _record("customers_by_rows", dict(kwargs))
    rows = kwargs.get("rows")
    if not isinstance(rows, list):
        msg = "expected rows list"
        raise ValueError(msg)

    out: Dict[object, Dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("customer_id")
        if cid is None:
            continue
        out[cid] = {"customer_id": cid, "name": "c{}".format(cid), "level": "L{}".format(cid)}
    return out


def load_preload_refdata(flag: int, **kwargs: object) -> Mapping[object, Dict[str, object]]:
    _record("preload_refdata", {"flag": flag, **dict(kwargs)})
    # 用 order_id 作为 key, 便于测试 via relation 访问预加载结果.
    return {
        1: {"config_id": 1, "value": "v1"},
        2: {"config_id": 2, "value": "v2"},
    }
