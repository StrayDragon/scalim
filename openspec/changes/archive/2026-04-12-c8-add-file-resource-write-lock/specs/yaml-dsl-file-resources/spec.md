# yaml-dsl-file-resources (delta) Specification

## MODIFIED Requirements

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

## ADDED Requirements

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
