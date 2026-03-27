## ADDED Requirements

### Requirement: `__all__` MUST NOT export internal underscore symbols

系统 MUST 将任何模块 `__all__` 中包含非 dunder 的 `_...` 名称视为内部符号泄漏，并要求在治理变更中将其从 `__all__` 移除。

#### Scenario: underscore symbols are rejected from __all__
- **WHEN** 回归门禁扫描 `src/scalim/**.py` 中的 `__all__`
- **THEN** 任一 `__all__` MUST NOT 包含以 `_` 开头且非 dunder 的名称
- **AND** 若发现该类条目，门禁 MUST fail-fast 并输出可定位的模块路径与符号名集合

### Requirement: internal implementation modules MUST explicitly seal exports

系统 MUST 要求内部实现模块显式声明其导出面，以避免 `from <module> import *` 意外将内部符号扩散为事实公共 API。

最小治理要求：
- 位于任意 `_internal/` 目录下的模块 MUST 定义 `__all__`，且其 MUST 为空。
- 文件名以 `_` 前缀标识为内部实现的模块 MUST 定义 `__all__`，且其 MUST 为空。

#### Scenario: internal modules declare empty __all__
- **WHEN** 回归门禁扫描 `_internal/` 目录与 `_*.py` 模块
- **THEN** 每个模块 MUST 定义 `__all__`
- **AND** 其 `__all__` MUST 为空（`[]` 或 `()`）

