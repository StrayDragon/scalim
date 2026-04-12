# yaml-dsl-file-resources Specification

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
- `path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2），而不是最终文件路径
- 相对路径 MUST 以声明该资源的 YAML 文件所在目录为基准解析
- 系统 MUST 基于 `file_id` 与 `version_id` 推导最终输出路径：
  - final path MUST 等价于 `<root>/versions/<version_id>/files/<file_id>.csv`
- legacy `write_lock` 配置面 MUST 被移除；若用户仍提供该字段，系统 MUST fail-fast 并给出迁移提示

其中 `version_id` 取值约束：

- standalone demand: `version_id` MUST 等于该 demand 的 `run_id`
- workflow: `version_id` MUST 等于该 workflow 的 `workflow_exec_id`

#### Scenario: file resource passes schema validation
- **WHEN** demand YAML 声明 `resources.files.detail.kind=csv_file`
- **AND** `resources.files.detail.path=./out`
- **THEN** schema-only 校验 MUST 通过

## REMOVED Requirements

### Requirement: csv_file write_lock MUST prevent concurrent writers to the same output path

**Reason**：版本化输出（D-2）将并发写入从“共享最终路径”改为“版本目录天然隔离”，不再需要基于 `<final_path>.scalim.lock` 的跨进程互斥；继续生成 lockfile 会造成用户目录污染并放大服务端并发冲突。

**Migration**：

- 将 `resources.files.<id>.path` 配置为输出 root 目录（而非最终文件路径）。
- 删除 `resources.files.<id>.write_lock` 配置。
- 通过 `<root>/manifest/latest.json` 或指定 `<root>/versions/<version_id>/...` 读取产物。

#### Scenario: legacy write_lock configuration is rejected with an actionable migration hint
- **GIVEN** 用户仍在 YAML 中提供 `resources.files.detail.write_lock=true`
- **WHEN** 系统执行 validate/compile
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 提示 `write_lock` 已移除并指向“版本化输出 + manifest/latest.json”的迁移路径

