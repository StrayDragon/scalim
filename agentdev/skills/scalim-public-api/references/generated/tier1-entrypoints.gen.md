# Scalim Public API (Tier1)

此文档由 `scripts/gen-public-api-skill.py` 自动生成.

## SSOT
- Tier1 curated entrypoints markers: `src/scalim/**/__init__.py`
- Entrypoint exports: 每个入口模块的字面量 `__all__` (AST 扫描; 不 import)

## Tier1 Entrypoints (17)

### `scalim.dsl.yaml_dsl` (order=10)
- desc: YAML DSL 官方运行入口 + 运行期契约
- scenario: 运行 demand/workflow YAML
- marker: `src/scalim/dsl/yaml_dsl/__init__.py:6`
- source: `src/scalim/dsl/yaml_dsl/__init__.py:74`
- exports (`__all__`, tuple, count=32):
  - `UNSET`
  - `BookBudgetOverride`
  - `BookExportXlsxOverride`
  - `BookResourceOverride`
  - `BookWriteDefaultsOverride`
  - `CaptureNone`
  - `CapturePolicy`
  - `CaptureRows`
  - `Compilation`
  - `DemandDiagnosticsOverride`
  - `DemandDiagnosticsPolicy`
  - `DemandRunOptions`
  - `DemandRunOutputOptions`
  - `DemandRunResult`
  - `DemandRunRuntimeOptions`
  - `DemandRunSecurityOptions`
  - `DemandRunTemplateOptions`
  - `FileResourceOverride`
  - `OutputDefaultsToOverride`
  - `OutputExtraSheetOverride`
  - `OutputExtrasOverride`
  - `OutputOverride`
  - `OutputToOverride`
  - `OutputWriteOverride`
  - `OutputsDefaultsOverride`
  - `ResolverTrustedMode`
  - `ResourcesOverride`
  - `RunOverrides`
  - `WorkflowRunOptions`
  - `compile`
  - `run`
  - `run_workflow`

### `scalim.dsl.yaml_dsl.tools` (order=20)
- desc: YAML DSL 辅助工具(输出配置/路径推导)
- scenario: 工具链集成/排错
- marker: `src/scalim/dsl/yaml_dsl/__init__.py:7`
- source: `src/scalim/dsl/yaml_dsl/tools.py:21`
- exports (`__all__`, tuple, count=3):
  - `OutputConfigDict`
  - `derive_base_module_path`
  - `load_output_config`

### `scalim.dsl.yaml_dsl.workflow` (order=30)
- desc: workflow 配置(稳定导入路径)
- scenario: 解析/校验 workflow YAML
- marker: `src/scalim/dsl/yaml_dsl/__init__.py:8`
- source: `src/scalim/dsl/yaml_dsl/workflow.py:21`
- exports (`__all__`, tuple, count=10):
  - `ScalimWorkflowConfigError`
  - `WorkflowConfig`
  - `WorkflowOutputStagingOptions`
  - `WorkflowResourcesWaitDiagnosticsOptions`
  - `WorkflowResourcesWaitOptions`
  - `WorkflowRun`
  - `load_workflow_config`
  - `load_workflow_config_from_mapping`
  - `resolve_workflow_demand_path`
  - `validate_workflow_yaml_text_json`

### `scalim.dsl.yaml_dsl.workflow_types` (order=40)
- desc: workflow 类型(拆分给 typing/依赖方用)
- scenario: 仅用类型,或避免重导入
- marker: `src/scalim/dsl/yaml_dsl/__init__.py:9`
- source: `src/scalim/dsl/yaml_dsl/workflow_types.py:191`
- exports (`__all__`, tuple, count=22):
  - `UNSET`
  - `ComponentsExtend`
  - `ComponentsInherit`
  - `ComponentsPatch`
  - `ComponentsReplace`
  - `PipelineSchedulerOptions`
  - `ScalimWorkflowConfigError`
  - `StageBarrierSchedulerOptions`
  - `WorkflowCachePoolDisabled`
  - `WorkflowCachePoolPin`
  - `WorkflowCachePoolPreloadForeverShared`
  - `WorkflowCachePoolPreloadForeverUnlimited`
  - `WorkflowCachePoolPreset`
  - `WorkflowConfig`
  - `WorkflowExecutionOptions`
  - `WorkflowNodePatch`
  - `WorkflowOutputStagingOptions`
  - `WorkflowResourcesWaitDiagnosticsOptions`
  - `WorkflowResourcesWaitOptions`
  - `WorkflowRun`
  - `WorkflowRunOptions`
  - `WorkflowRuntimeOptions`

