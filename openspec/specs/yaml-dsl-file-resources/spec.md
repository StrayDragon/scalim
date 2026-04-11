# yaml-dsl-file-resources Specification

**状态: ✅ 已实现**
## Purpose
定义 demand/workflow 统一的 `resources.files` 文件输出资源入口,并约束 CSV 输出通过 `outputs[*].to.file` + `outputs[*].write` 绑定,取代 legacy `outputs[*].container`.

## Requirements
### Requirement: demand and workflow YAML MUST support `resources.files` as the unified file-output resource surface
系统 MUST 提供 `resources.files` 作为非 book 文件输出的统一资源入口,并在 demand/workflow 两类 YAML 中保持一致:

- demand: `resources.files.<file_id>`
- workflow: `workflow.resources.files.<file_id>`

约束:

- `<file_id>` MUST 为非空字符串且在同一 mapping 内唯一
- `resources.files.<file_id>` MUST 为 mapping
- v1 仅允许 `kind=csv_file`
- `path` MUST 为非空字符串或 `{$init_var: <name>}`
- `encoding` MAY 存在,默认 `utf-8`
- `write_lock` MUST 为 bool(默认 `false`)
- 相对路径 MUST 以声明该资源的 YAML 文件所在目录为基准解析

#### Scenario: file resource passes schema validation
- **WHEN** demand YAML 声明 `resources.files.detail.kind=csv_file`
- **AND** `resources.files.detail.path=./out/detail.csv`
- **AND** `resources.files.detail.write_lock=true`
- **THEN** schema-only 校验 MUST 通过

### Requirement: csv_file write_lock MUST prevent concurrent writers to the same output path

当 `resources.files.<id>.write_lock=true` 时,系统 MUST 在最终文件写入边界对目标输出路径执行跨进程互斥:

- 锁文件路径 MUST 为 `<final_path>.scalim.lock`
- 当检测到并发 writer 时,系统 MUST fail-fast 并抛出可诊断的写入异常
- 异常信息 MUST 包含 `lock_path` 以及可用的 lock owner 信息(例如 `workflow_exec_id`)

#### Scenario: concurrent workflow publish with write_lock fails fast
- **GIVEN** 两个独立 workflow 进程将 CSV 输出发布到同一 `final_path`
- **AND** 该 CSV file resource 启用了 `write_lock=true`
- **WHEN** 两个 workflow 在 publish(staged → final) 阶段并发尝试写入该 `final_path`
- **THEN** 系统 MUST 允许其中一个 workflow 完成 publish
- **AND** 系统 MUST 使另一个 workflow fail-fast 并抛出写入异常

#### Scenario: concurrent standalone writes with write_lock fails fast
- **GIVEN** 两个独立运行(standalone demand)将 CSV 输出写入到同一 `final_path`
- **AND** 该 CSV file resource 启用了 `write_lock=true`
- **WHEN** 两个运行在 sink close 的原子 replace 边界并发尝试写入该 `final_path`
- **THEN** 系统 MUST 允许其中一个运行完成写入
- **AND** 系统 MUST 使另一个运行 fail-fast 并抛出写入异常

### Requirement: temp-path creation for atomic file writes MUST mitigate TOCTOU in untrusted output directories

当系统需要为文件输出执行 “temp+replace” 原子写入时(例如 CSV/Excel 文件落盘),系统 MUST 降低在不可信输出目录中的 TOCTOU(time-of-check to time-of-use) 可利用性:

- 系统 MUST 将临时文件放置在目标输出目录下的“私有临时目录”中(同文件系统/同父目录层级,保证后续 replace 原子性)
- 私有临时目录 MUST 尽可能收紧权限,使其他用户/进程无法进入该目录替换临时文件条目(例如仅当前用户可访问)
- 系统 MUST 允许第三方库按 path 写入临时文件(不强制要求 fd 写入),并在写入完成后以原子方式 replace 到最终输出路径
- 系统 SHOULD 在 replace 后对私有临时目录进行 best-effort 清理,避免长期残留

#### Scenario: temp path resides in a private directory under output_dir
- **GIVEN** 输出路径为 `/out/report.csv`
- **WHEN** 系统为该输出创建临时路径
- **THEN** 临时路径 MUST 位于 `/out/` 下的私有临时目录内(例如 `/out/.scalim-tmp-*/...`)
- **AND** 其他用户/进程 MUST 不应能够进入该私有目录以替换临时文件条目

#### Scenario: replace remains atomic and final path is unchanged
- **GIVEN** 系统采用私有临时目录策略
- **WHEN** 临时文件写入完成并提交到最终输出路径
- **THEN** 系统 MUST 以原子 replace 的方式生成最终文件
- **AND** 最终输出路径与文件名 MUST 保持不变

### Requirement: CSV outputs MUST bind via `outputs[*].to.file` and `outputs[*].write`
系统 MUST 要求 CSV 输出通过统一 target model 绑定:

- `outputs[*].to.file` MUST 为非空字符串
- `outputs[*].write.include_header` MAY 存在,默认 `true`
- `outputs[*].write.header_fields_output_by` MAY 存在,默认 `name`
- CSV 输出 MUST NOT 再使用 `outputs[*].container`

#### Scenario: csv output binds through to.file
- **WHEN** output 声明 `to.file=detail_csv`
- **AND** `resources.files.detail_csv.kind=csv_file`
- **THEN** 该 output MUST 绑定到对应文件资源

### Requirement: standalone demand MUST fail-fast when a referenced file resource is missing
系统 MUST 在 standalone `compile/run` 中校验所有 `outputs[*].to.file` 的资源存在性:

- 若 `to.file` 引用的 `resources.files.<id>` 缺失,系统 MUST fail-fast
- 错误信息 MUST 包含缺失的 `file_id`
- 错误信息 MUST 指向 `outputs[*].to.file`
- 错误信息 MUST 提示在 YAML 或 overrides.resources.files 中补齐资源

#### Scenario: missing file resource fails fast
- **GIVEN** output 声明 `to.file: detail_csv`
- **AND** YAML 与 overrides 中均不存在 `resources.files.detail_csv`
- **WHEN** 调用方执行 standalone compile/run
- **THEN** 系统 MUST fail-fast

### Requirement: workflow MUST merge `resources.files` with the same precedence model as books
系统 MUST 对 `files` 资源采用与 `books` 相同的 merge precedence:

1. demand YAML 的 `resources.files`
2. workflow YAML 的 `workflow.resources.files`
3. Python overrides 的 `overrides.resources.files`

#### Scenario: workflow overrides demand file path
- **GIVEN** demand 声明 `resources.files.detail.path=./out/a.csv`
- **AND** workflow 声明 `workflow.resources.files.detail.path=./out/b.csv`
- **WHEN** workflow 运行该 demand
- **THEN** effective file path MUST 等于 workflow 声明值
