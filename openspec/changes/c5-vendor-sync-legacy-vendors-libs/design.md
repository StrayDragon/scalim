## Context

下游旧工程采用 `vendors/libs/` 作为 PythonPath 自动导入链路,并通过 `import scalim` 直接使用本仓库核心逻辑.该工程路径本身属于敏感信息,不应进入仓库.

我们需要一个:
- 对仓库 **零泄露敏感路径** 的同步入口（目标路径由调用方显式传入,不写入仓库）;
- 能将 `src/scalim/` 稳定镜像到下游 `vendors/libs/scalim/`;
- 默认镜像语义包含 `--delete`,避免残留脏文件导致“幽灵 bug”.

## Goals / Non-Goals

**Goals:**
- 在仓库根 `justfile` 增加一个快捷 recipe `sync-project-vendors <path> [YES]`,由调用方显式传入目标路径（默认 dry-run; 需要 YES 才执行）.
- 提供 `python + rsync` 的同步脚本,默认镜像式同步 `src/scalim/` 到指定 `<dest>/scalim/`,并支持 `--dry-run`.
- 同步时额外携带仓库根的 `README.md`,用于下游审阅/排查.

**Non-Goals:**
- 不支持远端/SSH 同步(仅本机路径).
- 不引入新的公开 CLI 命令(仅 dev/just recipe + 脚本).
- 不在本变更中处理第三方依赖的 vendoring/shim（后续若需要再单独推进）。

## Decisions

1. **目标路径通过 `just` 参数传入,不落仓库**
   - 方案: 根 `justfile` 提供 `sync-project-vendors <path> [YES]`，由调用方显式传入目标路径。
   - 理由: 避免把敏感路径写入仓库；同时保持命令可发现、可审计、可复用。

2. **同步实现使用 `python` 驱动 `rsync`,默认 `-a --delete`**
   - 方案: 新增 `scripts/vendor_sync.py`,接收 `--dest <vendors/libs>`,实际同步到 `${dest}/scalim/`.
   - 脚本默认只做 dry-run 预览;仅当显式 `--apply` 时才执行实际写入.
   - 默认 `rsync -a --delete` 镜像目录,并排除 `__pycache__`/`*.pyc`.
   - 同步提供 `--dry-run` 以便预览.
   - 理由:
     - rsync 的镜像语义 + `--delete` 能减少“脏文件残留导致的幽灵 bug”.
     - 删除范围限定在 `${dest}/scalim/` 子目录,降低误删风险.

## Risks / Trade-offs

- [风险] `rsync --delete` 误用导致删除目标目录内容 → [缓解] 删除范围限定为 `${dest}/scalim/`;脚本对明显危险的 `--dest`(如根目录)做硬拒绝;先推荐 `--dry-run`.