### `scalim.dsl.yaml_dsl.workflow_paths` (order=50)
- desc: workflow 路径解析(稳定导入路径)
- scenario: 解析 workflow 引用的 demand 路径
- marker: `src/scalim/dsl/yaml_dsl/__init__.py:10`
- source: `src/scalim/dsl/yaml_dsl/workflow_paths.py:11`
- exports (`__all__`, tuple, count=1):
  - `resolve_workflow_demand_path`

### `scalim.spec.ir` (order=60)
- desc: IR(中间表示)数据结构(稳定导入路径)
- scenario: 写自定义组件/扩展点/高级调试
- marker: `src/scalim/spec/ir/__init__.py:6`
- source: `src/scalim/spec/ir/__init__.py:53`
- exports (`__all__`, tuple, count=40):
  - `BindingIr`
  - `BuiltinCallableIdIr`
  - `CallBySpecIr`
  - `CallByValueIr`
  - `CallableRefIr`
  - `ComputeCallContextIr`
  - `CsvFieldPresentationIr`
  - `DemandIr`
  - `DerivedFieldIr`
  - `ExportProfileIr`
  - `FieldIr`
  - `FieldPresentationIr`
  - `FieldRefIr`
  - `JoinConditionIr`
  - `KeyIr`
  - `LoaderCallContextIr`
  - `LoaderExtractor`
  - `LoaderIr`
  - `LoaderParamsBuilder`
  - `LoaderResultMapCallable`
  - `LookupCastSpecIr`
  - `LookupKeyCast`
  - `LookupKeySpec`
  - `LookupStepIr`
  - `MainSourceIr`
  - `MainSourceRowIterableCallable`
  - `NormalizedLookupKeySpec`
  - `OrderByKeyIr`
  - `PandasFieldPresentationIr`
  - `PythonReferenceIr`
  - `RelationIr`
  - `RuntimeHandleIdIr`
  - `SourceIr`
  - `SourceNormalizeIr`
  - `SourceRefIr`
  - `SpreadsheetFieldPresentationIr`
  - `SupportedFieldIr`
  - `ValueOpIr`
  - `build_stable_lookup_key_list`
  - `describe_callable_ref`

### `scalim.workflow.loaders` (order=70)
- desc: workflow 内置 loader 的上下文与实现
- scenario: 在自定义 loader/运行器中复用
- marker: `src/scalim/workflow/__init__.py:9`
- source: `src/scalim/workflow/loaders.py:114`
- exports (`__all__`, tuple, count=2):
  - `book_sheet_rows`
  - `workflow_loader_context`

### `scalim.planning` (order=80)
- desc: 规划层入口
- scenario: 规划/编排/可视化分析
- marker: `src/scalim/planning/__init__.py:6`
- source: `src/scalim/planning/__init__.py:12`
- exports (`__all__`, tuple, count=9):
  - `ComputeOperatorIr`
  - `ExecutionPlan`
  - `LoadOperatorIr`
  - `LoadRefOperatorIr`
  - `OperatorType`
  - `PlanBuilder`
  - `PlanMetadata`
  - `PlanOperatorIr`
  - `Stage`

### `scalim.execution` (order=90)
- desc: execution facade(run_ir + contracts)
- scenario: DSL-agnostic 执行入口 + request/result 契约
- marker: `src/scalim/execution/__init__.py:3`
- source: `src/scalim/execution/__init__.py:15`
- exports (`__all__`, tuple, count=7):
  - `ExecutionRequest`
  - `ExecutionResult`
  - `ExportLayout`
  - `ObservabilitySpec`
  - `OutputSpec`
  - `export_layout_from_demand_ir`
  - `run_ir`

