## Context

`YAML DSL` 的多个配置点允许用户提供 Python 可调用对象（通过安全引用 + allowlist / builtin vocabulary）:

- `main_source.loader` / `sources.*.loader`
- `main_source.params` / `sources.*.params`（传给 loader 的 kwargs 模板; keys 形态可在编译期推理）
- `fields.*.call_by`（派生字段）
- `outputs[*].aggregate.fields.*.call_by`（聚合后派生字段）
- `sources.*.normalize.call_by`（whole-result normalize 扩展点）
- `loader retry should_retry`（driver/yaml 注入的回调）
- `compute` 表达式中的安全内置函数调用（`SecureComputeEngine.SAFE_FUNCTIONS`）

其中一类常见故障是“参数绑定不匹配”:

- YAML `call_by: "ref(x)"` 会被按 Python 调用语义编译为位置参数调用 `fn(x)`
- 但用户函数可能是 keyword-only 签名（例如 `def fn(*, x): ...`）
- 运行期触发 `TypeError: ... takes 0 positional arguments but 1 was given`
- 在某些执行链路（尤其是 compute operator）里该 `TypeError` 可能被 guardrails 视为“预期计算错误”而转为 `None` 并继续执行,最终导致静默错误（例如 `where: "... and _is_valid_group"` 把所有行过滤干净）

这类错误具备两个特征:

1) **可在编译期推理**（无需执行函数体,仅需签名绑定/契约检查）
2) **运行期吞错代价极高**（不报错但产出空/错报表）

约束:

- 运行时代码(`src/scalim/`)必须兼容 Python 3.6（避免依赖 `inspect.Parameter.POSITIONAL_ONLY` 等新特性）。
- 预检查不得执行用户函数体（避免副作用/安全风险）；只做解析、引用解析与签名/形状约束校验。
- allowlist/builtin vocabulary 仍是安全边界；任何“预检查”都不得扩大允许导入面。
- 文档治理保持不变：不手工编辑任何 `*.gen.*`；OpenSpec delta specs 为手工 SSOT；校验门禁为 `just openspec-check`。

## Goals / Non-Goals

**Goals:**

- 在 demand runtime compile（以及 workflow preflight）阶段新增/收敛统一的 callable preflight,对所有 callable 引用点执行一致的 fail-fast 预检查。
- 对“参数绑定不匹配”类错误,在编译期抛出可操作诊断（包含引用、签名、错误原因、以及可直接照抄的改写建议）。
- 明确错误生命周期边界：callable preflight 失败属于配置/编译错误,不得落入运行期 guardrails 的 quiet/吞错语义。
- 在不引入新外部依赖的前提下,保持实现可测试、覆盖充分且顺序确定性（deterministic）。

**Non-Goals:**

- 不引入兼容层：不把 `call_by: "fn(x)"` 自动转换为关键字调用；用户必须显式改写为 `call_by: "fn(x=x)"` 或其它与签名一致的形式。
- 不做运行期值类型校验（例如 `int("x")` 的值域问题仍属于运行期错误）；预检查只覆盖“形态/绑定/契约”可推理部分。
- 不在编译期执行任何用户函数（包括 loader/normalize/call_by/should_retry）。
- 不试图让 `scalim-cli yaml-dsl validate` 在默认模式下导入用户模块（避免把 validate 变成有副作用的入口）；如需 CLI 支持,应提供显式 opt-in 的 preflight 子命令/开关。

## Decisions

### Decision 1: 引入 SSOT 的 callable preflight helper

增加一个内部 SSOT 模块,用于承载:

- 统一的签名绑定校验（基于 `inspect.signature(...).bind(...)`）
- 统一的错误消息格式（中文 + 关键片段用反引号包裹）
- 统一的“location/path”注入策略（例如 `派生字段 '<id>'` / `outputs.<name>.aggregate.fields.<id>`）

并要求所有 callsite 复用它（derived `call_by`、aggregate `call_by`、后续扩展到 loader/normalize/should_retry/compute builtins）。

理由:

- 避免在多个编译器/转换器中复制 `inspect.signature` 的分支与错误文案,减少 drift 与漏修风险。
- 让“可调用契约”从实现细节收敛为可测试的独立单元。

### Decision 2: 以“签名绑定”作为参数不匹配的判定口径

对 `call_by` 这类存在明确参数列表的场景:

- 解析出 args/kwargs 形态（不执行求值）
- 使用 placeholder 值做 `sig.bind(*args, **kwargs)` 绑定校验
- 当绑定失败时,直接在编译期抛出错误,并提供改写建议（例如 keyword-only 形态提示改为 `x=x`）

当 `inspect.signature` 无法获取签名（少数内置/扩展 callable）,预检查跳过“绑定校验”但仍保留:

