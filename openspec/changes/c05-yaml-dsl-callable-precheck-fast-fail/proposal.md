## Why

`YAML DSL` 允许用户在多个位置配置/注册 Python 可调用对象（例如 `loader`、派生字段 `call_by`、`normalize.call_by` 以及 `compute` 表达式中的安全内置函数调用）。

当前实现中,一类“参数绑定不匹配”的错误会在运行期才触发 `TypeError`（例如把位置参数传给仅关键字参数的函数）,并且在某些执行路径里会被 `guardrails` 归为“可预期计算错误”而静默吞掉,最终表现为字段值变成 `None`、`where` 过滤全部为 `False`、明细表 0 行等“无报错但结果全错”的高风险故障。

我们需要把这类错误从“运行期数据问题”提升为“编译期配置错误”,并为所有用户侧可调用引用点提供一致的快速失败(precheck/fast-fail)与可操作诊断,避免同类问题在其它 callable 位置重复出现。

## What Changes

- **新增编译期 callable preflight**: 在 demand runtime compile（以及 workflow preflight）阶段,对所有用户可配置的 callable 引用点执行统一预检查:
  - 引用解析(resolver/allowlist/builtin vocabulary)是否可解析为 callable
  - 对存在“可静态确定的调用形态”的位置,做参数绑定校验（例如 `call_by: "ref(args...)"`）
  - 对存在固定 contract 的位置,做签名/形状校验（例如 `normalize.call_by` / `should_retry`）
- **BREAKING**: 对于“参数绑定不匹配”的 callable,系统 MUST fail-fast 为编译期错误（不得继续执行并在运行期吞掉）。
  - 不再尝试把 `call_by: "fn(x)"` 自动解释为关键字参数调用；用户应显式改写为 `call_by: "fn(x=x)"`（或与函数签名一致的 kwargs 形态）。
- **compute 调用预检查(可选扩展)**: 对 `compute` 表达式中出现的安全内置函数调用（`SecureComputeEngine.SAFE_FUNCTIONS`）做参数个数/形态的静态校验（当 `inspect.signature` 可用时）,避免运行期 `TypeError` 被 `compute` 侧护栏吞掉导致静默错误。
- **诊断与错误生命周期收敛**: 将“callable 预检查失败”定义为配置/编译错误,与运行期 guardrails 的 quiet/fast_fail 策略解耦（guardrails 仅处理运行期数据/计算异常,不应吞掉可在编译期推理的配置错误）。
- **示例与回归门禁**: 为关键场景补充 notebooks 例子与集成测试入口,确保未来修改不会回退为静默吞错。

## Capabilities

### New Capabilities
- `yaml-dsl-callable-preflight`: 为所有用户可调用引用点提供统一的编译期预检查（解析、签名绑定、固定 contract 校验）与一致诊断/错误生命周期。

### Modified Capabilities
- `field-compute`: 派生字段 `call_by` 与 `compute` 的编译期校验范围扩展,新增“参数绑定不匹配”类错误的 fail-fast 语义。
- `demand-dsl`: demand compile 生命周期中新增/明确 callable preflight 阶段,并要求 loader/params 等 callable 相关配置在该边界完成可推理的契约校验。
- `yaml-source-normalize`: `normalize.call_by` 的 callable contract（入参/可选 `ctx`、返回 Mapping）在编译期进行可推理的签名预检查,避免 fail-late。
- `loader-retry-policy`: `should_retry(exc, ctx) -> bool` 回调契约补充签名预检查与一致诊断。
- `runtime-guardrails`: 明确 guardrails 的边界: 运行期护栏不得吞掉编译期可推理的 callable 配置错误；对“预检查失败”应直接作为 compile/config error 抛出。

## Impact

- 受影响代码主要集中在 `YAML DSL` 的 runtime compile（resolver/IR conversion/output composition compile）与少量 callable 执行辅助模块。
- 对已有配置的影响:
  - 合法配置无影响；
  - 过去“误配但运行期静默吞掉”的配置将变为编译期失败（这属于期望行为变更,避免产出错误报表）。
- 文档/生成物治理:
  - 行为规范以 `openspec/specs/*/spec.md` 为 SSOT；本变更的增量规范写入 `openspec/changes/.../specs/*/spec.md`。
  - 本变更不直接手工编辑任何 `*.gen.*` 生成物；如需同步 schema/doc,应修改对应 SSOT 并运行 `just gen-docs` / `just openspec-check` 验证漂移门禁。
