## ADDED Requirements

### Requirement: demand JSON Schema MUST encode `lookup_cast` as a one-of cast-branch object
系统 MUST 在生成的 demand JSON Schema 中将 `lookup_cast` 表达为 one-of 分支对象,以实现 authoring 阶段 fail-fast:

- `lookup_cast` MUST 为 object
- `lookup_cast` MUST 通过 `oneOf` 限定为以下四种之一（且只能选其一）:
  - `{auto: {}}`
  - `{int: {}}`
  - `{str: {}}`
  - `{sep_first: {sep?: <string>}}`
- `auto/int/str` 分支的 value object MUST NOT 接受任何额外字段
- `sep_first` 分支的 value object MUST 仅允许可选字段 `sep`(string),且 MUST NOT 接受任何额外字段
- schema MUST NOT 再接受 legacy 形态 `lookup_cast: {name: ...}`

#### Scenario: schema rejects legacy lookup_cast shape with `name`
- **GIVEN** 用户编写 `lookup_cast: {name: int}`
- **WHEN** 编辑器或 schema-only 校验使用 demand JSON Schema 校验该 YAML
- **THEN** 校验 MUST 失败并指出 `lookup_cast` 结构不匹配

#### Scenario: schema rejects `sep` under non-sep_first branches
- **GIVEN** 用户编写 `lookup_cast: {int: {sep: ","}}`
- **WHEN** 编辑器或 schema-only 校验使用 demand JSON Schema 校验该 YAML
- **THEN** 校验 MUST 失败并指出 `lookup_cast.int` 不允许字段 `sep`

#### Scenario: schema rejects multiple lookup_cast branches
- **GIVEN** 用户编写 `lookup_cast: {int: {}, sep_first: {sep: ","}}`
- **WHEN** 编辑器或 schema-only 校验使用 demand JSON Schema 校验该 YAML
- **THEN** 校验 MUST 失败并指出 `lookup_cast` 必须且只能选择一个分支
