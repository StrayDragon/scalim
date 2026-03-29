## ADDED Requirements

### Requirement: public API suite MUST stay consistent with the public API manifest

系统 MUST 将 public API suite 与 public API manifest 视为同一份“稳定公开面 SSOT”的两个投影：
- manifest 表达“允许的公开入口与导出面”
- suite 通过可运行示例与 `__all__` 覆盖断言表达“可用且可回归”

两者 MUST 保持一致：
- suite 覆盖的稳定公开入口集合 MUST 与 manifest 对齐
- suite 中的导入示例 MUST 仅使用 manifest 的 curated entrypoints

#### Scenario: manifest/suite drift is rejected
- **WHEN** suite 覆盖集合与 manifest 不一致（缺失/新增模块或导出）
- **THEN** gate MUST fail-fast 并指出差异

