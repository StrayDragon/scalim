## MODIFIED Requirements

### Requirement: CLI MUST provide workflow-level validate that recursively validates referenced demands
系统 MUST 提供 workflow-level validate,并在统一输出 target model 下递归校验 workflow 与其引用的 demands。

校验范围 MUST 至少包含:

- workflow YAML 自身结构与语义校验
- 递归校验每个 `runs[*].demand` 的统一输出绑定:
  - `to.book` ↔ `resources.books`
  - `to.file` ↔ `resources.files`
- 对旧 `outputs[*].container` 给出迁移诊断

#### Scenario: validate fails when a demand binds to an unknown file id
- **GIVEN** 某 demand 声明 `outputs[0].to.file: "detail_csv"`
- **AND** 该 demand 与 workflow 均未声明 `resources.files.detail_csv`
- **WHEN** 调用方执行 workflow validate
- **THEN** 校验 MUST 失败
- **AND** 输出 MUST 指出缺失的 file id 与来源路径

#### Scenario: validate fails when a demand still uses container
- **GIVEN** 某 demand 仍声明 `outputs[0].container`
- **WHEN** 调用方执行 workflow validate
- **THEN** 校验 MUST 失败
- **AND** 输出 MUST 提示迁移到 `resources.files/resources.books` + `to/write`
