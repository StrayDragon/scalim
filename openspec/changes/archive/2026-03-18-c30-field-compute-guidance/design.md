## Context

当前 `compute` 的安全模型在实现上只允许受控的 AST 子集，并且只允许 `ast.Call(func=ast.Name)` 形式的函数调用；任何 `ast.Attribute` 形式的方法调用都会被拒绝（例如 `a.get(...)` / `s.strip()`）。

这条规则本身是合理且必要的：一旦允许 attribute call，很容易走向对象逃逸（`__class__` / `__mro__` / `__subclasses__` 等）并破坏“YAML 不等于脚本”的安全边界。

问题不在于“要不要放开方法调用”，而在于：
- 用户写出常见表达式后得到的报错缺少可操作的迁移提示；
- 文档虽然描述了 compute/call_by 边界，但没有覆盖 `.get()` 这类最常见的具体例子；
- 导致用户不得不反复把简单逻辑搬到 Python（但不知道这是推荐路径）。

## Goals / Non-Goals

**Goals:**
- 保持 compute 安全边界不变（仍拒绝 method call），但让报错与文档更“可迁移”。
- 当 compute 因方法调用被拒绝时，错误信息 MUST 指向 `call_by` 并给出最小可复制示例。
- 在 user guide 中给出典型 cookbook，减少下游重复造轮子与沟通成本。

**Non-Goals:**
- 不放开 `dict.get` / `str.strip` 等方法调用白名单（安全模型保持严格）。
- 不在本提案中新增一组内置“安全 helper 函数”（例如 `get(mapping, key, default)`）；如确有需要，留作后续独立提案评估其收益/风险与 API 演进成本。

## Decisions

### D1. 错误信息以“迁移提示”为核心，不改变安全规则

决定：当 `SecureComputeEngine` 拒绝 `ast.Attribute`/method call 时，错误文本必须包含：
- 明确原因：`compute` 不支持方法调用/attribute call；
- 迁移建议：将复杂逻辑迁移为 `call_by`；
- 最小示例片段（不要求与当前表达式完全等价，但应可复制粘贴作为起点）。

### D2. 文档添加 cookbook，覆盖 `.get()` 典型用例

决定：在 `docs/doc/yaml-dsl/user-guide.md` 的 compute/call_by 边界章节补充示例：
- “不被允许”的 `.get()` compute；
- “推荐”的 `call_by` 写法（强调 allowlist）。

## Risks / Trade-offs

- [用户期望落差] 用户仍然不能在 compute 中写 `.get()`：缓解 → 更明确地把 `call_by` 定位成推荐路径，并降低试错成本。
- [错误信息变动] 下游可能依赖旧错误文本：缓解 → 错误中保留稳定关键字（例如 `ast.Attribute`/`method call`）并为测试提供断言锚点。

