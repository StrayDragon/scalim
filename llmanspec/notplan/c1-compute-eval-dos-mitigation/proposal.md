# Proposal: compute-eval-dos-mitigation

> 一句话描述: 为 `SecureComputeEngine` 的高风险内置函数（`sum`/`sorted`/`map` 等）增加运行时迭代长度守卫（`ComputeLimits.max_iterable_len`），并评估移除 `repr`/`format`。

## Why

`SecureComputeEngine` 的 AST 沙箱对**表达式本身**有严格的节点数/深度/字面量限制，但允许的内置函数（`sum`、`sorted`、`filter`、`map`、`list`、`reversed`）对**运行时字段值**操作无界限。

恶意或意外的 loader 数据 + 表达式如 `sum(big_list)` 可耗尽 CPU/内存：
- `sum(huge_list)` — CPU 绑定
- `sorted(huge_list)` — CPU + 内存
- `list(map(str, huge_list))` — 内存放大

此外，`repr()` 和 `format()` 在白名单中，但在 compute 表达式场景中实用性有限，且可能泄露对象内部信息。

## What Changes

1. **为高风险内置函数添加运行时长度守卫**：类似 `_safe_range` 模式，包装 `sum`、`sorted`、`filter`、`map`、`list`、`reversed`、`enumerate`、`zip`，在执行前检查可迭代对象长度
2. **新增 `ComputeLimits.max_iterable_len` 参数**：控制运行时可迭代对象的最大长度（默认如 `100_000`）
3. **评估移除 `repr`/`format`**：降低信息泄露面（或降级为可选白名单）

## Capabilities

### Modified Capabilities

- `ir-field-compute` — compute 安全约束增强

## Impact

- **代码区域**: `src/scalim/dsl/yaml_dsl/_internal/config_parsing/security.py` (`SecureComputeEngine`)
- **破坏性**: 低 — 仅影响超大数据集上的 compute 表达式（新增限制有默认值）
- **安全**: DoS 风险从 Medium 降为 Low
