## Context

### 现状: 已有扩展点,但对 YAML-first 用户“不够可达/不够全面”

仓库当前已经具备一些“受控扩展”能力,但它们分散在不同层级,且多数需要修改 Python driver 才能启用:

- **安全引用解析(allowlist + 相对引用归一化)**: `loader`/`retry.should_retry`/`derived.call_by`/`normalize.call_by` 等通过 `SecurePythonReferenceResolver` 解析并受 allowlist 约束。
  - 关键实现: `src/scalim/dsl/by_yaml/runtime/references.py`, `src/scalim/dsl/by_yaml/runtime/compiler.py`
- **派生字段自定义函数**: `fields.*.call_by` 支持 `reference(args...)` + `$ctx`。
  - 关键实现: `src/scalim/dsl/by_yaml/config_parsing/call_by.py`, `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
- **whole-result normalize.call_by**: mapping→mapping 扩展点(带 ctx),可做“加载结果的后处理/修正/归一化”。
  - 关键实现: `src/scalim/spec/ir/sources.py::SourceNormalizeIr.apply`
- **driver 注入(非 YAML)**: `run(..., components=[Observer/Hook...], sink=..., output_composition=...)`
  - 关键实现: `src/scalim/dsl/by_yaml/runtime/entrypoints.py`, `src/scalim/execution/run_ir.py`

痛点是:

1) **YAML-first 用户需要改 driver** 才能挂载自定义 hook/observer、替换 outputs 装配等。
2) **输出格式/聚合能力仍高度内置**:
   - 单输出 `_create_file_sink()` 只支持 `csv/excel`(`src/scalim/execution/run_ir.py`)
   - composed outputs 只支持 `csv/excel` 且要求 `streaming=true`(`src/scalim/execution/output_composition.py`)
   - YAML `outputs[*].container.type` 只允许 `workbook/csv`(`src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`)
   - YAML `outputs[*].aggregate` 只暴露 `group_by`(`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`)

### 关键约束(必须在设计里一次性考虑清楚)

- **Python 运行时边界**: `src/scalim/` 必须保持 Python 3.6 兼容(见仓库 `AGENTS.md`)。
- **schema/validator 双轨**:
  - schema-only 校验用于 editor/CLI `schema validate`
  - 运行时语义校验由 `ConfigValidator` 执行,且顶层 schema 当前为 `additionalProperties: false`。
- **allowlist 是现有硬边界**: `scalim.dsl.by_yaml.run/compile` 必须传 allowlist(安全审计边界)。
- **本场景 YAML 可信**: 允许更强的可编程扩展,但仍需要“可诊断/可回滚/可对拍”的边界,避免变成不可控的“任意注入”。

## Goals / Non-Goals

**Goals:**
- 在 YAML 顶层提供一个显式扩展入口 `extensions`,并且 **同时支持**:
  - **BUNDLE**: 通过 `extensions.bundles` 引入扩展包(工厂返回一组贡献)
  - **ANALYZE**: 通过 `extensions.analyze` 运行只读分析器(产出 issues/元信息)
  - **Direct config**: 在 `extensions.compute/components/outputs/aggregates/transform` 下直接声明常见扩展(无需写 bundle)
- 扩展能力覆盖完整需求面(不以“只做 MVP”为边界),至少包括:
  - 自定义 compute/where 表达式函数
  - YAML 注入 components(Observer/Hook)
  - 自定义输出格式/容器的 registry(单输出 + composed outputs 复用)
  - 自定义派生聚合(aggregate kind/ref → `IDerivedAggregationSpec/IRowAggregator`)
  - 编译期变换器(transformers): raw/config/IR/request
  - 分析器(analyzers): 支持 CLI/IDE/CI 消费
- 扩展加载/合并/错误必须确定性、可审计:
  - 引用统一走 allowlist resolver
  - 合并顺序确定,冲突策略可配置
  - 错误包含 `yaml_path/ref/stage` 等上下文
- 收敛文档与生成边界并给出 drift gate:
  - schema 生成与前端 schema 镜像的同步策略明确

**Non-Goals:**
- 不做“插件市场/自动发现/远程下载”的重型插件系统(优先显式引用;entry-points discovery 可作为可选增强)。
- 不要求 editor 对每个第三方扩展的 `options` 做强 schema 校验(核心 schema 只保证 `extensions` 的容器与通用形状,扩展内部细节走 analyzer/文档)。

## Decisions

### Decision 0: `extensions.api` + `ExtensionHost` 收敛扩展契约

为避免扩展面越做越散、不同扩展点各自“临时长出一套接口”,本提案引入两个**收敛点**作为 SSOT:

1) **`extensions.api`(版本号)**  
   - `extensions` 块存在时,系统 MUST 识别 `extensions.api`。  
   - `api` 缺省时视为 `1`(便于快速试验);当出现未知 `api` 时 MUST fail-fast,并提示升级/降级或切换 `extensions.enabled=false`。  
   - 破坏性变化必须通过递增 `api` 来完成(例如 2),避免“同一份 YAML 在不同版本下语义漂移”。

2) **`ExtensionHost`(扩展宿主/编译产物)**  
   扩展解析与合并在编译期**只做一次**,并产出一个可复用的“扩展视图”,供 validator/parser/compiler/executor/CLI 共享,避免多个模块各自解析导致漂移。

概念接口(伪代码):

```python
@dataclass(frozen=True)
class ExtensionHost:
    api: int
    enabled: bool

    # 贡献(merge 后的最终视图)
    compute_functions: Dict[str, Callable[..., object]]
    components: Tuple[object, ...]
    output_format_factories: Dict[str, object]  # format_id -> factory
    aggregate_kind_factories: Dict[str, object]  # kind_id -> factory

    transformers_raw: Tuple[Callable[[dict, object], dict], ...]
    transformers_config: Tuple[Callable[[object, object], object], ...]
    transformers_ir: Tuple[Callable[[object, object], object], ...]
    transformers_request: Tuple[Callable[[object, object], object], ...]

    analyzers: Tuple[Callable[[object], object], ...]

    # 可对拍摘要(用于 CLI/IDE/CI/viz meta)
    summary: Dict[str, object]
