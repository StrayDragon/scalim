from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Sequence, Tuple

from scalim_misc.examples.oracle import diff_first_mismatch, stable_sort_rows

if TYPE_CHECKING:
    from scalim.execution.loader_retry import LoaderRetryContext


class AdsTransientError(RuntimeError):
    def __init__(self, message: str = "simulated transient error (retry expected)") -> None:
        super(AdsTransientError, self).__init__(message)


_ADS_CREATIVES_RETRY_COUNTER = {"calls": 0}


def reset_ads_creatives_retry_counter_calls() -> None:
    _ADS_CREATIVES_RETRY_COUNTER["calls"] = 0


def get_ads_creatives_retry_counter_calls() -> int:
    return int(_ADS_CREATIVES_RETRY_COUNTER["calls"])


def should_retry_ads_transient(exc: Exception, ctx: LoaderRetryContext) -> bool:
    _ = ctx
    return isinstance(exc, AdsTransientError)


def _to_csv_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


# -----------------------------------------------------------------------------
# Deterministic fixtures (loaders)
# -----------------------------------------------------------------------------

_ADS_IMPRESSIONS: List[Dict[str, Any]] = [
    {
        "imp_id": 1,
        "ts": "2026-03-01T10:00:00Z",
        "user_id": 100,
        "adgroup_id": 10,
        "creative_id": "101",  # str -> int cast via relation.lookup_cast
        "placement": "feed",
        "country": "US",
        "cost_micros": 1_000_000,
    },
    {
        "imp_id": 2,
        "ts": "2026-03-01T10:01:00Z",
        "user_id": 101,
        "adgroup_id": 10,
        "creative_id": "101",
        "placement": "feed",
        "country": "US",
        "cost_micros": 1_000_000,
    },
    {
        "imp_id": 3,
        "ts": "2026-03-01T10:02:00Z",
        "user_id": 102,
        "adgroup_id": 20,
        "creative_id": "202",
        "placement": "search",
        "country": "CN",
        "cost_micros": 2_000_000,
    },
    {
        "imp_id": 4,
        "ts": "2026-03-01T10:03:00Z",
        "user_id": 103,
        "adgroup_id": 20,
        "creative_id": "202",
        "placement": "search",
        "country": "CN",
        "cost_micros": 2_000_000,
    },
]

_ADS_ADGROUPS: Dict[int, Dict[str, Any]] = {
    10: {"adgroup_id": 10, "adgroup_name": "AG-10 (Prospecting)", "campaign_id": 1},
    20: {"adgroup_id": 20, "adgroup_name": "AG-20 (Retargeting)", "campaign_id": 2},
}

_ADS_CAMPAIGNS: Dict[int, Dict[str, Any]] = {
    1: {"campaign_id": 1, "campaign_name": "C-1 (App Install)", "objective": "install"},
    2: {"campaign_id": 2, "campaign_name": "C-2 (Web Conversion)", "objective": "conversion"},
}

_ADS_CREATIVES: Dict[int, Dict[str, Any]] = {
    101: {"creative_id": 101, "creative_format": "image", "creative_size": "1:1"},
    202: {"creative_id": 202, "creative_format": "video", "creative_size": "16:9"},
}

_ADS_CLICKS: Dict[int, Dict[str, Any]] = {
    1: {"impression_id": 1, "click_id": "clk-1"},
    3: {"impression_id": 3, "click_id": "clk-3"},
    4: {"impression_id": 4, "click_id": "clk-4"},
}

_ADS_CONVERSIONS: Dict[int, Dict[str, Any]] = {
    1: {"impression_id": 1, "conversion_id": "cv-1", "conversion_value": Decimal(4)},
    4: {"impression_id": 4, "conversion_id": "cv-4", "conversion_value": Decimal(6)},
}

_ADS_PRICING: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("feed", "US"): {"placement": "feed", "country": "US", "cpm_multiplier": 1.2},
    # ("search", "CN") deliberately missing: demonstrate "miss -> None -> fallback" in derived compute.
}


