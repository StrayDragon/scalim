import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional

from scalim.dsl import yaml_dsl as api
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_public_api_suite/ch135_public_api_key_normalization"

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _first_dim_name(rows) -> Optional[object]:  # type: ignore[no-untyped-def]
    if not rows:
        return None
    return rows[0].get("dim_name")


def run_public_api_key_normalization() -> ExampleResult:
    """演示 `key_normalization` 解决 `relations` 的 `key` 类型不一致导致的 `miss`.

    场景:
    - 主源 `dim_id` 为 `"1"`(`str`)
    - 维表 `mapping` 的 `key` 为 `1`(`int`) 且为 `preload_forever` 缓存源

    期望:
    - `raw` 下 `miss` → `dim_name=None`
    - `auto_str` 下命中 → `dim_name="One"`
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        demand_path = tmp / "demand.yaml"

        demand_yaml = """\
name: public_api_key_normalization_demo

main_source:
  source_id: items
  loader: "scalim_misc.examples.public_api._fixtures:load_items_key_normalization_demo"
  fields:
    item_id: {extract: item_id, name: Item ID}
    dim_id: {extract: dim_id, name: Dim ID}

relations:
  items_to_dims:
    steps:
      - from: items.dim_id
        to: dims.dim_id

sources:
  dims:
    loader: "scalim_misc.examples.public_api._fixtures:load_dims_key_normalization_demo_int_keys"
    key: dim_id
    cache_mode: preload_forever
    fields:
      dim_name:
        name: Dim Name
        relation: items_to_dims
"""
        _write_text(demand_path, demand_yaml)

        result_raw = api.run(
            str(demand_path),
            options=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                runtime=api.DemandRunRuntimeOptions(key_normalization="raw", batch_size=10),
                outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
            ),
        )
        captured_raw = result_raw.captured_rows
        raw_rows = [] if captured_raw is None else list(captured_raw.iter_row_data())

        result_norm = api.run(
            str(demand_path),
            options=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                runtime=api.DemandRunRuntimeOptions(key_normalization="auto_str", batch_size=10),
                outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
            ),
        )
        captured_norm = result_norm.captured_rows
        norm_rows = [] if captured_norm is None else list(captured_norm.iter_row_data())

        raw_dim_name = _first_dim_name(raw_rows)
        norm_dim_name = _first_dim_name(norm_rows)

        passed = bool(raw_rows and norm_rows and raw_dim_name is None and norm_dim_name == "One")
        summary = "raw_dim_name={} normalized_dim_name={}".format(raw_dim_name, norm_dim_name)
        details: Dict[str, Any] = {
            "raw_dim_name": raw_dim_name,
            "normalized_dim_name": norm_dim_name,
            "raw_rows": raw_rows,
            "normalized_rows": norm_rows,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_ch135_public_api_key_normalization() -> ExampleResult:
    return run_public_api_key_normalization()


def run_chapter() -> ExampleResult:
    return run_public_api_key_normalization()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch135_public_api_key_normalization

        本章目标:
        - 演示 `key_normalization` 在 relations 场景下如何统一 key 口径

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch135_public_api_key_normalization.py::run_public_api_key_normalization`

        Gate:
        - `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    result = run_public_api_key_normalization()
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