```

收敛原则:
- **单一来源**: Direct config 与 bundles 都先被编译成“隐式 bundle”,再按确定性顺序合并为 `ExtensionHost`。
- **单一执行边界**: 所有扩展引用 MUST 通过 `SecurePythonReferenceResolver` + allowlist 解析(即便 YAML 可信,仍保留显式授权与可审计边界)。
- **单一诊断面**: `ExtensionHost.summary` 必须包含 bundles/analyzers/registries/transformers/components 的最终列表,并携带来源 ref 信息,便于对拍与回滚。

### Decision 1: YAML 形状同时支持 BUNDLE + ANALYZE + Direct config

`extensions` 作为顶层唯一命名空间,形状示例(“全量形态”):

```yaml
extensions:
  api: 1
  enabled: true

  # 1) Direct config: 常见扩展不必写 bundle
  compute:
    functions:
      safe_div: myapp.scalim_ext.compute:safe_div
  components:
    - ref: myapp.scalim_ext.hooks:LatencyBudgetHook
      config: {max_ms: 2000}
  outputs:
    formats:
      parquet:
        ref: myapp.scalim_ext.outputs:parquet_format
        config: {compression: zstd}
  aggregates:
    kinds:
      pivot:
        ref: myapp.scalim_ext.agg:pivot_aggregate
  transform:
    raw:
      - ref: myapp.scalim_ext.transform:expand_macros
    request:
      - ref: myapp.scalim_ext.transform:default_parallel_mode

  # 2) BUNDLE: 扩展包工厂返回一组贡献
  bundles:
    - ref: myapp.scalim_ext:bundle_v1
      config: {profile: "dev"}

  # 3) ANALYZE: 只读分析(输出 issues/建议/元信息)
  analyze:
    - ref: myapp.scalim_ext.analyze:lint_v1
      config: {level: "warning"}
```

规则(语义):
- Direct config 与 bundles 的贡献进入同一组 registries(最终行为一致)
- analyzers 不得修改 config/IR/request,只能产出诊断与元信息

### Decision 2: 扩展引用一律走 allowlist resolver(显式授权)

扩展引用复用现有引用语法与解析器:
- `module.path:function` / `module.path:Obj.method` / `module.path.function`
- 相对引用 `.`/`..` 仍按 `derive_base_module_path(yaml_path)` 归一化
- 解析实现复用 `SecurePythonReferenceResolver`

这保证:
- 扩展“能执行什么”必须由调用方通过 allowlist 显式授权(即便 YAML 可信,仍保留最小门禁)
- 错误提示与现有 loader/call_by 一致,便于排障

### Decision 3: 统一“实例化/调用”约定,兼容函数/类/工厂

扩展条目统一用 `ref + config` 形态,并定义容错调用策略(伪代码):

```python
def call_ext(ref_obj, config, ctx):
    # 优先支持 (config, ctx) / (config) / (**config, ctx=ctx) / (**config) / (ctx) / ()
    ...
