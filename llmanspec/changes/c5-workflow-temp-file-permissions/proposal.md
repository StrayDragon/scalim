# Proposal: workflow-temp-file-permissions

## 与 c20/c30 关系

- **不被取代**。本 change 加固 publish 临时文件权限（`resources_base` staging），与 c20 policy 边界正交；与 c30 内存释放可并行，注意同一文件合并冲突即可。
- 相关归档：`llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/`、`.../2026-07-12-c30-workflow-shared-book-memory/`。

## Why

`src/scalim/workflow/resources_base.py:172-177` 中 workflow publish 路径的临时文件使用 `tempfile.mkstemp` 创建，默认权限为系统默认（通常 `0o644`），在共享输出目录场景下存在 symlink/race 风险。

对比 `sinks/_internal/base.py:55-60`，后者使用 `0o700` 私有子目录 + `mkstemp` 的安全模式。两处应统一。

## What Changes

1. **统一临时文件策略**: `_create_publish_temp_path` 改为在私有 `0o700` 子目录下创建临时文件（与 sinks 的 `create_temp_path` 对齐）
2. **复用 `sinks/_internal/base.py` 中的 `create_temp_path`**（或提取到 `_internal/utils/`）
3. **清理临时目录**: 发布完成后清理私有子目录

## Capabilities

### Modified Capabilities

- `workflow-managed-temp-outputs` — 临时文件安全加固

## Impact

- **代码区域**: `src/scalim/workflow/resources_base.py`
- **破坏性**: 无（内部实现变更，输出路径不变）
- **安全**: 临时文件权限从系统默认收紧到 `0o700`
