<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- `src/scalim/**` module-level `__all__` exports (AST-scanned; excludes `src/scalim/vendor/**`)
- `src/scalim/**/__init__.py` markers: `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
- `scripts/check-api-surface-governance.py`
- `scripts/check-user-material-import-boundaries.py`
- `notebooks/marimo/example_public_api_suite/`
- `tests/public_api/`
-->
# 公共 API 导入指南

??? warning "自动生成文件"
    本文件由 `scripts/gen-docs.py` 自动生成，请勿手动编辑。如需修改，请编辑源文件或生成脚本。

??? note "适用读者"
    - 使用方:在 Python 里调用 Scalim,希望导入路径稳定、可回归
    - 贡献者:需要扩展/治理 public API,避免“看起来能 import 但其实是内部实现细节”

本仓库将“public API”定义为:用户在 Python 侧可稳定导入、并被回归门禁覆盖的一组 `scalim.*` 模块与符号。
核心约束来自三处(约定优先):

- `__all__` 治理规则(模块内符号级): [`scripts/check-api-surface-governance.py`](repo:scripts/check-api-surface-governance.py)
- 用户材料导入边界(文档/示例/skills): [`scripts/check-user-material-import-boundaries.py`](repo:scripts/check-user-material-import-boundaries.py)
- 示例覆盖(可交互/可对拍): `notebooks/marimo/example_public_api_suite/`(见 [主线教程](demo-big-data-report.md))

## 1) 推荐导入（Tier 1:稳定入口）

下表中的模块是我们在文档中明确推荐的稳定入口(约定):优先从这些 facade 模块导入,避免引用内部实现细节。

| 模块 | `__all__` 导出数 | 说明 | 常见场景 |
| --- | ---: | --- | --- |
| `scalim.dsl.yaml_dsl` | 42 | YAML DSL 官方运行入口 + 运行期契约 | 运行 demand/workflow YAML |
| `scalim.dsl.yaml_dsl.tools` | 3 | YAML DSL 辅助工具(输出配置/路径推导) | 工具链集成/排错 |
| `scalim.dsl.yaml_dsl.workflow` | 10 | workflow 配置(稳定导入路径) | 解析/校验 workflow YAML |
| `scalim.dsl.yaml_dsl.workflow_types` | 22 | workflow 类型(拆分给 typing/依赖方用) | 仅用类型,或避免重导入 |
| `scalim.dsl.yaml_dsl.workflow_paths` | 1 | workflow 路径解析(稳定导入路径) | 解析 workflow 引用的 demand 路径 |
| `scalim.spec.ir` | 41 | IR(中间表示)数据结构(稳定导入路径) | 写自定义组件/扩展点/高级调试 |
| `scalim.workflow.loaders` | 2 | workflow 内置 loader 的上下文与实现 | 在自定义 loader/运行器中复用 |
| `scalim.planning` | 10 | 规划层入口 | 规划/编排/可视化分析 |
| `scalim.execution` | 8 | execution facade(run_ir + contracts) | DSL-agnostic 执行入口 + request/result 契约 |
| `scalim.ob` | 5 | 可观测性入口 | 构建 observer manager / 采集事件 |
| `scalim.events` | 44 | 事件envelope+EventType+公开payload+事件目录 | 写 Observer/Hook;按 EventType 订阅/过滤 |
| `scalim.events.type_groups` | 15 | 事件类型分组视图 | 按主题探索 EventType(不引入新值) |
| `scalim.sinks` | 16 | sink 契约与常用 sinks | 使用内置 sinks / 实现自定义 sink |
| `scalim.sinks.memory` | 4 | memory sinks(调试/测试/捕获) | `InMemoryRowDataSink`/`InMemoryCsv` 等 |
| `scalim.sinks.pandas` | 2 | pandas sinks(可选依赖) | 需要 `pandas` 时显式使用该子模块 |
| `scalim.shortcuts.resources` | 1 | 资源类 shortcut 稳定入口 | 从 output root 定位产物/资源 |
| `scalim.shortcuts.resources.outputs` | 5 | outputs discovery facade | 定位最新一次发布的 workbook/books 与 files |

最常见的“只关心导入”的用法:

```python
from scalim.dsl.yaml_dsl import RunOverrides, compile, run, run_workflow
```

需要工具链能力(例如输出配置/基准路径推导)时:

```python
from scalim.dsl.yaml_dsl.tools import derive_base_module_path, load_output_config
```

需要 workflow 配置类型/校验能力时:

```python
from scalim.dsl.yaml_dsl.workflow import WorkflowConfig, load_workflow_config
```

需要 IR(中间表示)类型时,推荐“模块导入”减少符号级耦合:

```python
from scalim.spec import ir as ir
```

需要事件类型/目录查询入口时:

```python
from scalim.events import Event, EventType, PipelineStartEvent, get_event_catalog, parse_event_type
```

需要常用 sinks 时:

```python
from scalim.sinks import CSVSink
```

需要内存 sinks(调试/测试/捕获) 时:

```python
from scalim.sinks.memory import InMemoryRowDataSink
```

需要 pandas sinks(可选依赖) 时:

```python
from scalim.sinks.pandas import PandasRowSink
```

### Tier 1: `__all__` 导出清单（自动生成）

本节用于对齐“模块内符号级契约”(即 `from <module> import <name>` 的白名单集合)。

#### `scalim.dsl.yaml_dsl`

- Export count: `42`

```python
from scalim.dsl.yaml_dsl import (
    UNSET,
    BookExportXlsxOverride,
    BookResourceOverride,
    BookResourcePolicy,
    BookWriteAlignBy,
    BookWriteHeaderPolicy,
    BookWriteMode,
    BookWriteOnConflict,
    BookWriteOnMismatch,
    BookWritePolicy,
    CaptureNone,
    CapturePolicy,
    CaptureRows,
    Compilation,
    DemandDiagnosticsOverride,
    DemandDiagnosticsPolicy,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunResult,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    ExcelColumnResidency,
    FileResourceOverride,
    LookupChunking,
    OutputDefaultsToOverride,
    OutputExtraSheetOverride,
    OutputExtrasOverride,
    OutputOverride,
    OutputToOverride,
    OutputWriteOverride,
    OutputsDefaultsOverride,
    ResolverTrustedMode,
    ResourcesOverride,
    ResourcesPolicy,
    RowsReuse,
    RunOverrides,
    SourceCache,
    WorkflowRunOptions,
    compile,
    run,
    run_workflow,
)
```

#### `scalim.dsl.yaml_dsl.tools`

- Export count: `3`

```python
from scalim.dsl.yaml_dsl.tools import (
    OutputConfigDict,
    derive_base_module_path,
    load_output_config,
)
```

#### `scalim.dsl.yaml_dsl.workflow`

- Export count: `10`

```python
from scalim.dsl.yaml_dsl.workflow import (
    ScalimWorkflowConfigError,
    WorkflowConfig,
    WorkflowOutputStagingOptions,
    WorkflowResourcesWaitDiagnosticsOptions,
    WorkflowResourcesWaitOptions,
    WorkflowRun,
    load_workflow_config,
    load_workflow_config_from_mapping,
    resolve_workflow_demand_path,
    validate_workflow_yaml_text_json,
)
```

#### `scalim.dsl.yaml_dsl.workflow_types`

- Export count: `22`

```python
from scalim.dsl.yaml_dsl.workflow_types import (
    UNSET,
    ComponentsExtend,
    ComponentsInherit,
    ComponentsPatch,
    ComponentsReplace,
    PipelineSchedulerOptions,
    ScalimWorkflowConfigError,
    StageBarrierSchedulerOptions,
    WorkflowCachePoolDisabled,
    WorkflowCachePoolPin,
    WorkflowCachePoolPreloadForeverShared,
    WorkflowCachePoolPreloadForeverUnlimited,
    WorkflowCachePoolPreset,
    WorkflowConfig,
    WorkflowExecutionOptions,
    WorkflowNodePatch,
    WorkflowOutputStagingOptions,
    WorkflowResourcesWaitDiagnosticsOptions,
    WorkflowResourcesWaitOptions,
    WorkflowRun,
    WorkflowRunOptions,
    WorkflowRuntimeOptions,
)
```

#### `scalim.dsl.yaml_dsl.workflow_paths`

- Export count: `1`

```python
from scalim.dsl.yaml_dsl.workflow_paths import (
    resolve_workflow_demand_path,
)
```

#### `scalim.spec.ir`

- Export count: `41`

```python
from scalim.spec.ir import (
    BindingIr,
    BuiltinCallableIdIr,
    CallBySpecIr,
    CallByValueIr,
    CallableRefIr,
    ComputeCallContextIr,
    CsvFieldPresentationIr,
    DemandIr,
    DerivedFieldIr,
    ExportProfileIr,
    FieldIr,
    FieldPresentationIr,
    FieldRefIr,
    JoinConditionIr,
    KeyIr,
    LoaderCallContextIr,
    LoaderExtractor,
    LoaderIr,
    LoaderParamsBuilder,
    LoaderResultMapCallable,
    LookupCastSpecIr,
    LookupKeyCast,
    LookupKeySpec,
    LookupStepIr,
    MainSourceIr,
    MainSourceRowIterableCallable,
    NormalizedLookupKeySpec,
    OrderByKeyIr,
    PandasFieldPresentationIr,
    PythonReferenceIr,
    RelationIr,
    RuntimeHandleIdIr,
    ScalimRelationInferenceError,
    SourceIr,
    SourceNormalizeIr,
    SourceRefIr,
    SpreadsheetFieldPresentationIr,
    SupportedFieldIr,
    ValueOpIr,
    build_stable_lookup_key_list,
    describe_callable_ref,
)
```

#### `scalim.workflow.loaders`

- Export count: `2`

```python
from scalim.workflow.loaders import (
    book_sheet_rows,
    workflow_loader_context,
)
```

#### `scalim.planning`

- Export count: `10`

```python
from scalim.planning import (
    ComputeFusionGroup,
    ComputeOperatorIr,
    ExecutionPlan,
    LoadOperatorIr,
    LoadRefOperatorIr,
    OperatorType,
    PlanBuilder,
    PlanMetadata,
    PlanOperatorIr,
    Stage,
)
```

#### `scalim.execution`

- Export count: `8`

```python
from scalim.execution import (
    ExcelColumnResidency,
    ExecutionRequest,
    ExecutionResult,
    ExportLayout,
    ObservabilitySpec,
    OutputSpec,
    export_layout_from_demand_ir,
    run_ir,
)
```

#### `scalim.ob`

- Export count: `5`

```python
from scalim.ob import (
    CaptureOverflowPolicy,
    LoaderResultPolicy,
    Observability,
    ObservabilityOptions,
    ObserverManagerMode,
)
```

#### `scalim.events`

- Export count: `44`

```python
from scalim.events import (
    WORKFLOW_ATTRIBUTION_META_KEYS,
    WORKFLOW_EXEC_ID_META_KEY,
    WORKFLOW_NODE_ID_META_KEY,
    AdaptiveSchedulerDecisionEvent,
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    Event,
    EventDescriptor,
    EventType,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderRetryEvent,
    LoaderSlimEvent,
    OperatorSpanEvent,
    OutputTargetEndEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
    WorkflowCacheAcquireEvent,
    WorkflowCacheEvictEvent,
    WorkflowCacheReleaseEvent,
    WorkflowFinishedEvent,
    WorkflowNodeCancelledEvent,
    WorkflowNodeCancelledReason,
    WorkflowNodeEndEvent,
    WorkflowNodeEndStatus,
    WorkflowNodeStartEvent,
    WorkflowResourceCommitEvent,
    WorkflowResourceCreateEvent,
    WorkflowResourceDiscardEvent,
    WorkflowResourceWriteEvent,
    WorkflowStartedEvent,
    generate_run_id,
    get_event_catalog,
    get_event_catalog_map,
    now_ts,
    parse_event_type,
)
```

#### `scalim.events.type_groups`

- Export count: `15`

```python
from scalim.events.type_groups import (
    adaptive,
    batch,
    column,
    diagnostic,
    error,
    field,
    loader,
    operator,
    output,
    pipeline,
    pre,
    relation,
    row,
    stage,
    workflow,
)
```

#### `scalim.sinks`

- Export count: `16`

```python
from scalim.sinks import (
    BaseColumnSink,
    BaseRowSink,
    BaseSink,
    BlockColumnCSVSink,
    CSVSink,
    ColumnBatch,
    ColumnCSVSink,
    ColumnData,
    ColumnExcelSink,
    ColumnValues,
    ExcelSink,
    ExcelWorkbookSink,
    IColumnSink,
    IRowSink,
    ISink,
    StreamingColumnExcelSink,
)
```

#### `scalim.sinks.memory`

- Export count: `4`

```python
from scalim.sinks.memory import (
    InMemoryColumnSink,
    InMemoryCsv,
    InMemoryCsvSink,
    InMemoryRowDataSink,
)
```

#### `scalim.sinks.pandas`

- Export count: `2`

```python
from scalim.sinks.pandas import (
    PandasColumnSink,
    PandasRowSink,
)
```

#### `scalim.shortcuts.resources`

- Export count: `1`

```python
from scalim.shortcuts.resources import (
    outputs,
)
```

#### `scalim.shortcuts.resources.outputs`

- Export count: `5`

```python
from scalim.shortcuts.resources.outputs import (
    LatestOutputs,
    latest_book_path,
    latest_file_path,
    load_latest_outputs,
    try_load_latest_outputs,
)
```

## 2) 其它可用导入（Tier 2:可用但不在稳定白名单）

这些模块当前也对外导出了 `__all__`,但**不在 Tier 1 curated 白名单**内:适合高级用户/贡献者使用,但不建议“把它当成稳定入口依赖”。
如果你确实需要依赖它们,建议:

- pin 版本 + 自己维护回归(尤其是导出面较大的模块)
- 优先通过更上层的稳定入口间接使用(例如优先用 `scalim.dsl.yaml_dsl.*`)

常见的 Tier 2 模块(非穷举):

- `scalim.exceptions`:异常 taxonomy
- `scalim.hooks`:hook 扩展点导出
- `scalim.planning`:计划/编排相关导出
- `scalim.execution`:执行相关导出
- `scalim.ob`:observer 相关导出

## 3) 治理与验收（对贡献者）

### 3.1 `__all__` 的含义

- 对外“公开导出”的 **符号级契约**: `from <module> import <name>` 的稳定集合
- 要求 **显式** 定义,避免“无意暴露内部实现”

### 3.2 治理脚本:禁止隐式暴露内部模块

`scripts/check-api-surface-governance.py` 强制:

- `__all__` 不得导出(非 dunder 的) `_name`
- `_internal/` 与 `_*.py` 这类内部实现模块必须显式 `__all__ = []`(或 `()`)封堵导出面

### 3.3 Tier 1 编目（SSOT）

Tier 1 curated entrypoints 的 SSOT 不在本生成器里手写维护,而是通过源码注释标注自动发现:

- 在相关包的 `__init__.py` 内添加一行标注:
  - `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`
- 该行会被 `just gen-docs` 读取并生成本页的 Tier 1 表格与导出清单。

### 3.4 如何自查

```bash
python3 scripts/check-api-surface-governance.py --check
python3 scripts/check-user-material-import-boundaries.py --check
pytest -q tests/public_api/test_example_public_api_suite.py --no-cov
just qa
```

## 4) 结构评估与打分（阶段性）

**综合评分: 9.1/10**

理由(摘要):

- 优点:Tier 1 入口清晰,有 `__all__` 白名单 + gate,回归成本低
- 优点:YAML DSL 运行入口(`scalim.dsl.yaml_dsl`)与 workflow/IR 的稳定导入路径已明确拆出
- 代价:仍有部分 Tier 2 模块导出面偏大/偏“平铺”,但它们不在 curated 白名单内；若需依赖建议自行 pin 版本并维护回归

导出规模不在文档里维护数值快照:以 `__all__` 治理规则 + 示例覆盖为准。

## 5) 代价与优化方向（Brainstorming）

这里的“优化”指结构与治理成本,不是添加新功能。

### 5.1 主要代价点

- 部分 Tier 2 模块的导出面仍可能偏大且平铺:
  - 使用方容易“随手 import 一个看起来能用的符号”并形成隐式依赖
  - 贡献者很难判断“删/改一个符号是否 breaking”

### 5.2 可选优化方向（不落地,仅用于评估）

1) **文档侧收敛(最低成本)**:保留现状,但把“推荐导入组合”写清楚,并将 Tier 2 明确标为高级入口(本页已做)。
2) **引入更细粒度稳定子模块(中成本,可能 breaking)**:为部分高 churn 的 Tier 2 领域引入稳定分组模块,并把推荐导入从“平铺符号”转向“分组模块”。
3) **收窄导出面(高成本,明确 breaking)**:对代表性的大导出面模块做显式收敛,只保留“长期承诺”的符号;该方向建议用 OpenSpec 变更管理并配合版本策略,避免静默破坏下游。