```

目的:
- YAML 用户可以用“类继承 + __init__”实现扩展,无需额外 glue
- 也可用纯函数/工厂函数实现
- ctx 可选,避免强耦合

### Decision 4: ExtensionBundle 作为聚合贡献模型(核心数据结构)

bundle factory 返回 `ExtensionBundle`(伪代码):

```python
@dataclass(frozen=True)
class ExtensionBundle:
    compute_functions: Dict[str, Callable[..., object]] = field(default_factory=dict)
    components: Tuple[object, ...] = ()
    output_formats: Dict[str, object] = field(default_factory=dict)
    aggregate_kinds: Dict[str, object] = field(default_factory=dict)
    transformers_raw: Tuple[Callable[[dict, object], dict], ...] = ()
    transformers_config: Tuple[Callable[[object, object], object], ...] = ()
    transformers_ir: Tuple[Callable[[object, object], object], ...] = ()
    transformers_request: Tuple[Callable[[object, object], object], ...] = ()
    analyzers: Tuple[Callable[[object], object], ...] = ()
```

Direct config 也会被编译为“隐式 bundle”,与显式 bundles 统一合并。

### Decision 5: 扩展生命周期固定为“显式编译管线”,并允许在多个阶段挂载 analyze/transform

本提案将 `ExtensionHost` 作为编译管线的前置步骤,用来一次性解决以下“漂移源”:
- raw transformers 的结果必须被 validator 看见(宏/默认值注入与校验一致)
- compute/where 的函数扩展必须在 **依赖推导/语义校验/IR 构造/运行期 predicate** 中完全一致
- custom aggregate 的 `required_fields()` 必须在“字段裁剪”发生前注入 required 字段闭包

编译管线(概念级,SSOT):

```text
YAML(load+imports) → raw(dict)
  → build ExtensionHost(api/enabled + direct + bundles; merge; summary)
  → build compute engine (SecureComputeEngine + host.compute_functions)
  → raw transformers (mutating; MUST NOT mutate `extensions` itself)
  → core validator (ConfigValidator; MUST use the same compute engine)
  → parse DemandConfig
  → outputs/aggregates/containers parsing MUST be extensions-aware
    - container.type MAY be custom format id when extensions enabled
    - custom aggregate kind/ref MUST compile to derived spec early enough to contribute required_fields()
  → config transformers (mutating; semantic changes)
  → DemandConfig → DemandIr (MUST use the same compute engine)
  → ir transformers (mutating)
  → build ExecutionRequest / OutputCompositionSpec (uses registries)
  → request transformers (mutating)
  → run_ir(...)
```

落地要求(对现有实现的结构性影响):
- 当前 `YamlDemandLoader.load()` 是 “validator → parse” 的单体实现;为了让 raw transformers 生效,需要拆分为可编排的步骤(例如 load_raw/validate/parse)或引入新的 extensions-aware pipeline 入口。
- `ConfigValidator`/outputs parser/runtime output composition MUST 共享同一套 compute engine(包含扩展函数名),否则会出现“依赖推导/校验通过但运行失败(或反之)”的漂移。

analyzers 允许挂载在至少两个稳定点(只读):
- `raw`(imports 展开后,validator 之前): 用于 lint/模板检查/禁用模式检查
- `compiled`(DemandConfig/DemandIr/ExecutionRequest 已具备后): 用于“计划/输出/依赖”的一致性检查与建议

### Decision 6: Compute/Where 扩展 = 扩展 SecureComputeEngine 的 allowed_function_map

目标:
- 不改变 AST 白名单模型
- 允许用户把常用“小函数”下放为 compute 函数,避免为小能力发版

“后”示例:

```yaml
extensions:
  compute:
    functions:
      safe_div: myapp.scalim_ext.compute:safe_div

