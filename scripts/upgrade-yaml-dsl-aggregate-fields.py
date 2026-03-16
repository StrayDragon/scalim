"""升级 YAML DSL 的 `outputs.*.aggregate.metrics` 到 `outputs.*.aggregate.fields`.

说明:
- 这是一个“尽力而为”的机械升级器,用于处理破坏性语法变更.
- 使用 `PyYAML safe_load/safe_dump`,因此不会保留注释/`anchors`.
- 不会尝试升级已移除的旧 `rank` 配置(例如 `rank_by`/`rank_order` 等);请手工处理.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import yaml


def _as_mapping(value: object) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return cast("Dict[str, Any]", value)
    return None


def _as_list(value: object) -> Optional[List[Any]]:
    if isinstance(value, list):
        return cast("List[Any]", value)
    return None


def _field_value(spec: Dict[str, Any]) -> Optional[object]:
    if "field" in spec:
        return spec.get("field")
    if "field_id" in spec:
        return spec.get("field_id")
    return None


def _fields_value(spec: Dict[str, Any]) -> Optional[object]:
    if "fields" in spec:
        return spec.get("fields")
    if "field_ids" in spec:
        return spec.get("field_ids")
    return None


def _upgrade_metric_spec(raw: object, *, path: str) -> Dict[str, Any]:
    spec = _as_mapping(raw)
    if spec is None:
        msg = "{} must be an object".format(path)
        raise TypeError(msg)

    op_raw = spec.get("op")
    if op_raw is None:
        # 已是“函数当键”的写法(或未知形态):保持原样,交由 `validator` 决定.
        return spec

    op = str(op_raw).strip()
    if not op:
        msg = "{}.op must not be empty".format(path)
        raise ValueError(msg)

    params: Dict[str, Any] = {}
    if op == "count":
        field = _field_value(spec)
        if field is not None and str(field).strip():
            params["field"] = field
        return {op: params}

    if op in ("sum", "min", "max", "count_true"):
        field = _field_value(spec)
        if field is None or not str(field).strip():
            msg = "{} requires field/field_id".format(path)
            raise ValueError(msg)
        params["field"] = field
        return {op: params}

    if op == "count_true_gte":
        field = _field_value(spec)
        if field is None or not str(field).strip():
            msg = "{} requires field/field_id".format(path)
            raise ValueError(msg)
        if spec.get("threshold") is None:
            msg = "{}.threshold is required for op='count_true_gte'".format(path)
            raise ValueError(msg)
        params["field"] = field
        params["threshold"] = spec.get("threshold")
        return {op: params}

    if op == "count_distinct":
        field = _field_value(spec)
        fields = _fields_value(spec)
        if field is not None and fields is not None:
            msg = "{}.count_distinct does not allow both field and fields".format(path)
            raise ValueError(msg)
        if field is None and fields is None:
            msg = "{}.count_distinct requires field or fields".format(path)
            raise ValueError(msg)
        if field is not None:
            if not str(field).strip():
                msg = "{}.count_distinct.field must not be empty".format(path)
                raise ValueError(msg)
            params["field"] = field
            return {op: params}

        fields_list = _as_list(fields)
        if fields_list is None:
            msg = "{}.count_distinct.fields must be a list".format(path)
            raise TypeError(msg)
        normalized = [str(item or "").strip() for item in fields_list if str(item or "").strip()]
        if not normalized:
            msg = "{}.count_distinct.fields must not be empty".format(path)
            raise ValueError(msg)
        params["fields"] = normalized
        return {op: params}

    msg = "{} has unsupported op={!r}; upgrade manually".format(path, op)
    raise ValueError(msg)


def _upgrade_metrics_map(metrics: object, *, path: str) -> Dict[str, Any]:
    typed = _as_mapping(metrics)
    if typed is None:
        msg = "{} must be an object".format(path)
        raise TypeError(msg)
    out: Dict[str, Any] = {}
    for out_field_id, raw_spec in typed.items():
        key = str(out_field_id or "").strip()
        if not key:
            continue
        out[key] = _upgrade_metric_spec(raw_spec, path="{}.{}".format(path, key))
    return out


def _upgrade_outputs(config: Dict[str, Any]) -> Tuple[bool, List[str]]:
    outputs = _as_list(config.get("outputs"))
    if not outputs:
        return False, []

    errors: List[str] = []
    changed = False

    for idx, item in enumerate(outputs):
        target = _as_mapping(item)
        if target is None:
            continue
        agg = _as_mapping(target.get("aggregate"))
        if agg is None:
            continue

        if "metrics" in agg:
            if "fields" in agg:
                errors.append("outputs.{}.aggregate has both metrics and fields; resolve manually".format(idx))
                continue
            agg["fields"] = _upgrade_metrics_map(agg.pop("metrics"), path="outputs.{}.aggregate.metrics".format(idx))
            changed = True

    return changed, errors


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _dump_yaml(data: Any) -> str:
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
    )


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upgrade YAML DSL aggregate metrics syntax (breaking change).")
    _ = parser.add_argument("yaml_files", nargs="+", type=Path, help="YAML DSL demand file(s)")
    _ = parser.add_argument("--in-place", action="store_true", help="Write changes back to file(s)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    paths = [p.resolve() for p in cast("List[Path]", args.yaml_files)]
    in_place = bool(args.in_place)

    if not in_place and len(paths) != 1:
        msg = "Without --in-place, exactly one yaml_file is supported"
        raise SystemExit(msg)

    any_changed = False
    all_errors: List[str] = []

    for path in paths:
        data = _load_yaml(path)
        config = _as_mapping(data)
        if config is None:
            all_errors.append("{}: expected a YAML mapping at root".format(path))
            continue

        changed, errors = _upgrade_outputs(config)
        all_errors.extend(["{}: {}".format(path, e) for e in errors])
        if not changed:
            continue
        any_changed = True

        content = _dump_yaml(config)
        if in_place:
            path.write_text(content, encoding="utf-8")
        else:
            sys.stdout.write(content)

    if all_errors:
        for msg in all_errors:
            sys.stderr.write(msg + "\n")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
