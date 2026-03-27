# API Surface Audit (auto)
Generated: `2026-03-27T22:00:45`

## Summary
- `src/scalim/` Python files: **275**
- Files defining `__all__`: **160**
- Files missing `__all__`: **115**
- `__init__.py` files: **54**

## Missing `__all__` by Area (bucketed)
| Area | Files | Missing `__all__` |
|---|---:|---:|
| `dsl/by_yaml/config_parsing` | 35 | 21 |
| `execution/executor` | 33 | 19 |
| `ob` | 31 | 12 |
| `dsl/by_yaml/runtime` | 20 | 5 |
| `planning` | 17 | 3 |
| `dsl/by_yaml/schema_dsl` | 15 | 13 |
| `execution/adaptive` | 15 | 4 |
| `workflow` | 12 | 0 |
| `spec/ir` | 11 | 7 |
| `hooks` | 10 | 7 |
| `vendor` | 9 | 3 |
| `utils` | 8 | 5 |
| `sinks` | 7 | 1 |
| `execution/pipeline` | 6 | 2 |
| `events` | 5 | 1 |
| `cli` | 4 | 4 |
| `_internal` | 2 | 0 |
| `__init__.py` | 1 | 0 |
| `_project_constants.py` | 1 | 0 |
| `dsl` | 1 | 0 |
| `dsl/by_yaml/__init__.py` | 1 | 0 |
| `dsl/by_yaml/_public_template_sandbox.py` | 1 | 0 |
| `dsl/by_yaml/init_var_nodes.py` | 1 | 0 |
| `dsl/by_yaml/params_template.py` | 1 | 0 |
| `dsl/by_yaml/reference_syntax.py` | 1 | 0 |
| `dsl/by_yaml/schema` | 1 | 1 |
| `dsl/by_yaml/tools.py` | 1 | 0 |
| `dsl/by_yaml/workflow.py` | 1 | 0 |
| `dsl/by_yaml/workflow_compile.py` | 1 | 0 |
| `dsl/by_yaml/workflow_config.py` | 1 | 0 |
| `dsl/by_yaml/workflow_entrypoints.py` | 1 | 0 |
| `dsl/by_yaml/workflow_load.py` | 1 | 0 |
| `dsl/by_yaml/workflow_paths.py` | 1 | 0 |
| `dsl/by_yaml/workflow_types.py` | 1 | 0 |
| `exceptions.py` | 1 | 0 |
| `execution/__init__.py` | 1 | 0 |
| `execution/context.py` | 1 | 1 |
| `execution/derived_outputs.py` | 1 | 1 |
| `execution/engine.py` | 1 | 1 |
| `execution/guardrails.py` | 1 | 1 |
| `execution/key_normalization.py` | 1 | 0 |
| `execution/loader_retry.py` | 1 | 1 |
| `execution/output_composition.py` | 1 | 0 |
| `execution/output_contracts.py` | 1 | 0 |
| `execution/preload_cache.py` | 1 | 0 |
| `execution/run_ir.py` | 1 | 0 |
| `execution/workbook_multi_root.py` | 1 | 0 |
| `execution/workflow_cache_pool.py` | 1 | 0 |
| `secure_compute_contracts.py` | 1 | 0 |
| `spec/__init__.py` | 1 | 1 |
| `typedefs.py` | 1 | 1 |
| `warningsx.py` | 1 | 0 |

## `__all__` Underscore Violations
Modules whose `__all__` includes non-dunder `_...` names (should be treated as internal):

- `src/scalim/dsl/by_yaml/runtime/conversion.py`: _validate_source_id
- `src/scalim/workflow/resources_base.py`: _WorkflowResourceManagerBase, _acquire_write_lock, _release_write_lock
- `src/scalim/workflow/resources_csv.py`: _AppendSegment, _CsvPlan, _WorkflowCsvResourceMixin, _build_alignment_mapping, _describe_header_diff, _iter_csv_rows, _read_csv_header
- `src/scalim/workflow/resources_sheetbook.py`: _SheetBookPlan, _SheetBookSegment, _SheetBookSheetPlan, _WorkflowSheetBookResourceMixin
- `src/scalim/workflow/resources_workbook.py`: _SheetPlan, _WorkbookPlan, _WorkflowWorkbookResourceMixin, _best_effort_close_write_only_workbook_worksheets, _get_openpyxl_workbook_class