fields:
  margin:
    compute: "safe_div(revenue - cost, revenue)"
```

要求:
- validator 与 runtime 编译必须使用同一套“扩展后的 compute engine”,否则会出现“validate 通过/运行失败(或反之)”的漂移。

#### Decision 6.1: Compute 依赖推导必须忽略函数名(否则扩展函数无法落地)

现状中 `extract_compute_dependencies()` 会把 `safe_div(a, b)` 的 `safe_div` 误判为字段依赖,从而导致:
- 派生字段 `compute` 推导 `depends_on` 时出现“未知字段 safe_div”
- outputs 的 `where` 校验/编译阶段出现同类错误

因此依赖推导必须收敛为:
- **字段依赖** = 表达式中作为“值引用”的 `Name`(变量/字段)
- **函数名** = `Call.func`(且仅允许 `Name` 风格调用) → MUST NOT 被计入字段依赖

伪代码(意图):

```python
class DependencyCollector(ast.NodeVisitor):
    def visit_Call(self, node):
        # 不访问 node.func,只访问 args/comparators 等
        for arg in node.args:
            self.visit(arg)
```

### Decision 7: YAML Components 注入(Observer/Hook),与 presets 叠加

目标:
- 用户不改 driver,就能为某个 YAML 临时挂载 hook/observer
- 仍复用 `split_components` 做类型校验并在装配期 fail-fast

示例:

```yaml
extensions:
  components:
    - ref: myapp.scalim_ext.hooks:LatencyBudgetHook
      config: {max_ms: 2000}
```

### Decision 8: 输出格式/容器扩展 = format registry(单输出 + composed outputs 复用)

核心决策:
- 引入 `format_id → factory` registry:
  - 内置: `csv`, `excel`(workbook 作为 excel 的 YAML alias)
  - 扩展: `parquet`, `jsonl`, `sqlite`, `s3_csv` 等由用户注册
- YAML `outputs[*].container.type` 从固定枚举扩展为 string format id,并新增 `container.options` 作为扩展配置载体(自由 dict)

“后”示例:

```yaml
extensions:
  outputs:
    formats:
      parquet: myapp.scalim_ext.outputs:parquet_format

outputs:
  - name: detail
    container:
      type: parquet
      path: ./output/detail.parquet
      streaming: true
      options: {compression: zstd}
    fields: [order_id, user_id, amount]
```

工厂最小契约(概念):
- 单输出: factory MAY 返回 `IRowSink`/`IColumnSink`/`ISink`
- composed outputs: factory MUST 返回 `IRowSink`(保持现有 composed outputs 的流式假设)

#### 8.1 `container.options` 必须可达(format factory 必须拿到扩展配置)

为避免每次新增格式都要求扩展核心 `OutputSpec` 字段,本提案引入:
- `outputs[*].container.options: object` 作为扩展配置载体(自由 dict)
- format factory MUST 接收 `options`(以及标准化的 `OutputSpec`/`ExportLayout`)并据此创建 sink

推荐的执行层契约(概念):
- 扩展 `OutputSpec` 以携带 `options`(DSL agnostic; 内置 csv/excel 忽略)
- 或引入 `OutputSinkConfig(OutputSpec + options)` 作为 registry 的输入(更显式,但改动面更大)

#### 8.2 Container handle(容器型输出)作为“完整方案”的一等公民

workbook 的本质是“多目标共享一个容器资源(同一路径一个 workbook handle)”。为了让扩展格式也能表达类似能力(例如 sqlite DB、zip 容器等),需要抽象 container handle:

```python
class IOutputContainerHandle(ABC):
    def create_row_sink(self, *, target_id, layout, options, sheet_name=None) -> IRowSink: ...
    def close(self) -> None: ...
