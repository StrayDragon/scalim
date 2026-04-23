# yaml-dsl-cli-validation (delta)

## ADDED Requirements

### Requirement: demand `schema validate` MUST support `--workflow` context for outputs→resources binding checks

系统 MUST 允许用户在对 **demand YAML** 执行 `yaml-dsl schema validate` 时提供 workflow 上下文参数：

- `yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>`

当提供 `--workflow` 时，系统 MUST：

- 读取并解析 `<workflow.yaml>`，并提取可见资源 id 集合：
  - visible books = demand `resources.books` ∪ workflow `workflow.resources.books`
  - visible files = demand `resources.files` ∪ workflow `workflow.resources.files`
- 在 schema-only 校验的 outputs 绑定检查阶段，对每个 output 的 destination 执行资源存在性校验：
  - 若 output 绑定到 `to.book=<book_id>`：`<book_id>` MUST 存在于 visible books
  - 若 output 绑定到 `to.file=<file_id>`：`<file_id>` MUST 存在于 visible files
- 当 `<workflow.yaml>` 无法读取/解析时，schema validate MUST fail-fast（不得静默忽略 workflow 上下文）。

#### Scenario: schema validate accepts a workflow-declared book id
- **GIVEN** workflow YAML 声明 `workflow.resources.books.report`
- **AND** demand YAML 声明 `outputs[0].to.book: report`
- **AND** demand YAML 未声明 `resources.books.report`
- **WHEN** 调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`
- **THEN** 校验 MUST 通过（退出码为 0）

#### Scenario: schema validate accepts a workflow-declared file id
- **GIVEN** workflow YAML 声明 `workflow.resources.files.detail_csv`
- **AND** demand YAML 声明 `outputs[0].to.file: detail_csv`
- **AND** demand YAML 未声明 `resources.files.detail_csv`
- **WHEN** 调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`
- **THEN** 校验 MUST 通过（退出码为 0）

#### Scenario: schema validate fails fast when workflow context cannot be loaded
- **GIVEN** 用户提供不存在的 `--workflow missing.yaml`
- **WHEN** 调用方执行 `yaml-dsl schema validate --workflow missing.yaml demand.yaml`
- **THEN** 命令 MUST fail-fast（非零退出码）

#### Scenario: schema validate still rejects unknown ids even with workflow context
- **GIVEN** workflow YAML 未声明 `workflow.resources.books.report`
- **AND** demand YAML 未声明 `resources.books.report`
- **AND** demand YAML 声明 `outputs[0].to.book: report`
- **WHEN** 调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`
- **THEN** 命令 MUST fail-fast（非零退出码）
- **AND** 错误 MUST 指向 `outputs[0].to.book`

### Requirement: demand `validate` MUST support the same `--workflow` context behavior as `schema validate`

系统 MUST 允许用户在对 **demand YAML** 执行 `yaml-dsl validate` 时提供 workflow 上下文参数：

- `yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>`

并且该上下文的资源可见性语义 MUST 与 `schema validate` 一致（同一份输入在同一 workflow 上下文下，两者对 outputs→resources 绑定的接受/拒绝结果 MUST 一致）。

#### Scenario: validate accepts a workflow-declared resource id
- **GIVEN** workflow YAML 声明 `workflow.resources.books.report`
- **AND** demand YAML 声明 `outputs[0].to.book: report`
- **AND** demand YAML 未声明 `resources.books.report`
- **WHEN** 调用方执行 `yaml-dsl validate --workflow workflow.yaml demand.yaml`
- **THEN** 校验 MUST 通过（退出码为 0）

#### Scenario: validate accepts a workflow-declared file id
- **GIVEN** workflow YAML 声明 `workflow.resources.files.detail_csv`
- **AND** demand YAML 声明 `outputs[0].to.file: detail_csv`
- **AND** demand YAML 未声明 `resources.files.detail_csv`
- **WHEN** 调用方执行 `yaml-dsl validate --workflow workflow.yaml demand.yaml`
- **THEN** 校验 MUST 通过（退出码为 0）
