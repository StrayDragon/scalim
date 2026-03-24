# legacy-vendors-sync Specification

**状态: ✅ 已实现**
## Purpose
为下游采用 `vendors/libs/` 导入链路的旧工程提供一个可审计、可重复的同步入口,用于将本仓库的 `src/scalim/` vendors 化后镜像到目标 `<vendors/libs>/scalim/`。默认仅预览(dry-run),并在显式确认时执行实际同步。
## Related Code (as implemented)
- `scripts/vendor_sync.py`（同步脚本: `python + rsync`）
- `justfile`（`sync-project-vendors` recipe）
## Requirements
### Requirement: 提供 vendors 同步的 `just` 快捷入口
系统 MUST 在仓库根 `justfile` 中提供一个快捷 recipe,用于触发 vendors 同步脚本;目标路径 MUST 由调用方显式传入,不得写入仓库版本控制。

#### Scenario: 默认 dry-run 预览
- **WHEN** 开发者执行 `just sync-project-vendors <vendors/libs>`
- **THEN** recipe MUST 触发同步脚本并将目标路径传入脚本（默认 `dry-run` 预览）

#### Scenario: 实际同步需要显式确认 token
- **WHEN** 开发者执行 `just sync-project-vendors <vendors/libs> YES`
- **THEN** recipe MUST 执行实际同步（非 dry-run）

### Requirement: 同步脚本镜像 `src/scalim` 到 `<dest>/scalim`
系统 MUST 提供一个同步脚本,用于将仓库的 `src/scalim/` 镜像同步到下游旧工程的 `vendors/libs/scalim/` 导入链路。

同步脚本 MUST 满足:
- 接收目标目录参数 `--dest <vendors/libs>` 并将同步落点固定为 `<dest>/scalim/`。
- 默认 MUST 以 dry-run 方式执行镜像式同步预览（等价于 `rsync -a --delete --dry-run`）。
- 当调用方显式确认执行实际同步时,脚本 MUST 执行镜像式同步（等价于 `rsync -a --delete`）。
- MUST 提供 `--apply` 用于显式触发实际写入。
- MUST 排除非源码产物(至少包含 `__pycache__` 与 `*.pyc`)。
- MUST 提供 `--dry-run` 以预览变更。
- MUST 对明显危险的目标路径做硬拒绝(例如 `--dest /`),避免误删。

#### Scenario: 镜像同步会移除残留文件
- **GIVEN** 目标 `<dest>/scalim/` 中存在历史残留文件
- **WHEN** 使用 `--apply` 执行同步脚本
- **THEN** 同步结果 MUST 与源 `src/scalim/` 保持一致且残留文件 MUST 被移除

#### Scenario: dry-run 不产生写入
- **WHEN** 使用 `--dry-run` 执行同步脚本
- **THEN** 脚本 MUST 不写入目标目录且输出计划变更

### Requirement: vendors 同步包含 `README.md`
同步脚本 MUST 将仓库根的 `README.md` 同步到目标目录下的 `scalim/` 子目录。

#### Scenario: 目标包含 README
- **WHEN** 执行同步脚本
- **THEN** 目标目录中的 `scalim/README.md` MUST 存在