```

format factory 可以选择:
- **file factory**: 每个 target 直接创建 sink(不共享资源)
- **container factory**: 先创建/复用 handle(按 `container_key` 缓存),再为每个 target 创建 sink

约束:
- composed outputs 仍 MUST 使用 streaming row sinks;因此 container handle 的 `create_row_sink` 必须返回 `IRowSink`

### Decision 9: 自定义派生聚合(aggregate)支持 kind/ref,并返回“编译后的聚合描述”

现状: YAML aggregate 固定为 group_by 配置。

决策:
- `outputs[*].aggregate` 支持三类形态:
  1) **内置 group_by**(保持现状)
  2) **kind**: `aggregate.kind: pivot` + `aggregate.options: {...}` 走 registry
  3) **ref**: `aggregate.ref: myapp.ext:pivot_aggregate` + `aggregate.config` 直指工厂

关键点: 自定义 aggregate 需要同时给出:
- `derived`: `IDerivedAggregationSpec`(用于 required_fields/fingerprint/parallel validation/build_aggregator)
- `output_field_ids`: 输出列(用于构造 `ExportLayout`)

因此 aggregate factory 不能只返回 `IDerivedAggregationSpec`,而应返回一个“编译产物”(伪代码):

```python
@dataclass(frozen=True)
class CompiledAggregate:
    derived: IDerivedAggregationSpec
    output_field_ids: Tuple[str, ...]
```

#### Decision 9.1: custom aggregate 必须在“字段裁剪”前注入 required_fields 闭包

当前 loader 会基于 outputs 收集 `required_field_ids`,再选择性解析/编译 fields。若自定义 aggregate 的 `derived.required_fields()` 直到运行期才可知,会导致 planner/executor 在 composed outputs 模式下缺字段。

因此当 `extensions.enabled=true` 且 outputs 使用 custom aggregate 时:
- 系统 MUST 在 parse fields 之前就能得到 `CompiledAggregate.derived.required_fields()` 并合并进 required_field_ids
- 实现上要求 outputs parser 在 extensions-aware 模式下可调用 aggregate factory(经 resolver + registry)以获得 `CompiledAggregate`

### Decision 10: ANALYZE = 只读分析器(不改行为),输出 issues/元信息

分析器目的:
- 扩展 `validate` 的语义校验能力(组织级规则、惯例检查、依赖检查)
- 为 CI/IDE 输出结构化诊断
- 为可观测性提供“编译期摘要”(例如把扩展贡献写入 viz meta/日志)

分析器最小契约(概念):
- 输入: 编译上下文(含 yaml_path/raw/config/ir/request 的可用子集)
- 输出: `issues`(errors/warnings) + `meta`(可选)

#### 10.1 分析输出契约(结构化 issues)需要一次性定型

analyzer 产出的 issues MUST 可被 CLI/IDE/CI 稳定消费,建议最小字段集合:
- `severity`: `error|warning|info`
- `code`: 可选,用于组织级规则编号
- `path`: YAML path(例如 `outputs.0.container.type`)
- `message`: 人类可读信息
- `source`: `{kind: "analyzer", ref: "<python-ref>", stage: "raw|compiled"}`
- `location`: 可选 `{line, column}`(CLI 可用 YAML location index 补全)

#### 10.2 CLI 集成决策(默认不执行;显式启用后可对拍)

- `scalim-cli yaml-dsl validate` 默认 **不解析/导入/执行** `extensions` 中的 Python 引用(避免校验命令隐式执行用户代码)。
- 但当 YAML 使用了扩展语法(例如 `container.type: parquet` / `aggregate.kind: pivot`)时,默认 validate MUST 给出可行动提示:
  - “此配置依赖 extensions registry;请使用 `--resolve-extensions` 并提供 allowlist/或 `--trusted`”
- `--resolve-extensions` 显式开启后:
  - 引用解析 + bundles 执行 + transformers/analyzers(按阶段)执行
  - 输出 `ExtensionHost.summary` + analyzers issues(可 `--json`)

### Decision 11: Transformers = 可变更语义的编译期变换器,按阶段挂载

transformers 是“改变行为”的扩展点,与 analyzers(只读)分离:
- `raw` transformers: 用于宏/模板展开/默认值注入
- `config/ir/request` transformers: 用于装配覆盖与高级定制

护栏:
- 变换器异常必须包含 stage/ref/yaml_path
- 默认冲突策略与顺序必须确定

### Decision 12: 冲突策略与确定性合并(必须可配置且可观测)

合并顺序(默认):
1) Direct config(隐式 bundle)
2) `extensions.bundles` 按声明顺序

冲突策略(默认建议):
- `compute.functions`/`outputs.formats`/`aggregates.kinds` 同名冲突: **error** 或 **warn+last-wins**(由 `extensions.conflicts` 配置)
- components/transformers/analyzers: 追加合并

必须提供“编译期摘要”:
- 最终启用的 bundles/analyzers/registries 列表(用于对拍与排障)

推荐补充: 冲突策略配置形状(概念):

```yaml
extensions:
  conflicts:
    compute_functions: error           # or last_wins
    output_formats: error              # or last_wins
    aggregate_kinds: error             # or last_wins
    analyzer_failure: error            # or warn
