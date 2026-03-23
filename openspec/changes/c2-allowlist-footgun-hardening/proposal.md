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

- **BREAKING**：移除 `"*"` 作为 allowlist 的隐式语法糖（默认一律 fail-fast）
  - `allowed_modules={"*"}` / `allowed_functions={"*"}` 在默认模式下 MUST fail-fast，并给出可复制的迁移建议。
  - 目的：把“全放开”从“一个字符串悄悄放宽”升级为“显式声明的信任边界”。
- 引入显式的 resolver 安全模式（SSOT：单一枚举，而不是散落的 bool）
  - 以 `resolver_trusted_mode=<enum>`（最终命名见 design）表达 `strict_allowlist` / `trusted_allow_all_modules` /（可选）`denylist_only` 等模式。
  - 默认值必须是安全默认：`strict_allowlist`。
  - 任何非默认模式 MUST 强告警（稳定日志前缀 + `k=v` 字段），避免“看起来开了约束但实际没生效”的错觉。
- 增加配置互斥与一致性护栏（防误用，默认 fail-fast）
  - `allowed_functions={"*"}` 一律拒绝（它无法表达“仍受模块约束”，只会制造脚枪）。
  - `trusted_allow_all_modules` 与显式 allowlist（`allowed_modules/allowed_functions`）混用时 MUST fail-fast（避免用户以为“部分约束仍生效”）。
- **BREAKING（倾向）**：移除 `ConfigToIRConverter(allow_unsafe_resolver=...)` 逃逸口子
  - 倾向直接删除该参数并统一为：**缺少 allowlist 必须严格失败**（并给出友好提示）。
  - 若未来确有内部/测试场景需要 denylist-only，应作为单独的、强标注的 unsafe entrypoint（不通过环境变量隐式改变框架行为）。
- 增加回归测试与文档更新（以“可验证的失败信号”取代“仅靠约定”）
  - `"*"` 默认拒绝与迁移提示稳定性测试。
  - `allowed_functions={"*"}` 必须 fail-fast 的测试（含与 `allowed_modules` 混用）。
  - trusted mode 的强告警可观测测试（不依赖外部 observer/hook）。

## Sequencing / Dependencies

- 建议作为安全基线优先落地（在 `yaml-template-vars-sandbox` / `yaml-path-escape-hardening` / `yaml-dsl-import-aliases-and-presets` 之前），以统一“显式信任边界 + 默认 fail-fast”口径。

## Capabilities

### New Capabilities
- `yaml-dsl-allowlist-policy`: 定义 allowlist/trusted-mode/denylist-only 的安全语义、互斥规则、默认值与强告警要求。

### Modified Capabilities
- `demand-dsl`: 收敛 allowlist 的行为边界（默认禁止 `"*"`、明确 trusted-mode 语义、明确 denylist-only 的显式 opt-in 约束）。
- `dsl-runtime-structure`: 对外 API 合约对齐新的 allowlist/trusted-mode/denylist-only 语义（含 `ConfigToIRConverter` 的不安全入口双确认要求）。

## Impact

- 受影响代码路径（实现阶段）：
  - `src/scalim/dsl/by_yaml/runtime/references.py`（ResolverPolicy 与 `"*"` 处理、互斥校验、告警）
  - `src/scalim/dsl/by_yaml/runtime/compiler.py` / `src/scalim/dsl/by_yaml/runtime/entrypoints.py`（新增 trusted-mode 入口或校验）
  - `src/scalim/dsl/by_yaml/runtime/conversion.py`（移除或重构 `allow_unsafe_resolver` 逃逸口子）
  - `openspec/specs/*`（规范更新）与 `tests/`（安全回归测试）
- 行为变化（对用户的影响）：
  - 任何依赖 `"*"` 的旧用法将默认 fail-fast；需要显式开启 trusted-mode 才能继续使用“全放开”能力。
  - （若按倾向执行）denylist-only（原 allow_unsafe_resolver）入口将被移除；缺少 allowlist 一律严格失败并提示迁移方案。
