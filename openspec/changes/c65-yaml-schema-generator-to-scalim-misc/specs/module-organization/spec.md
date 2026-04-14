# module-organization (delta) Specification

## ADDED Requirements

### Requirement: runtime core MUST NOT import dev tooling packages

系统 MUST 保持依赖方向单向且可审计：

- runtime core（`src/IMPL_ROOT/**`）MUST NOT 导入 dev tooling packages（例如 `packages/scalim-misc`）
- dev tooling packages MAY 导入 `IMPL_ROOT` 并消费其 SSOT/公共入口

说明：禁止通过 optional hook / `importlib.import_module` 等动态导入方式绕开该限制。

#### Scenario: importing IMPL_ROOT does not require scalim-misc
- **GIVEN** 环境中未安装 `scalim-misc`
- **WHEN** 用户仅导入并使用 runtime core（compile/validate/run/workflow）
- **THEN** 导入与运行 MUST 成功