```

### Decision 13: 文档/生成边界与 drift gate(设计时明确,避免落地时返工)

需要同步的 SSOT 与门禁:
- canonical schema: `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- schema 生成入口: `scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`
- 前端 schema 镜像与漂移门禁: 见 `_X/03-frontends.md` 与 `just schema-drift-check`

原则:
- 扩展能力的“通用形状”必须进入 canonical schema
- 扩展内部的 `options/config` 允许自由 dict,避免每个扩展都驱动 schema 发版

## Before / After Examples (重点覆盖完整 scope)

### A) compute 扩展函数

**Before**: 需要发版或改用 `call_by`。

**After**:

```yaml
extensions:
  compute:
    functions:
      safe_div: myapp.scalim_ext.compute:safe_div
fields:
  margin:
    compute: "safe_div(revenue - cost, revenue)"
```

### B) YAML 注入 hook/observer

**Before**: 必须改 driver 传 `components=[...]`。

**After**:

```yaml
extensions:
  components:
    - ref: myapp.scalim_ext.hooks:LatencyBudgetHook
      config: {max_ms: 2000}
```

### C) 自定义输出格式 parquet

**Before**: outputs 只支持 workbook/csv,新格式要发版或 Python-only 装配。

**After**:

```yaml
extensions:
  outputs:
    formats:
      parquet: myapp.scalim_ext.outputs:parquet_format
outputs:
  - name: detail
    container: {type: parquet, path: ./out/detail.parquet, streaming: true, options: {compression: zstd}}
    fields: [order_id, amount]
```

### D) 自定义 aggregate: pivot

**After**:

```yaml
extensions:
  aggregates:
    kinds:
      pivot: myapp.scalim_ext.agg:pivot_aggregate
outputs:
  - name: pivot
    container: {type: workbook, path: ./out/r.xlsx, sheet: "pivot"}
    aggregate:
      kind: pivot
      options: {group_by: [province], metric: amount}
```

### E) ANALYZE: 组织级 lint/建议

```yaml
extensions:
  analyze:
    - ref: myapp.scalim_ext.analyze:lint_v1
      config: {level: warning}
```

### F) Transformers: 宏展开(可信 YAML 快速验证)

```yaml
extensions:
  transform:
    raw:
      - ref: myapp.scalim_ext.transform:expand_macros
```

## Risks / Trade-offs

- [风险] 扩展面大导致稳定性压力 → 缓解: 明确最小契约(ExtensionBundle + factories)并对外文档化;把“自由 dict options”限定在容器中,避免核心字段无限膨胀。
- [风险] validate 命令执行扩展带来安全/可复现问题 → 缓解: CLI 默认不执行扩展,需显式 `--resolve-extensions/--trusted` 开关。
- [风险] schema/editor 与 runtime 漂移 → 缓解: 扩展通用形状进入 schema;扩展细节走 options + analyzer;并把 schema 镜像纳入 drift gate。
- [风险] 自定义 outputs/aggregate 导致结果不可对拍 → 缓解: 要求 derived spec 提供 fingerprint_parts;输出/扩展摘要写入 meta/viz 便于对拍。

## Migration Plan

- 向后兼容:
  - 不含 `extensions` 的 YAML 行为不变
  - `extensions.enabled=false` 等价于未启用
  - `outputs.container.type: workbook/csv` 保持兼容;`workbook` 作为内置 alias
- 实施节奏:
  - 允许分阶段实现,但本提案的规范/接口一次性考虑到“全量 scope”,避免后续反复改 YAML 形状与契约。

## Open Questions

- CLI flags 设计: allowlist 参数如何表达(`--allow-module/--allow-function`),以及 `--trusted` 快捷模式是否默认开启通配符(并输出警告)?
- aggregate factory 的返回类型是否需要同时提供 header names/展示信息(与 `header_fields_output_by` 的交互)?
- transformers 的幂等/纯函数要求是否要在框架侧提供 best-effort 检测/告警?
