import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.dsl.by_yaml import run as run_yaml
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.imports import load_and_expand_imports
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator
from scalim.sinks.sink_memory import InMemoryRowSink
from scalim.typedefs import RowData

from ..loaders import ECommerceConfig, set_config
from ..shared import TARGET_FIELDS_FULL
from ..verification import VerificationResult, verify_scalim_output
from ._types import ChapterResult


def _extract_verifiable_fields(rows: Sequence[RowData]) -> List[str]:
    if not rows:
        return []
    keys = set(rows[0].keys())
    return [field for field in TARGET_FIELDS_FULL if field in keys]


def run_yaml_dsl(cfg: ECommerceConfig, *, yaml_path: Path, runtime_vars: Optional[Dict[str, object]] = None) -> ChapterResult:
    """YAML DSL 主线: `compile`/`run` + 内存 `sink` + 对拍 + `rows-binding` 对拍字段校验."""
    set_config(cfg)

    loader_module = "scalim_misc.demo_big_data_report.loaders"
    allowed_modules = frozenset([loader_module])
    runtime_vars = runtime_vars or {"order_ids": []}

    # 1) 语义校验: ConfigValidator + YamlDemandLoader
    validator = ConfigValidator()
    yaml_config = load_and_expand_imports(yaml_path)
    try:
        validator.validate(yaml_config)
    except ConfigValidationError as exc:
        summary = "ConfigValidator failed: {}".format(exc)
        return ChapterResult(chapter_id="yaml_dsl", passed=False, summary=summary, details={"errors": getattr(exc, "errors", None)})

    demand_config = YamlDemandLoader().load(str(yaml_path))

    # 2) `compile`: 确保能生成 `IR`/`request`
    compilation = compile_yaml(
        str(yaml_path),
        allowed_modules=allowed_modules,
        runtime_vars=runtime_vars,
    )

    # 3) `run`: 用内存 `sink` 获取行数据
    sink = InMemoryRowSink()
    start = time.time()
    result = run_yaml(
        str(yaml_path),
        allowed_modules=allowed_modules,
        sink=sink,
        runtime_vars=runtime_vars,
    )
    elapsed = time.time() - start

    rows = sink.get_data()
    if not rows:
        return ChapterResult(
            chapter_id="yaml_dsl", passed=False, summary="YAML run produced no rows", details={"duration": elapsed, "result": result}
        )

    # 4) `rows-binding` 对拍字段校验(来自唯一完整 YAML 示例)
    match_fields = ["rows_name_match", "rows_level_match"]
    mismatch = 0
    for row in rows:
        for field in match_fields:
            if not row.get(field):
                mismatch += 1
                break

    # 5) 基于纯 Python 对照组对拍(只检查可验证字段子集)
    fields_to_check = _extract_verifiable_fields(rows)
    verification: VerificationResult = verify_scalim_output(rows, fields_to_check=fields_to_check)

    passed = bool(verification.passed and mismatch == 0)
    summary = "rows={} elapsed={:.3f}s verify={} rows_match_failures={}".format(len(rows), elapsed, verification.passed, mismatch)
    if mismatch:
        summary = summary + "\nrows match fields failed on {} rows".format(mismatch)
    if not verification.passed:
        summary = summary + "\n" + verification.summary

    details: Dict[str, Any] = {
        "duration_seconds": elapsed,
        "rows": len(rows),
        "result": result,
        "demand_config": demand_config,
        "compilation": compilation,
        "verification": verification,
        "fields_checked": fields_to_check,
        "rows_match_failures": mismatch,
    }
    return ChapterResult(chapter_id="yaml_dsl", passed=passed, summary=summary, details=details)