def micros_to_usd(*, cost_micros: Any) -> float:
    """Convert micros to USD for derived fields.

    Note: derived fields only support int/float/str/bool/None (Decimal is not allowed there),
    so we keep this helper returning int/float (as float).
    """

    if cost_micros is None:
        return 0.0
    try:
        micros = int(cost_micros)
    except (TypeError, ValueError):
        return 0.0
    if micros % 1_000_000 == 0:
        return float(micros // 1_000_000)
    return micros / 1_000_000.0


def load_ads_impressions(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> List[Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if not ids:
        return list(_ADS_IMPRESSIONS)
    wanted = {int(x) for x in ids}
    return [r for r in _ADS_IMPRESSIONS if int(r.get("imp_id", -1)) in wanted]


def load_ads_adgroups(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if ids is None:
        return dict(_ADS_ADGROUPS)
    return {int(k): dict(_ADS_ADGROUPS[int(k)]) for k in ids if int(k) in _ADS_ADGROUPS}


def load_ads_campaigns(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if ids is None:
        return dict(_ADS_CAMPAIGNS)
    return {int(k): dict(_ADS_CAMPAIGNS[int(k)]) for k in ids if int(k) in _ADS_CAMPAIGNS}


def load_ads_creatives(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    _ADS_CREATIVES_RETRY_COUNTER["calls"] = int(_ADS_CREATIVES_RETRY_COUNTER["calls"]) + 1
    if int(_ADS_CREATIVES_RETRY_COUNTER["calls"]) == 1:
        raise AdsTransientError

    full = dict(_ADS_CREATIVES)
    if ids is None:
        return full
    return {int(k): dict(full[int(k)]) for k in ids if int(k) in full}


def load_ads_clicks(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if ids is None:
        return dict(_ADS_CLICKS)
    return {int(k): dict(_ADS_CLICKS[int(k)]) for k in ids if int(k) in _ADS_CLICKS}


def load_ads_conversions(
    ids: Optional[List[int]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[int, Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if ids is None:
        return dict(_ADS_CONVERSIONS)
    return {int(k): dict(_ADS_CONVERSIONS[int(k)]) for k in ids if int(k) in _ADS_CONVERSIONS}


def load_ads_pricing(
    ids: Optional[List[Tuple[str, str]]] = None,
    field_keys: Optional[List[str]] = None,
    *,
    is_ref_loader: bool = False,
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    _ = field_keys
    _ = is_ref_loader
    if ids is None:
        return dict(_ADS_PRICING)
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for placement, country in ids:
        key = (str(placement), str(country))
        if key in _ADS_PRICING:
            out[key] = dict(_ADS_PRICING[key])
    return out


# -----------------------------------------------------------------------------
# Pure-Python oracle (CSV-level)
# -----------------------------------------------------------------------------


def _join_one(table: Mapping[Any, Mapping[str, Any]], key: Any) -> Mapping[str, Any]:
    return table.get(key) or {}


def build_ads_expected_outputs_csv_rows() -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    detail_all: List[Dict[str, str]] = []
    detail_clicks: List[Dict[str, str]] = []

    for imp in _ADS_IMPRESSIONS:
        impression_id = int(imp["imp_id"])
        adgroup_id = int(imp["adgroup_id"])
        creative_id = int(str(imp["creative_id"]))
        placement = str(imp["placement"])
        country = str(imp["country"])
        cost_micros = int(imp["cost_micros"])

        adg = _join_one(_ADS_ADGROUPS, adgroup_id)
        campaign_id = int(adg.get("campaign_id") or 0)
        campaign = _join_one(_ADS_CAMPAIGNS, campaign_id)
        creative = _join_one(_ADS_CREATIVES, creative_id)
        click = _join_one(_ADS_CLICKS, impression_id)
        conv = _join_one(_ADS_CONVERSIONS, impression_id)
        pricing = _join_one(_ADS_PRICING, (placement, country))

        click_id = click.get("click_id")
        conversion_value = conv.get("conversion_value")
        is_click = bool(click_id)
        is_conversion = bool(conv.get("conversion_id"))

        cost_usd = micros_to_usd(cost_micros=cost_micros)
        cpm_multiplier = pricing.get("cpm_multiplier")
        cost_usd_adjusted = cost_usd if cpm_multiplier is None else (cost_usd * float(cpm_multiplier))

        row: Dict[str, Any] = {
            "impression_id": impression_id,
            "user_id": int(imp["user_id"]),
            "campaign_name": campaign.get("campaign_name") or "",
            "adgroup_name": adg.get("adgroup_name") or "",
            "creative_format": creative.get("creative_format") or "",
            "placement": placement,
            "country": country,
            "is_click": is_click,
            "is_conversion": is_conversion,
            "conversion_value": conversion_value,
            "cost_usd": cost_usd,
            "cost_usd_adjusted": cost_usd_adjusted,
        }
        csv_row = {k: _to_csv_cell(v) for k, v in row.items()}
        detail_all.append(csv_row)
        if is_click:
            detail_clicks.append(dict(csv_row))

    # metrics by campaign_name
    by_campaign: Dict[str, Dict[str, Any]] = {}
    for row in detail_all:
        key = row["campaign_name"]
        acc = by_campaign.setdefault(
            key,
            {
                "campaign_name": key,
                "impression_cnt": 0,
                "click_cnt": 0,
                "conversion_cnt": 0,
                "spend_usd": Decimal(0),
                "revenue_usd": Decimal(0),
            },
        )
        acc["impression_cnt"] = int(acc["impression_cnt"]) + 1
        acc["click_cnt"] = int(acc["click_cnt"]) + (1 if row.get("is_click") == "True" else 0)
        acc["conversion_cnt"] = int(acc["conversion_cnt"]) + (1 if row.get("is_conversion") == "True" else 0)
        acc["spend_usd"] = acc["spend_usd"] + Decimal(row.get("cost_usd") or "0")
        acc["revenue_usd"] = acc["revenue_usd"] + Decimal(row.get("conversion_value") or "0")

    metrics_rows: List[Dict[str, str]] = []
    for acc in by_campaign.values():
        imp_cnt = int(acc["impression_cnt"])
        click_cnt = int(acc["click_cnt"])
        conv_cnt = int(acc["conversion_cnt"])
        spend = acc["spend_usd"]
        revenue = acc["revenue_usd"]

        ctr = Decimal(click_cnt) / Decimal(imp_cnt) if imp_cnt else Decimal(0)
        cvr = Decimal(conv_cnt) / Decimal(click_cnt) if click_cnt else Decimal(0)
        roas = revenue / spend if spend else Decimal(0)

        row = {
            "campaign_name": acc["campaign_name"],
            "impression_cnt": imp_cnt,
            "click_cnt": click_cnt,
            "conversion_cnt": conv_cnt,
            "spend_usd": spend,
            "revenue_usd": revenue,
            "ctr": ctr,
            "cvr": cvr,
            "roas": roas,
        }
        metrics_rows.append({k: _to_csv_cell(v) for k, v in row.items()})

    return detail_all, detail_clicks, metrics_rows


def verify_ads_outputs_csv_rows(
    *,
    actual_detail_all: Sequence[Mapping[str, Any]],
    actual_detail_clicks: Sequence[Mapping[str, Any]],
    actual_metrics_by_campaign: Sequence[Mapping[str, Any]],
) -> Tuple[bool, str, Dict[str, Any]]:
    exp_detail_all, exp_detail_clicks, exp_metrics = build_ads_expected_outputs_csv_rows()

    detail_fields = [
        "impression_id",
        "user_id",
        "campaign_name",
        "adgroup_name",
        "creative_format",
        "placement",
        "country",
        "is_click",
        "is_conversion",
        "conversion_value",
        "cost_usd",
        "cost_usd_adjusted",
    ]
    metrics_fields = [
        "campaign_name",
        "impression_cnt",
        "click_cnt",
        "conversion_cnt",
        "spend_usd",
        "revenue_usd",
        "ctr",
        "cvr",
        "roas",
    ]

    act_detail_all = stable_sort_rows(actual_detail_all, by=("impression_id",))
    act_detail_clicks = stable_sort_rows(actual_detail_clicks, by=("impression_id",))
    act_metrics = stable_sort_rows(actual_metrics_by_campaign, by=("campaign_name",))

    exp_detail_all_sorted = stable_sort_rows(exp_detail_all, by=("impression_id",))
    exp_detail_clicks_sorted = stable_sort_rows(exp_detail_clicks, by=("impression_id",))
    exp_metrics_sorted = stable_sort_rows(exp_metrics, by=("campaign_name",))

    ok_all, msg_all = diff_first_mismatch(act_detail_all, exp_detail_all_sorted, fields=detail_fields)
    ok_clicks, msg_clicks = diff_first_mismatch(act_detail_clicks, exp_detail_clicks_sorted, fields=detail_fields)
    ok_metrics, msg_metrics = diff_first_mismatch(act_metrics, exp_metrics_sorted, fields=metrics_fields)

    ok = bool(ok_all and ok_clicks and ok_metrics)
    summary = "detail_all={} detail_clicks={} metrics={}".format(msg_all, msg_clicks, msg_metrics)
    details: Dict[str, Any] = {
        "detail_all": {"actual": len(act_detail_all), "expected": len(exp_detail_all_sorted), "first_mismatch": msg_all},
        "detail_clicks": {"actual": len(act_detail_clicks), "expected": len(exp_detail_clicks_sorted), "first_mismatch": msg_clicks},
        "metrics_by_campaign": {"actual": len(act_metrics), "expected": len(exp_metrics_sorted), "first_mismatch": msg_metrics},
    }
    return ok, summary, details


__all__ = [
    "AdsTransientError",
    "get_ads_creatives_retry_counter_calls",
    "load_ads_adgroups",
    "load_ads_campaigns",
    "load_ads_clicks",
    "load_ads_conversions",
    "load_ads_creatives",
    "load_ads_impressions",
    "load_ads_pricing",
    "micros_to_usd",
    "reset_ads_creatives_retry_counter_calls",
    "should_retry_ads_transient",
    "verify_ads_outputs_csv_rows",
]
