# -*- coding: utf-8 -*-
"""Deterministic synthetic loaders (no business vocabulary)."""
from __future__ import print_function

from typing import Any, Dict, List, Optional, Sequence

_SHAPE = {
    "fact_rows": 10000,
    "dim_rows": 2000,
    "region_rows": 50,
}


def configure_shape(fact_rows, dim_rows, region_rows):
    # type: (int, int, int) -> None
    _SHAPE["fact_rows"] = int(fact_rows)
    _SHAPE["dim_rows"] = int(dim_rows)
    _SHAPE["region_rows"] = int(region_rows)


def _as_int_list(value):
    # type: (Any) -> Optional[List[int]]
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [int(x) for x in value]
    return None


def load_facts(ids=None, **_kwargs):
    # type: (Optional[Sequence[Any]], **Any) -> List[Dict[str, Any]]
    """Main fact table: fact_id, dim_id, region_id, qty, unit_price.

    Empty ``ids`` (or None) means generate the full configured shape (demo convention).
    """
    n = int(_SHAPE["fact_rows"])
    dim_n = max(1, int(_SHAPE["dim_rows"]))
    region_n = max(1, int(_SHAPE["region_rows"]))
    id_filter = _as_int_list(ids)
    if id_filter is not None and len(id_filter) == 0:
        id_filter = None
    rows = []  # type: List[Dict[str, Any]]
    for i in range(1, n + 1):
        if id_filter is not None and i not in id_filter:
            continue
        rows.append(
            {
                "fact_id": i,
                "dim_id": ((i - 1) % dim_n) + 1,
                "region_id": ((i - 1) % region_n) + 1,
                "qty": (i % 17) + 1,
                "unit_price": float(((i % 50) + 1) * 1.5),
            }
        )
    return rows


def load_dims(keys=None, **_kwargs):
    # type: (Optional[Sequence[Any]], **Any) -> Dict[Any, Dict[str, Any]]
    n = int(_SHAPE["dim_rows"])
    region_n = max(1, int(_SHAPE["region_rows"]))
    wanted = None
    if keys is not None:
        wanted = set(int(k) for k in keys)
    out = {}  # type: Dict[Any, Dict[str, Any]]
    for i in range(1, n + 1):
        if wanted is not None and i not in wanted:
            continue
        out[i] = {
            "dim_id": i,
            "dim_code": "D{:05d}".format(i),
            "region_id": ((i - 1) % region_n) + 1,
            "weight": float((i % 9) + 1),
        }
    return out


def load_regions(keys=None, **_kwargs):
    # type: (Optional[Sequence[Any]], **Any) -> Dict[Any, Dict[str, Any]]
    n = int(_SHAPE["region_rows"])
    wanted = None
    if keys is not None:
        wanted = set(int(k) for k in keys)
    out = {}  # type: Dict[Any, Dict[str, Any]]
    for i in range(1, n + 1):
        if wanted is not None and i not in wanted:
            continue
        out[i] = {
            "region_id": i,
            "region_code": "R{:03d}".format(i),
            "tier": (i % 3) + 1,
        }
    return out


def load_preload_marker(**_kwargs):
    # type: (**Any) -> Dict[Any, Dict[str, Any]]
    """Tiny preload_forever table for cache_pool / hit observability."""
    return {1: {"id": 1, "marker": "preload"}}


def amount_expr(qty, unit_price, weight=1.0):
    # type: (Any, Any, Any) -> float
    """call_by helper used by derived field."""
    try:
        return float(qty) * float(unit_price) * float(weight or 1.0)
    except (TypeError, ValueError):
        return 0.0
