## Why

在 `v0.9.9`（commit `d78f9d2f`：`refactor: policy-normalization-breaking-cleanup`）中，我们把多组 “policy-like（封闭集合）” 从 `StrEnum` 迁移到了 `Literal[str]` + `normalize_* -> builtin str` 的模式，并在入口强制 `type(x) is str`，以确保 state/pickle 等边界只存储内置类型并避免 `str` 子类/Enum 在跨边界时带来的不确定性。

另外，`FailurePolicy` 相关的 `StrEnum` + `Literal[...]` 双定义与 normalize 分支是在更早的 commit `7f52e103`（`qa: refactor & pythonic recoding`，被 `v0.9.7` 收录）引入的。

但这个改变对用户侧体验不友好：
- 用户更偏好 **Enum 作为 API**（更强的约束、更好的 IDE 补全/发现性、可扩展方法/语义）。
- 目前实现会同时存在 `StrEnum` 与 `Literal[...]` 两套定义（例如 `FailurePolicy`），可维护性差（非 DRY），且让“到底该用哪一种”变得模糊。

本变更的目标是：**对用户恢复 Enum（一等公民），同时仍然在序列化/状态边界保证稳定 builtin `str` 形态**，并用单一 SSOT 消除 Enum/Literal 的手工重复定义。

## What Changes

- **BREAKING**: policy 相关的 public surface 回到 “Enum/`StrEnum` 一等公民”，接口层严格收敛为 Enum（推荐/默认写法回到 `XPolicy.FOO`），不再把 `"foo"` 作为首选 authoring surface。
- 统一 policy 的 SSOT：每组 policy **只定义一次**（Enum/`StrEnum`），允许值集合、错误信息 label、序列化字符串值均从 Enum 派生，禁止手工维护 `StrEnum` + `Literal[...]` 双份列表。
- 边界分层（严进宽出）：
  - **输入边界**（公开 API）：严格只接受 Enum（fail-fast）。
  - **配置/反序列化边界**（YAML/JSON/state/pickle）：允许 builtin `str`，并通过统一的 parse/format SSOT 映射到 Enum。
  - **输出边界**（state/wire）：统一输出稳定的 builtin `str`（`.value`），确保对象图可跨版本长期存取；运行时内部优先存储 canonical builtin `str`（最小热路径扰动）。
- 迁移并覆盖当前高优先级 policy（先收敛跨边界的封闭集合）：
  - `LoaderResultPolicy`
  - `ObserverManagerMode`
  - `CaptureOverflowPolicy`
  - `FailurePolicy`（清理现有 Enum/Literal 重复定义）

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `runtime-policy-normalization`: 将 “入口强制 builtin `str` + 内部只存 `str`” 调整为 “用户侧 Enum，一切序列化/状态边界只存 builtin `str`，并允许从边界字符串恢复为 Enum；policy 定义以 Enum 为唯一 SSOT（DRY）”。

## Impact

- 受影响模块（预期）：
  - hooks/ob 的 manager/state（policy 字段的存储与 (de)serialization）
  - YAML DSL / CLI 配置入口（policy 字符串解析为 Enum）
  - tests/governance（policy roundtrip、pickle roundtrip、错误信息）
- 版本与历史定位：
  - `FailurePolicy` 的 Literal/normalize 模式在 `v0.9.7`（commit `7f52e103`）引入。
  - hooks/ob 的 `LoaderResultPolicy` / `ObserverManagerMode` / `CaptureOverflowPolicy` 等从 Enum → Literal 的主要 breaking 发生在 `v0.9.9` 区间（`v0.9.8..v0.9.9`），核心 commit 为 `d78f9d2f`。
  - `v0.9.13` 版本只是“仍然包含上述 breaking 的后续版本”，并不是引入 breaking 的起点。
