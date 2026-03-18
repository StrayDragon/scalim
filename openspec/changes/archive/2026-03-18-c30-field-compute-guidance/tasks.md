## 1. 规范与文档

- [x] 1.1 更新增量规范：在 `openspec/changes/c30-field-compute-guidance/specs/field-compute/spec.md` 新增“method call 被拒绝时必须给出 call_by 迁移提示”的 REQUIREMENT 与场景。
- [x] 1.2 更新手写 SSOT 文档 `docs/doc/yaml-dsl/user-guide.md`：补充 `.get()` 典型示例与 `call_by` 推荐写法；避免修改任何 `BEGIN/END AUTOGEN:*` 注入区块内部内容。

## 2. 实现与测试

- [x] 2.1 在 `src/scalim/dsl/by_yaml/config_parsing/security.py` 为 method call/attribute call 的拒绝路径补充可复制的迁移提示（指向 `call_by`）。
- [x] 2.2 新增/调整单测：覆盖 `.get()` / `.strip()` 在 compute 中被拒绝时，错误信息包含稳定关键字与迁移提示。

## 3. 门禁

- [x] 3.1 运行 `just openspec-check` 确保 OpenSpec 工件结构与脱敏规则通过。
- [x] 3.2 运行 `just qa`（或至少覆盖 compute 校验相关单测）确保无回归。
