# yaml-dsl-callable-preflight Specification

**状态: ✅ 已实现**
## Purpose
定义 YAML DSL 在 demand compile / workflow preflight 阶段的 callable preflight: 在 resolver 安全边界就绪后,对用户可配置的 Python callable 执行“可推理的签名/形态/固定 contract”校验,并在失败时 fail-fast。

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/yaml_dsl/runtime/_internal/callable_preflight.py`
- `src/IMPL_ROOT/dsl/yaml_dsl/runtime/_internal/call_by_signature.py`
- `src/IMPL_ROOT/dsl/yaml_dsl/runtime/_internal/conversion_sources.py`
- `src/IMPL_ROOT/dsl/yaml_dsl/runtime/compiler.py`
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/security.py`

## Requirements
### Requirement: callable preflight MUST run at the resolver boundary and fail-fast
系统 MUST 在 demand runtime compile（以及 workflow preflight 中对每个 run 的 demand compile）阶段,在“resolver 已就绪”边界执行 callable preflight,并在发现第一个可推理错误时立即 fail-fast 抛出配置/编译错误:

- callable preflight MUST 在 allowlist/builtin vocabulary 已生效的 resolver 可用后执行（不得在缺失安全边界的情况下尝试导入/解析用户引用）。
- callable preflight MUST 覆盖所有“用户可配置为 Python callable”的入口点（至少包含 `loader`、派生字段 `call_by`、聚合后派生字段 `call_by`、`normalize.call_by`、`should_retry` 以及 `compute` 的安全内置函数调用形态检查）。
- callable preflight MUST NOT 执行用户 callable（不得调用函数体）,仅允许解析引用与做签名/形态/固定 contract 校验。
- callable preflight 失败 MUST 被归类为 compile/config error,不得进入运行期 guardrails 的 quiet/吞错语义。

#### Scenario: call_by signature mismatch fails at compile time
- **GIVEN** 派生字段声明 `call_by: "pkg.mod:fn(x)"` 且 `fn` 的 Python 签名为 keyword-only（例如 `fn(*, x)`）
- **WHEN** 调用方执行 demand `compile/run`（或 workflow preflight 执行到 demand compile）
- **THEN** 系统 MUST 在编译期失败并报告“参数绑定不匹配”
- **AND** MUST NOT 进入运行期执行（不得把该错误吞掉并将字段写为 `None`）

### Requirement: callable preflight diagnostics MUST be actionable and include rewrite hints
当 callable preflight 因“参数绑定不匹配”失败时,错误诊断 MUST 至少包含:

- callsite location（例如 `派生字段 '<field_id>'` / `outputs.<name>.aggregate.fields.<field_id>` / `sources.<id>.normalize.call_by`）
- callable reference（例如 `pkg.mod:fn`）
- `inspect.signature` 形式的签名文本（当可用）
- `TypeError` 的绑定失败原因摘要
- 至少一个可照抄的迁移建议（例如把位置参数改写为关键字参数 `x=x`）

#### Scenario: keyword-only rewrite hint is provided
- **GIVEN** `call_by: "pkg.mod:fn(group_name)"` 且目标函数签名为 `fn(*, group_name)`
- **WHEN** 系统执行 callable preflight
- **THEN** 编译失败的错误信息 MUST 包含可照抄的改写建议 `fn(group_name=group_name)`

### Requirement: loader params kwargs keys MUST be prechecked against loader signature when possible
当 `main_source.params` / `sources.<id>.params` 声明了传给 loader 的 `kwargs` 模板时,系统 MUST 在编译期对 **kwargs keys** 做可推理的签名绑定预检查（当 `inspect.signature` 可用时）:

- 系统 MUST 基于 `params` **top-level mapping keys**（无需渲染/无需执行）构造 placeholder `kwargs` 并执行 `signature.bind(**kwargs)` 校验。
- 预检查 MUST 覆盖:
  - 未知 keyword（`unexpected keyword argument`）
  - 缺失必填参数（`missing a required argument`）
- 预检查失败 MUST fail-fast 作为配置/编译错误（不得延迟到运行期 loader 调用才暴露）。
- 当 `inspect.signature` 不可用时系统 MAY 跳过绑定校验,但仍 MUST 保持 loader 引用解析与可调用性校验。

#### Scenario: loader params unknown keyword fails fast
- **GIVEN** `sources.customers.loader: "pkg.mod:load_customers"` 且其签名为 `load_customers(ids, field_keys=None, *, is_ref_loader=False)`
- **AND** `sources.customers.params: { bad_key: 1 }`
- **WHEN** 系统编译 demand
- **THEN** 编译 MUST fail-fast 并指出 `bad_key` 无法绑定到 loader 的签名