- 引用解析（必须能 resolve 为 callable）
- 固定 contract 校验（能在不依赖签名的情况下进行的部分）

理由:

- `bind` 能覆盖 keyword-only/varargs/varkw 等复杂签名,且不需要执行函数体。
- 对不可 introspect 的 callable,强行预检查会引入误报或复杂回退策略；跳过更可控。

### Decision 3: 预检查边界放在“具备 resolver 的 compile/preflight”阶段

callable preflight 需要 resolver/allowlist/builtin vocabulary 才能解析引用到具体 callable,因此预检查边界选在:

- demand runtime compile（`YAML -> DemandConfig -> DemandIr -> ExecutionRequest`）过程中
- workflow 的 preflight 阶段（engine 启动前）对每个 demand run 执行 demand compile,并把错误视为 workflow config/compile error

这保证:

- 不需要让 “schema validate / 纯结构 validate” 导入用户代码
- 与安全边界一致（缺失 allowlist 的入口仍 fail-fast）

### Decision 4: 对 `compute` 表达式增加“可推理的调用形态”预检查

对 `SecureComputeEngine.SAFE_FUNCTIONS` 中的函数调用:

- 解析 AST 找到 `Call` 节点（当前已经禁止 keyword args,因此仅需校验位置参数个数/可变参数形态）
- 对可 introspect 的 builtin,使用 `inspect.signature(...).bind(...)` 做“仅形态”校验
- 预检查失败视为 `compute` 编译错误,不得延迟到运行期并被 guardrails 吞掉

理由:

- 这类错误同样会在运行期表现为 `TypeError` 并造成静默 `None` 链式传播。
- 因为 compute 表达式已限制语法节点集合,静态扫描与校验可控且确定性强。

### Decision 5: 文档/生成物边界与 drift gate

- OpenSpec delta specs（本 change 下的 `specs/*/spec.md`）为本变更的规范 SSOT。
- 任何 `*.gen.*` 与 injected blocks 禁止手工编辑；如预检查引入新的 YAML 文案或 schema 文档变化,应修改对应 SSOT（例如 schema_dsl models/doc_texts）并运行 `just gen-docs` 刷新。
- 验收门禁:
  - `just openspec-check`（sanitize + `openspec validate --all --strict --no-interactive`）
  - `just qa`（lint/tests + drift checks）

### Decision 6: loader `params` 的 preflight 仅校验 **top-level kwargs keys**

`main_source.params` / `sources.<id>.params` 在执行期以 `loader_fn(**kwargs)` 形态调用（`YAML` 的 params template binding 不产生位置参数）。

因此预检查策略为:

- 仅使用 **top-level mapping keys** 构造 placeholder `kwargs` 做 `inspect.signature(loader_fn).bind(**kwargs)` 校验（当签名可 introspect 时）。
- 不渲染 params template（不需要 `ctx.lookup_keys` / `ctx.batch_rows`）,也不执行 loader。
- `params` 为空映射时跳过（允许 loader 0-arg 调用/或由其它 binding 注入参数）。
- 当签名不可获取（`inspect.signature` 抛 `TypeError/ValueError`）时跳过绑定校验,但仍保留“引用解析必须成功”的边界。

### Decision 7: `should_retry` 的 preflight 在 YAML compile 期完成,以避免运行期静默降级

`LoaderRetryPolicy` 当前通过 `_safe_should_retry` 将回调异常（含签名 `TypeError`）吞掉并当作 `False` 处理,会把“误配”降级为“无重试”。

因此当 retry 启用且回调可 introspect 时:

- 在 build_request/编译阶段对 `should_retry(exc, ctx)` 做 `signature.bind(placeholder_exc, placeholder_ctx)` 校验。
- 失败时直接抛出 compile/config error（不得等到第一次 loader 异常后才暴露）。
- 诊断 location 以可定位为目标（例如 `loader_retry.default.should_retry` / `loader_retry.by_loader.<loader_id>.should_retry`）,不强依赖 YAML path（因为来源可能是 runtime injection）。

### Decision 8: 诊断输出应“稳定可断言”,并显式覆盖 py3.6 兼容分支

- 对于签名绑定类错误,诊断 MUST 包含:
  - `location/path`（callsite + config path）
  - callable reference（若来源为引用字符串）
  - 签名文本（当可用）
  - bind 失败原因摘要（`TypeError` message）
  - 至少一个可照抄的改写 hint（如 keyword-only 的 `x=x`）
- 实现必须兼容 `py3.6`:
  - 使用 `getattr(inspect.Parameter, "POSITIONAL_ONLY", None)` 处理 positional-only kind
  - 不引入 `inspect.Signature.bind_partial` 的新语义依赖（以 `bind` 为 SSOT）

## Risks / Trade-offs

