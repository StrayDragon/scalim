## Why

`compute` 表达式的安全沙箱是 Scalim 的关键边界：它故意限制表达式能力（禁止 attribute/subscript/dunder 等对象逃逸路径），以避免把 YAML 变成“可执行脚本”入口。

但下游在真实迁移中频繁遇到的痛点是：很多自然写法（例如 `dict.get()` / `str.strip()`）会被直接拒绝，而错误信息与文档边界不够“可操作”，导致用户以为是 bug，最终只能在 loaders.py 写大量样板 `call_by` 辅助函数。

我们对安全模型本身是满意的（不计划放开 method call），但需要把“遇到表达式能力边界时应该怎么做”讲清楚，并让报错直接指向 `call_by` 作为能力逃生舱。

## What Changes

- 明确并固化 `compute` 的边界文案：方法调用/attribute call 在 compute 中**必定被拒绝**，复杂逻辑应使用 `call_by`。
- 改进 compute 校验错误信息：当表达式因 method call 被拒绝时，错误 MUST 提供可复制的迁移提示（指向 `call_by`，并给出最小示例）。
- 补齐文档示例：在 YAML DSL user guide 中增加一段“compute 写不出来时 → call_by”的 cookbook，覆盖 `.get()` 典型用例。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `field-compute`: 新增“compute 被安全引擎拒绝时的可操作报错/迁移提示”要求与示例场景，提升 compute→call_by 的迁移体验。

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/config_parsing/security.py`（`SecureComputeEngine` 的校验/错误信息）
  - （可能）`src/scalim/dsl/by_yaml/config_parsing/parsers/fields.py`（错误归因路径补充）
- 受影响文档：
  - `docs/doc/yaml-dsl/user-guide.md`（手写 SSOT；注意不要修改 injected blocks 内部）
- 测试影响：
  - 新增/调整单测，覆盖 `.get()` 等 method call 被拒绝时的报错内容与提示稳定性。