## Curated / Stable Entrypoints Snapshot
Curated (hard gate today):
- `scalim.dsl.by_yaml`: `__all__`=8 path=`src/scalim/dsl/by_yaml/__init__.py`
- `scalim.dsl.by_yaml.tools`: `__all__`=3 path=`src/scalim/dsl/by_yaml/tools.py`
- `scalim.dsl.by_yaml.workflow`: `__all__`=18 path=`src/scalim/dsl/by_yaml/workflow.py`
- `scalim.dsl.by_yaml.workflow_paths`: `__all__`=1 path=`src/scalim/dsl/by_yaml/workflow_paths.py`
- `scalim.dsl.by_yaml.workflow_types`: `__all__`=14 path=`src/scalim/dsl/by_yaml/workflow_types.py`
- `scalim.spec.ir`: `__all__`=31 path=`src/scalim/spec/ir/__init__.py`
- `scalim.workflow.loaders`: `__all__`=2 path=`src/scalim/workflow/loaders.py`

Stable entrypoints (per `openspec/specs/testing-quality/spec.md`):
- `scalim.dsl.by_yaml`: `__all__`=8 path=`src/scalim/dsl/by_yaml/__init__.py`
- `scalim.execution`: `__all__`=1 path=`src/scalim/execution/__init__.py`
- `scalim.ob`: `__all__`=1 path=`src/scalim/ob/__init__.py`
- `scalim.planning`: `__all__`=9 path=`src/scalim/planning/__init__.py`
- `scalim.spec.ir`: `__all__`=31 path=`src/scalim/spec/ir/__init__.py`

## Barrel Status (`__init__.py`)
| Package | Path | Has `__all__` | `__all__` count | Relative re-export stmts | Re-exported names (rough) |
|---|---|---:|---:|---:|---:|
| `scalim` | `src/scalim/__init__.py` | Y | 1 | 0 | 0 |
| `scalim._internal` | `src/scalim/_internal/__init__.py` | Y | 0 | 0 | 0 |
| `scalim.cli` | `src/scalim/cli/__init__.py` | N | - | 0 | 0 |
| `scalim.dsl` | `src/scalim/dsl/__init__.py` | Y | 1 | 0 | 0 |
| `scalim.dsl.by_yaml` | `src/scalim/dsl/by_yaml/__init__.py` | Y | 8 | 2 | 6 |
| `scalim.dsl.by_yaml.config_parsing` | `src/scalim/dsl/by_yaml/config_parsing/__init__.py` | N | - | 0 | 0 |
| `scalim.dsl.by_yaml.config_parsing.models` | `src/scalim/dsl/by_yaml/config_parsing/models/__init__.py` | Y | 7 | 3 | 8 |
| `scalim.dsl.by_yaml.config_parsing.parsers` | `src/scalim/dsl/by_yaml/config_parsing/parsers/__init__.py` | N | - | 0 | 0 |
| `scalim.dsl.by_yaml.config_parsing.validators` | `src/scalim/dsl/by_yaml/config_parsing/validators/__init__.py` | N | - | 0 | 0 |
| `scalim.dsl.by_yaml.config_parsing.validators._internal` | `src/scalim/dsl/by_yaml/config_parsing/validators/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.dsl.by_yaml.runtime` | `src/scalim/dsl/by_yaml/runtime/__init__.py` | Y | 0 | 0 | 0 |
| `scalim.dsl.by_yaml.runtime._internal` | `src/scalim/dsl/by_yaml/runtime/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.dsl.by_yaml.schema` | `src/scalim/dsl/by_yaml/schema/__init__.py` | N | - | 0 | 0 |
| `scalim.dsl.by_yaml.schema_dsl` | `src/scalim/dsl/by_yaml/schema_dsl/__init__.py` | N | - | 0 | 0 |
| `scalim.dsl.by_yaml.schema_dsl.models` | `src/scalim/dsl/by_yaml/schema_dsl/models/__init__.py` | Y | 84 | 9 | 84 |
| `scalim.events` | `src/scalim/events/__init__.py` | N | - | 0 | 0 |
| `scalim.execution` | `src/scalim/execution/__init__.py` | Y | 1 | 1 | 1 |
| `scalim.execution.adaptive` | `src/scalim/execution/adaptive/__init__.py` | Y | 0 | 0 | 0 |
| `scalim.execution.adaptive._internal` | `src/scalim/execution/adaptive/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor` | `src/scalim/execution/executor/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.batch` | `src/scalim/execution/executor/batch/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.batch._internal` | `src/scalim/execution/executor/batch/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.helpers` | `src/scalim/execution/executor/helpers/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.operators` | `src/scalim/execution/executor/operators/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.operators._internal` | `src/scalim/execution/executor/operators/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.operators.compute` | `src/scalim/execution/executor/operators/compute/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.operators.load_ref` | `src/scalim/execution/executor/operators/load_ref/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.runtime` | `src/scalim/execution/executor/runtime/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.executor.runtime._internal` | `src/scalim/execution/executor/runtime/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.pipeline` | `src/scalim/execution/pipeline/__init__.py` | N | - | 0 | 0 |
| `scalim.execution.pipeline.base` | `src/scalim/execution/pipeline/base/__init__.py` | N | - | 0 | 0 |
| `scalim.hooks` | `src/scalim/hooks/__init__.py` | N | - | 0 | 0 |
| `scalim.hooks._internal` | `src/scalim/hooks/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.ob` | `src/scalim/ob/__init__.py` | Y | 1 | 1 | 1 |
| `scalim.ob._internal` | `src/scalim/ob/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.ob.presets` | `src/scalim/ob/presets/__init__.py` | N | - | 0 | 0 |
| `scalim.ob.presets._internal` | `src/scalim/ob/presets/_internal/__init__.py` | N | - | 0 | 0 |
| `scalim.ob.presets.viz` | `src/scalim/ob/presets/viz/__init__.py` | Y | 6 | 5 | 6 |
| `scalim.planning` | `src/scalim/planning/__init__.py` | Y | 9 | 3 | 9 |
| `scalim.planning.builder_helpers` | `src/scalim/planning/builder_helpers/__init__.py` | Y | 0 | 0 | 0 |
| `scalim.planning.loader_ordering` | `src/scalim/planning/loader_ordering/__init__.py` | Y | 0 | 0 | 0 |
| `scalim.sinks` | `src/scalim/sinks/__init__.py` | N | - | 0 | 0 |
| `scalim.spec` | `src/scalim/spec/__init__.py` | N | - | 0 | 0 |
| `scalim.spec.ir` | `src/scalim/spec/ir/__init__.py` | Y | 31 | 7 | 31 |
| `scalim.spec.ir.aliases` | `src/scalim/spec/ir/aliases/__init__.py` | Y | 7 | 1 | 4 |
| `scalim.spec.ir.binding` | `src/scalim/spec/ir/binding/__init__.py` | Y | 4 | 4 | 12 |
| `scalim.spec.ir.presentation` | `src/scalim/spec/ir/presentation/__init__.py` | Y | 5 | 2 | 3 |
| `scalim.utils` | `src/scalim/utils/__init__.py` | N | - | 0 | 0 |
| `scalim.vendor` | `src/scalim/vendor/__init__.py` | N | - | 0 | 0 |
| `scalim.vendor.compact` | `src/scalim/vendor/compact/__init__.py` | Y | 2 | 1 | 1 |
| `scalim.vendor.dataclassesx` | `src/scalim/vendor/dataclassesx/__init__.py` | Y | 12 | 0 | 0 |
| `scalim.vendor.litejinja2` | `src/scalim/vendor/litejinja2/__init__.py` | Y | 7 | 2 | 8 |
| `scalim.vendor.literich` | `src/scalim/vendor/literich/__init__.py` | Y | 3 | 1 | 1 |
| `scalim.workflow` | `src/scalim/workflow/__init__.py` | Y | 0 | 0 | 0 |

