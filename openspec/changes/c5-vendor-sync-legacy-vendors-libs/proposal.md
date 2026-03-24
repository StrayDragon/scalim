## Why

我们有一个特别老的下游代码环境,采用 `vendors/libs/` 目录作为 PythonPath 自动导入链路.为了让该环境持续使用最新的核心逻辑,需要一个稳定、可重复的方式将本仓库的 `src/scalim/` vendors 化后同步到目标 `vendors/libs/scalim/`.

目前同步过程缺少“标准入口 + 默认安全参数”(例如镜像式同步与 `--delete`),容易出现目标目录残留脏文件、版本不一致、难以排查等问题。

## What Changes

- 新增同步脚本(实现层)使用 `python + rsync`:
  - 默认 `rsync -a --delete`,并排除 `__pycache__`/`*.pyc` 等非必要产物.
  - 默认 dry-run 预览;仅当 `--apply` 时才执行实际写入.
  - 仍提供 `--dry-run` 便于显式预览变更.
- 同步内容聚焦为三类资产:
  - `src/scalim/`（包代码）
  - `README.md`（仓库说明）
- 在根 `justfile` 提供快捷命令 `sync-project-vendors <path> [YES]`：
  - 默认 dry-run
  - 仅当第二个参数为 `YES` 时才执行实际同步

## Capabilities

### New Capabilities
- `legacy-vendors-sync`: 提供一个可审计、可重复的 vendors 化同步入口,用于将 `scalim` 核心运行时代码同步到下游旧环境的 `vendors/libs/` 导入链路.

### Modified Capabilities
<!-- 本变更不修改现有规范的 REQUIREMENTS,仅新增能力与实现/工程化支持. -->

## Impact

- 受影响模块:
  - 根 `justfile`（新增 `sync-project-vendors` recipe）
  - 新增同步脚本 `scripts/vendor_sync.py`
- 下游影响:
  - 下游旧环境可通过同步后直接 `import scalim` 使用核心逻辑。
- 依赖与约束:
  - 同步脚本依赖本机存在 `rsync`.
