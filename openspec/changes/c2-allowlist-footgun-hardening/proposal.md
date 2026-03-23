## Why

当前 by_yaml 的 Python 引用 resolver allowlist 存在多处“误配置即失效”的脚枪：用户以为自己启用了约束，但实际把约束绕开/降级成 **denylist-only** 或 **全放开**。

主要风险点：

- `allowed_modules/allowed_functions` 支持通配符 `"*"`（`src/scalim/dsl/by_yaml/runtime/references.py`），这属于“隐式语法糖”，极易被误用到半可信 YAML 输入场景。
- `allowed_functions={"*"}` 会 **旁路 `allowed_modules` 模块约束**：`ResolverPolicy.check()` 会在函数侧短路返回，从而不再执行 `_check_allowed_module()`；这会让调用方误以为 module allowlist 生效，实际已被绕过。
- `ConfigToIRConverter(allow_unsafe_resolver=True)` 会在缺失 allowlist 时直接落到 `SecurePythonReferenceResolver()`（denylist-only）继续执行（`src/scalim/dsl/by_yaml/runtime/conversion.py`），属于高危的“默认安全语义被显式开关轻易破坏”入口。

### 最小复现：`allowed_functions={"*"}` 旁路模块 allowlist

```py
from scalim.dsl.by_yaml.runtime.references import SecurePythonReferenceResolver

resolver = SecurePythonReferenceResolver(
    allowed_modules=frozenset(["myapp.loaders"]),  # 期望只允许本业务包
    allowed_functions=frozenset(["*"]),  # 误以为“允许任意函数(但仍受模块约束)”
)

# 预期：应被 myapp.loaders 约束拒绝
# 实际：会成功 resolve（模块约束被旁路）
_ = resolver.resolve("pathlib:Path.cwd")
```

## What Changes

- **BREAKING**：移除 `"*"` 作为 allowlist 的隐式语法糖（默认一律报错）
  - `allowed_modules={"*"}` / `allowed_functions={"*"}` 在默认模式下必须 fail-fast，并给出迁移建议（见下）。
  - 目的：让“全放开”只能通过显式 opt-in 打开，而不是靠一个字符串悄悄关闭约束。
- 引入显式的“可信/全放开”开关（不太限制可信场景）
  - 例如 `trusted_mode=True` 或 `allow_all_modules=True`（命名在 design 中确定）。
  - CLI/日志必须强告警：明确提示当前在不安全模式运行、allowlist 约束被放宽（并建议仅用于内部/测试）。
- 增加配置互斥与一致性护栏（防误用）
  - 禁止 `allowed_functions={"*"}` 与 `allowed_modules` 混用（原因：它会旁路模块约束；要全放开请走统一的 trusted_mode）。
  - trusted_mode 与显式 allowlist 同时出现时建议直接报错（避免用户以为“部分约束仍生效”）。
- **BREAKING**：将 `allow_unsafe_resolver` 改名/改语义为 “denylist-only（不安全）”
  - 改成更不易误解的名称（例如 `unsafe_denylist_only_resolver=True`；最终命名在 design 中确定）。
  - 要求额外显式确认（例如环境变量二次确认 + 参数开关），避免无意开启。
  - 同步增强错误/告警信息：解释“denylist-only 不是 allowlist”，并提示何时应该使用（仅测试/演示/可信输入）。
- 增加回归测试与文档更新
  - `"*"` 默认报错与提示信息的稳定性测试。
  - `allowed_functions={"*"}` 与 `allowed_modules` 混用必须 fail-fast 的测试。
  - unsafe denylist-only 必须通过“双确认”才能启用的测试（CLI + env 或等价机制）。

## Capabilities

### New Capabilities
- `yaml-dsl-allowlist-policy`: 定义 allowlist/trusted-mode/denylist-only 的安全语义、互斥规则、默认值与强告警要求。

### Modified Capabilities
- `demand-dsl`: 收敛 allowlist 的行为边界（默认禁止 `"*"`、明确 trusted-mode 语义、明确 denylist-only 的显式 opt-in 约束）。
- `dsl-runtime-structure`: 对外 API 合约对齐新的 allowlist/trusted-mode/denylist-only 语义（含 `ConfigToIRConverter` 的不安全入口双确认要求）。
- `yaml-dsl-cli-validation`: CLI 需要暴露 trusted-mode/denylist-only 的显式开关，并在 `"*"`/混用/不安全模式下提供强诊断与阻断策略。

## Impact

- 受影响代码路径（实现阶段）：
  - `src/scalim/dsl/by_yaml/runtime/references.py`（ResolverPolicy 与 `"*"` 处理、互斥校验、告警）
  - `src/scalim/dsl/by_yaml/runtime/compiler.py` / `src/scalim/dsl/by_yaml/runtime/entrypoints.py`（新增 trusted-mode 入口或校验）
  - `src/scalim/dsl/by_yaml/runtime/conversion.py`（`allow_unsafe_resolver` 改名与双确认 gate）
  - `src/scalim/cli/yaml_dsl.py`（新增/调整 CLI 参数、强告警与错误提示）
  - `openspec/specs/*`（规范更新）与 `tests/`（安全回归测试）
- 行为变化（对用户的影响）：
  - 任何依赖 `"*"` 的旧用法将默认 fail-fast；需要显式开启 trusted-mode 才能继续使用“全放开”能力。
  - denylist-only（原 allow_unsafe_resolver）将更难被误启用：需要明确 opt-in + 二次确认。
