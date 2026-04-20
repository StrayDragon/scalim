# yaml-dsl-workflow-validate Specification

## Purpose
提供面向 CI/预发布的 workflow-level validate CLI 入口，在不执行 workflow 的前提下对 workflow YAML 及其引用的 demands 做静态/编译期校验。

## Related Concepts
- workflow validate CLI
- 递归 demand 校验
- workflow ↔ demand 交叉一致性
- resources.books/files 绑定
- YAML load/error envelope 共享
## Requirements
### Requirement: CLI MUST provide workflow-level validate that recursively validates referenced demands
系统 MUST 提供一个面向 CI/预发布的 workflow-level validate CLI 入口，用于在不执行 workflow 的前提下，对 workflow YAML 及其引用的 demands 做静态/编译期校验。

该入口 MUST 支持形如：

- `yaml-dsl validate --type workflow <workflow.yaml>`

校验范围 MUST 至少包含：

- workflow YAML 自身结构与语义校验（解析、引用合法性、cycle detection 等）
- 递归校验每个 `runs[*].demand` 引用的 demand YAML（允许 imports/$import，并在错误中提供可诊断的引用链路）
- workflow ↔ demand 的交叉一致性校验（例如 demand outputs 绑定到的资源 id 必须能解析到某个有效的资源 mapping）:
  - `to.book` ↔ `resources.books`
  - `to.file` ↔ `resources.files`
- 对旧 `outputs[*].container` 给出迁移诊断

#### Scenario: validate fails when a demand binds to an unknown book id
- **GIVEN** workflow YAML 中某个 `runs[*].demand` 引用的 demand YAML 声明 `outputs[0].to.book: "report"`
- **AND** 该 demand YAML 与 workflow YAML 均未声明 `resources.books.report` / `workflow.resources.books.report`
- **WHEN** 调用方执行 workflow validate CLI
- **THEN** 校验 MUST 失败（非零退出码）
- **AND** 输出 MUST 提供可定位的诊断信息，指出缺失的 book id 与来源路径(例如 `outputs[0].to.book`)

#### Scenario: validate fails when a demand binds to an unknown file id
- **GIVEN** workflow YAML 中某个 `runs[*].demand` 引用的 demand YAML 声明 `outputs[0].to.file: \"detail_csv\"`
- **AND** 该 demand YAML 与 workflow YAML 均未声明 `resources.files.detail_csv` / `workflow.resources.files.detail_csv`
- **WHEN** 调用方执行 workflow validate CLI
- **THEN** 校验 MUST 失败（非零退出码）
- **AND** 输出 MUST 提供可定位的诊断信息，指出缺失的 file id 与来源路径(例如 `outputs[0].to.file`)

#### Scenario: validate fails when a demand still uses container
- **GIVEN** workflow YAML 中某个 `runs[*].demand` 引用的 demand YAML 仍声明 `outputs[0].container`
- **WHEN** 调用方执行 workflow validate CLI
- **THEN** 校验 MUST 失败（非零退出码）
- **AND** 输出 MUST 提示迁移到 `resources.files/resources.books` + `to/write`

### Requirement: workflow validate MUST share YAML load and error envelope with demand compile

系统 MUST 要求 workflow validate 与 demand compile/run 在以下方面保持一致：
- YAML load（包括 duplicate key 检测）
- imports fragments 的处理（若 workflow 支持）
- location index 与 ErrorEnvelope 结构

#### Scenario: same YAML yields the same failure in workflow validate and compile
- **GIVEN** 某份 workflow YAML 包含 duplicate keys 或语法错误
- **WHEN** 维护者分别运行 workflow validate 与相同 loader 入口
- **THEN** 两者 MUST 产生一致的错误结构与定位口径