- [签名不可 introspect 导致漏检] → 预检查在 `inspect.signature` 失败时跳过绑定校验；缓解: 错误仍会在运行期暴露,并优先覆盖“用户自定义 Python 函数”这一主路径。
- [compute builtin 在不同 Python 版本签名差异] → 仅对可 introspect 且行为稳定的函数做绑定校验；其余跳过；并用单元测试锁定关键用例（例如 `dec(x)`）。
- [loader/params/normalize/should_retry 预检查覆盖面更大] → 以“仅校验形态/绑定/契约”为边界,避免引入运行期行为；并用 notebooks 端到端回归锁定关键链路.
- [行为更严格带来“破坏性变更”] → 明确这是“修复静默错报表”的安全升级；通过错误信息提供可直接照抄的迁移建议,降低升级成本。

## Notebooks / Regression Strategy

原则:

- **好例子融入全面 YAML fixture**: 尽量把“正确写法”融入已有的全面 YAML 样例（例如 `support/support_sla_report.yaml`）,让现有章节作为 good-path gate。
  - 好处: 减少重复 YAML,同时确保“真实复杂需求”不会被 preflight 误伤。
- **坏例子独立 chapter**: 用独立章节写入临时 YAML,仅覆盖“必须编译期 fast-fail”的错误形态（参考 `yaml_dsl_call_by_keyword_only`）。
- **should_retry 端到端**: 因为 `should_retry` 来自 runtime injection,必须用独立章节覆盖：
  - 坏签名 → 编译期失败（不能等到第一次 loader 异常才暴露）
  - 好签名 → loader fail-once 后可 retry 成功（验证回调确实被执行并生效）

建议把“新增预检查点”的 notebooks gate 映射成可回归的矩阵:

| Surface | Good-path gate（尽量复用） | Bad fast-fail gate（新增 chapter） |
|---|---|---|
| 派生字段 `call_by` | `yaml_dsl_ecommerce`（`declared_yaml_dsl/ecommerce_report.yaml` 已包含 kwargs call_by） | `yaml_dsl_call_by_keyword_only`（已存在） |
| `compute` SAFE_FUNCTIONS 调用 | `yaml_dsl_support` / `yaml_dsl_ecommerce`（多处 `Decimal(...)`/`round(...)`） | `yaml_dsl_compute_builtin_arity_mismatch`（例如 `len(x, y)`） |
| `sources.*.normalize.call_by` | 将 `normalize.call_by` 融入 `support/support_sla_report.yaml` 的某个 `source`（保持输出不变,只做 identity normalize） | `yaml_dsl_normalize_call_by_signature_mismatch`（例如 `def norm(*, result): ...`） |
| loader `params` kwargs keys | `yaml_dsl_support`（`sources.*.params` 已覆盖 `ids` / `field_keys` / kwonly） | `yaml_dsl_loader_params_signature_mismatch`（未知 kw / 缺失必填 kw） |
| retry `should_retry(exc, ctx)` | `yaml_dsl_ads`（已验证 retry_calls==2） | `yaml_dsl_should_retry_signature_mismatch`（注入 kwonly/缺参 should_retry,要求 compile 期失败） |

## Migration Plan

1. 升级后若遇到 `call_by` 预检查失败:
   - 按错误提示把位置参数改写为关键字参数（例如 `fn(x)` → `fn(x=x)`）。
2. 对 compute 表达式中误用内置函数的情况:
   - 按错误提示修正参数个数（例如 `dec(a, b)` 改为 `dec(a)`）。
3. 对 `normalize.call_by` 的签名不匹配:
   - 按错误提示调整函数签名以接受 `(result)` 或 `(result, ctx)`（或 `ctx` keyword-only 形态）。
4. 对 `should_retry` 的签名不匹配:
   - 按错误提示调整回调签名为 `should_retry(exc, ctx) -> bool`。
5. 对 loader `params` 的签名不匹配:
   - 修正 `params` 中的 kwargs keys,使其能绑定到 loader 的签名（例如移除未知 key 或补齐必填 key）。
6. 在 notebooks 中提供“坏例子必须 fail-fast / 好例子可运行”的回归样例,并纳入集成测试。

## Open Questions

- 是否需要新增一个更明确的异常类型（例如 `ScalimCallablePreflightError`）以便上层统一捕获并区分于一般 `ScalimConversionError`？
> 需要

- 是否需要在 CLI 中提供显式的 `yaml-dsl preflight`（要求用户提供 allowlist,仅做 resolve + precheck,不执行）以便 CI/IDE 更早发现问题？
> 暂时不需要 当前 用户的 run 可以执行前立即fast-fail 就够用 , 避免引入新的命令导致难以维护, 但是可以足够拆分细致api留足空间以便之后可能做这个处理
