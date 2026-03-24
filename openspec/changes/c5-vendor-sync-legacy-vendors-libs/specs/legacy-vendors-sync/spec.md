# legacy-vendors-sync Specification

## ADDED Requirements

### Requirement: project MUST provide a just shortcut for vendor sync
系统 MUST 在仓库根 `justfile` 中提供一个快捷 recipe,用于触发 vendors 同步脚本,且目标路径由调用方显式传入,不得写入仓库版本控制。

#### Scenario: developer can run sync with an explicit dest
- **WHEN** 开发者执行 `just sync-project-vendors <vendors/libs>`
- **THEN** recipe MUST 触发同步脚本并将目标路径传入脚本（默认 dry-run）

#### Scenario: actual sync requires explicit confirm token
- **WHEN** 开发者执行 `just sync-project-vendors <vendors/libs> YES`
- **THEN** recipe MUST 执行实际同步（非 dry-run）

### Requirement: vendor sync script MUST mirror src/scalim into legacy vendors/libs/scalim
系统 MUST 提供一个同步脚本,用于将仓库的 `src/scalim/` 镜像同步到下游旧工程的 `vendors/libs/scalim/` 导入链路。

同步脚本 MUST 满足:
- 接收目标目录参数 `--dest <vendors/libs>` 并将同步落点固定为 `<dest>/scalim/`。
- 默认 MUST 以 dry-run 方式执行镜像式同步预览（等价于 `rsync -a --delete --dry-run`）。
- 当调用方显式确认执行实际同步时，脚本 MUST 执行镜像式同步（等价于 `rsync -a --delete`）。
- 脚本 MUST 提供 `--apply` 用于显式触发实际写入。
- MUST 排除非源码产物(至少包含 `__pycache__` 与 `*.pyc`)。
- MUST 提供 `--dry-run` 以预览变更。
- MUST 对明显危险的目标路径做硬拒绝(例如 `--dest /`),避免误删。

#### Scenario: mirror sync removes stale files
- **GIVEN** 目标 `<dest>/scalim/` 中存在历史残留文件
- **WHEN** 使用 `--apply` 执行同步脚本
- **THEN** 同步结果 MUST 与源 `src/scalim/` 保持一致且残留文件 MUST 被移除

#### Scenario: dry-run produces no writes
- **WHEN** 使用 `--dry-run` 执行同步脚本
- **THEN** 脚本 MUST 不写入目标目录且输出计划变更

### Requirement: vendor sync MUST include README
同步脚本 MUST 将仓库根的 `README.md` 同步到目标目录下的 `scalim/` 子目录。

#### Scenario: vendor copy includes README
- **WHEN** 执行同步脚本
- **THEN** 目标目录中的 `scalim/README.md` MUST 存在