### `scalim.ob` (order=100)
- desc: 可观测性入口
- scenario: 构建 observer manager / 采集事件
- marker: `src/scalim/ob/__init__.py:3`
- source: `src/scalim/ob/__init__.py:7`
- exports (`__all__`, tuple, count=2):
  - `Observability`
  - `ObservabilityOptions`

### `scalim.events` (order=110)
- desc: 事件envelope+事件类型入口+事件目录查询入口
- scenario: 写 Observer/Hook;按 `event_type` 订阅/过滤
- marker: `src/scalim/events/__init__.py:9`
- source: `src/scalim/events/__init__.py:27`
- exports (`__all__`, tuple, count=12):
  - `WORKFLOW_ATTRIBUTION_META_KEYS`
  - `WORKFLOW_EXEC_ID_META_KEY`
  - `WORKFLOW_NODE_ID_META_KEY`
  - `Event`
  - `EventDescriptor`
  - `EventType`
  - `WorkflowNodeCancelledReason`
  - `WorkflowNodeEndStatus`
  - `generate_run_id`
  - `get_event_catalog`
  - `get_event_catalog_map`
  - `now_ts`

### `scalim.events.type_groups` (order=111)
- desc: 事件类型分组视图
- scenario: 按主题探索 `EventType`(不引入新值)
- marker: `src/scalim/events/__init__.py:10`
- source: `src/scalim/events/type_groups.py:67`
- exports (`__all__`, tuple, count=15):
  - `adaptive`
  - `batch`
  - `column`
  - `diagnostic`
  - `error`
  - `field`
  - `loader`
  - `operator`
  - `output`
  - `pipeline`
  - `pre`
  - `relation`
  - `row`
  - `stage`
  - `workflow`

### `scalim.sinks` (order=120)
- desc: sink 契约与常用 sinks
- scenario: 使用内置 sinks / 实现自定义 sink
- marker: `src/scalim/sinks/__init__.py:8`
- source: `src/scalim/sinks/__init__.py:30`
- exports (`__all__`, tuple, count=15):
  - `BaseColumnSink`
  - `BaseRowSink`
  - `BaseSink`
  - `BlockColumnCSVSink`
  - `CSVSink`
  - `ColumnBatch`
  - `ColumnCSVSink`
  - `ColumnData`
  - `ColumnExcelSink`
  - `ColumnValues`
  - `ExcelSink`
  - `ExcelWorkbookSink`
  - `IColumnSink`
  - `IRowSink`
  - `ISink`

### `scalim.sinks.memory` (order=121)
- desc: memory sinks(调试/测试/捕获)
- scenario: `InMemoryRowDataSink`/`InMemoryCsv` 等
- marker: `src/scalim/sinks/__init__.py:9`
- source: `src/scalim/sinks/memory.py:13`
- exports (`__all__`, tuple, count=4):
  - `InMemoryColumnSink`
  - `InMemoryCsv`
  - `InMemoryCsvSink`
  - `InMemoryRowDataSink`

### `scalim.sinks.pandas` (order=122)
- desc: pandas sinks(可选依赖)
- scenario: 需要 `pandas` 时显式使用该子模块
- marker: `src/scalim/sinks/__init__.py:10`
- source: `src/scalim/sinks/pandas.py:12`
- exports (`__all__`, tuple, count=2):
  - `PandasColumnSink`
  - `PandasRowSink`

### `scalim.shortcuts.resources` (order=140)
- desc: 资源类 shortcut 稳定入口
- scenario: 从 output root 定位产物/资源
- marker: `src/scalim/shortcuts/resources/__init__.py:7`
- source: `src/scalim/shortcuts/resources/__init__.py:15`
- exports (`__all__`, tuple, count=1):
  - `outputs`

### `scalim.shortcuts.resources.outputs` (order=150)
- desc: outputs discovery facade
- scenario: 定位最新一次发布的 workbook/books 与 files
- marker: `src/scalim/shortcuts/resources/__init__.py:8`
- source: `src/scalim/shortcuts/resources/outputs.py:214`
- exports (`__all__`, tuple, count=5):
  - `LatestOutputs`
  - `latest_book_path`
  - `latest_file_path`
  - `load_latest_outputs`
  - `try_load_latest_outputs`
