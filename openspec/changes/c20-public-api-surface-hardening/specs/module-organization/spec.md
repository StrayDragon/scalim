## ADDED Requirements

### Requirement: internal implementation paths MUST remain non-contract

系统 MUST 将“可导入”与“可承诺”为两个不同层级：

- 稳定公开入口由显式白名单定义
- 其余实现路径即使暂时可导入,也 MUST 视为内部实现细节

系统 MUST 不允许测试、示例、skills 或文档把内部实现路径反向固化为事实上的公共 API。

#### Scenario: implementation paths are not promoted to public contract
- **WHEN** 某个内部实现模块仍然可以被 import
- **THEN** 系统 MUST NOT 因此自动将其视为稳定公开入口
- **AND** 面向用户的回归门禁 MUST 仍以显式公共白名单为准

### Requirement: curated facade modules MUST use explicit export whitelists

系统 MUST 要求被认定为稳定公开入口的 facade 模块使用显式 `__all__` 或等价白名单控制导出面，避免内部符号随着重构被无意带出。

#### Scenario: facade export growth is deliberate
- **WHEN** 维护者调整某个稳定 facade 模块中的导出符号
- **THEN** 变更 MUST 通过显式白名单体现
- **AND** 公共表面 gate MUST 能对新增或删除导出做出确定性回归提示
