"""运行 README 最小 YAML 示例（假数据 + 临时输出目录）。"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

from scalim.dsl.yaml_dsl import (
    CaptureRows,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    FileResourceOverride,
    ResourcesOverride,
    RunOverrides,
    run,
)

_LOADER_MODULE = "notebooks.marimo.example_readme_suite.support.min_yaml_loaders"


def yaml_path() -> Path:
    return Path(__file__).resolve().parent / "min_yaml_example.yaml"


def run_min_yaml() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="scalim-readme-yaml-") as tmp:
        out_root = Path(tmp) / "output"
        out_root.mkdir(parents=True, exist_ok=True)
        overrides = RunOverrides(
            resources=ResourcesOverride(
                files={"detail_csv": FileResourceOverride(kind="csv_file", path=str(out_root))},
            )
        )
        result = run(
            str(yaml_path()),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=frozenset([_LOADER_MODULE])),
                outputs=DemandRunOutputOptions(capture=CaptureRows(), overrides=overrides),
            ),
        )
        assert result.total_rows == 3
        assert result.captured_rows is not None
        rows = list(result.captured_rows.iter_row_data())
        assert len(rows) == 3
        methods = {str(r.get("method")) for r in rows}
        assert "card" in methods
        assert "cash" in methods
        return {"rows": len(rows), "methods": sorted(methods)}
