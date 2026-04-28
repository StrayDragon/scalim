## ADDED Requirements

### Requirement: resolver MUST enforce denylist during attribute traversal (including trusted mode)

即使在 `resolver_trusted_mode=trusted_allow_all_modules` 放宽模块 allowlist 的情况下,Python 引用解析器也 MUST 对危险模式保持 denylist 防御深度。

系统 MUST 在解析 class-style 引用的属性链遍历过程中逐级执行 denylist 校验:
- 属性名命中危险函数列表(例如 `getattr/open/eval/...`) MUST fail-fast
- 属性名包含 `__` 或等价自省危险模式 MUST fail-fast
- 属性名为 `lambda` MUST fail-fast

该要求的目的是 defense-in-depth: 即使未来上游对“引用字符串”的校验逻辑调整,遍历实现本身也不应变成可被利用的空窗。

#### Scenario: dangerous attribute name is rejected in class-style traversal
- **WHEN** 引用包含属性链片段命中 denylist(例如 `pkg.mod:Obj.getattr`)
- **THEN** resolver MUST fail-fast

#### Scenario: dunder attribute is rejected in traversal
- **WHEN** 引用包含 `__` 相关属性(例如 `pkg.mod:Obj.__class__`)
- **THEN** resolver MUST fail-fast