## External Import Hotspots (tests/packages/notebooks)
Top imported `scalim.*` modules (by occurrence):

| Count | Module | Files |
|---:|---|---:|
| 54 | `scalim.spec.ir.sources` | 37 |
| 49 | `scalim.dsl.by_yaml` | 43 |
| 38 | `scalim.execution` | 32 |
| 37 | `scalim.spec.ir.fields` | 37 |
| 35 | `scalim.dsl.by_yaml.schema_dsl.models` | 22 |
| 34 | `scalim.ob.manager` | 31 |
| 33 | `scalim.sinks.sink_memory` | 33 |
| 31 | `scalim.planning` | 31 |
| 30 | `scalim.dsl.by_yaml.runtime.errors` | 18 |
| 29 | `scalim.events.catalog` | 26 |
| 29 | `scalim.hooks.base` | 29 |
| 29 | `scalim.spec.ir.binding` | 28 |
| 28 | `scalim.spec.ir.demand` | 28 |
| 28 | `scalim.dsl.by_yaml.runtime.conversion` | 13 |
| 24 | `scalim.execution.run_ir` | 20 |
| 24 | `scalim.dsl.by_yaml.config_parsing.loader` | 23 |
| 22 | `scalim.planning.operators` | 19 |
| 21 | `scalim.ob.observer` | 18 |
| 21 | `scalim.dsl.by_yaml.config_parsing.validator` | 18 |
| 20 | `scalim.planning.plan` | 20 |
| 19 | `scalim.spec.ir.relations` | 18 |
| 19 | `scalim.workflow` | 7 |
| 18 | `scalim.events.events` | 17 |
| 17 | `scalim.dsl.by_yaml.config_parsing.errors` | 17 |
| 16 | `scalim.execution.context` | 16 |
| 16 | `scalim.typedefs` | 16 |
| 16 | `scalim.sinks.sink_csv` | 11 |
| 16 | `scalim.spec.ir.workflow` | 5 |
| 14 | `scalim.execution.executor.runtime.runtime` | 14 |
| 14 | `scalim.dsl.by_yaml.runtime.references` | 14 |
| 13 | `scalim.events.event` | 11 |
| 12 | `scalim.ob.presets.viz` | 11 |
| 10 | `scalim.execution.loader_retry` | 8 |
| 10 | `scalim.dsl.by_yaml.runtime` | 9 |
| 10 | `scalim.dsl.by_yaml.config_parsing` | 6 |
| 9 | `scalim.sinks.sink_base` | 9 |
| 9 | `scalim.execution.output_composition` | 9 |
| 8 | `scalim.dsl.by_yaml.config_parsing.security` | 7 |
| 7 | `scalim.ob.presets.performance` | 7 |
| 7 | `scalim` | 7 |
| 6 | `scalim.ob.presets.execution_trace` | 6 |
| 6 | `scalim.execution.guardrails` | 6 |
| 6 | `scalim.execution.adaptive.loadref_scheduler` | 5 |
| 6 | `scalim.spec.ir` | 6 |
| 6 | `scalim.execution.executor.batch.executor` | 6 |
| 6 | `scalim.dsl.by_yaml.runtime.contracts` | 4 |
| 6 | `scalim.dsl.by_yaml.config_parsing.models` | 6 |
| 5 | `scalim.ob.presets.memory` | 5 |
| 5 | `scalim.ob.presets.row_gap` | 5 |
| 5 | `scalim.execution.pipeline.overrides` | 5 |
| 5 | `scalim.cli.yaml_dsl` | 5 |
| 5 | `scalim.dsl.by_yaml.config_parsing.call_by` | 4 |
| 5 | `scalim.utils.graph` | 5 |
| 5 | `scalim.ob.presets.logs` | 5 |
| 5 | `scalim.dsl.by_yaml.runtime.introspection` | 5 |
| 5 | `scalim.ob.presets._internal` | 3 |
| 5 | `scalim.sinks.sink_excel` | 4 |
| 5 | `scalim.dsl.by_yaml.runtime.compiler` | 3 |
| 4 | `scalim._project_constants` | 4 |
| 4 | `scalim.execution.executor.operators.load_ref.executor` | 4 |

