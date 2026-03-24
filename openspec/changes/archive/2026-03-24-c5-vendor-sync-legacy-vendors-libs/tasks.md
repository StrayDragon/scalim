## 1. vendors/libs 同步脚本（python + rsync）

- [x] 1.1 新增 `scripts/vendor_sync.py`,实现:
  - 参数 `--dest <vendors/libs>`、`--apply`（默认 dry-run）与 `--dry-run`
  - 同步落点固定为 `<dest>/scalim/`
  - 同步内容包含: `src/scalim/` + 根 `README.md`
  - 默认镜像式同步(等价 `rsync -a --delete`)并排除 `__pycache__`/`*.pyc`
  - 对明显危险 `--dest` 做硬拒绝(如 `/`)

## 2. just 快捷命令

- [x] 2.1 在根 `justfile` 新增 `sync-project-vendors <path> [YES]`：
  - 默认 dry-run
  - 仅当第二个参数为 `YES` 时才执行实际同步

## 3. 验收与门禁

- [x] 3.1 本机 dry-run: `just sync-project-vendors <path>` 输出计划变更且不写入
- [x] 3.2 本机实际同步: `just sync-project-vendors <path> YES` 后 `<path>/scalim/__init__.py` 存在
- [x] 3.3 运行 `just quick-check-only-py` 与 `just openspec-check` 确认基础门禁通过