## TYPE_CHECKING Usage (files)
- `src/scalim/cli/yaml_dsl.py`
- `src/scalim/dsl/__init__.py`
- `src/scalim/dsl/by_yaml/__init__.py`
- `src/scalim/dsl/by_yaml/config_parsing/effective_yaml.py`
- `src/scalim/dsl/by_yaml/config_parsing/imports.py`
- `src/scalim/dsl/by_yaml/config_parsing/loader.py`
- `src/scalim/dsl/by_yaml/config_parsing/project_config.py`
- `src/scalim/dsl/by_yaml/config_parsing/validator.py`
- `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
- `src/scalim/dsl/by_yaml/runtime/compiler.py`
- `src/scalim/dsl/by_yaml/runtime/contracts.py`
- `src/scalim/dsl/by_yaml/runtime/observability.py`
- `src/scalim/dsl/by_yaml/workflow_config.py`
- `src/scalim/dsl/by_yaml/workflow_entrypoints.py`
- `src/scalim/execution/adaptive/_internal/loadref_scheduler_base.py`
- `src/scalim/execution/adaptive/_internal/loadref_scheduler_execution.py`
- `src/scalim/execution/adaptive/config.py`
- `src/scalim/execution/adaptive/loadref_scheduler.py`
- `src/scalim/execution/engine.py`
- `src/scalim/execution/executor/operators/load_ref/executor.py`
- `src/scalim/execution/executor/operators/load_ref/flow.py`
- `src/scalim/execution/output_composition.py`
- `src/scalim/execution/pipeline/base/_row_emission.py`
- `src/scalim/execution/preload_cache.py`
- `src/scalim/execution/run_ir.py`
- `src/scalim/hooks/_internal/manager_base.py`
- `src/scalim/planning/loader_ordering/deps.py`
- `src/scalim/planning/loader_ordering/sequences.py`
- `src/scalim/planning/metadata.py`
- `src/scalim/planning/operators.py`
- `src/scalim/planning/plan.py`
- `src/scalim/sinks/sink_base.py`
- `src/scalim/sinks/sink_csv.py`
- `src/scalim/sinks/sink_excel.py`
- `src/scalim/sinks/sink_memory.py`
- `src/scalim/sinks/sink_pandas.py`
- `src/scalim/vendor/compact/typing_extensionsx.py`
- `src/scalim/workflow/resources_workbook.py`

