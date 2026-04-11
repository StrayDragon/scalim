## 1. `create_temp_path` 私有临时目录策略（降低 TOCTOU）

- [ ] 1.1 在 `src/scalim/sinks/_internal/base.py` 重构 `create_temp_path(output_path, suffix)`：在 `output_dir` 下创建权限收紧的私有临时目录（例如 `.scalim-tmp-*`），并在该目录内创建唯一临时文件路径返回（保持 replace 原子性前提）
- [ ] 1.2 尽量收紧临时目录权限（best-effort，例如 `0o700`）；保持 Python 3.6 兼容与跨平台可用性

## 2. 提交/清理策略（best-effort）

- [ ] 2.1 为 temp+replace 增加一个集中 helper（或在调用点补齐）用于在 `Path(temp).replace(final)` 成功后 best-effort 清理空的私有临时目录，避免目录残留
- [ ] 2.2 覆盖代表性调用点并保持行为一致（至少包含 `src/scalim/sinks/_internal/excel.py`、`src/scalim/sinks/_internal/sink_csv.py`、`src/scalim/workflow/resources_workbook.py`、`src/scalim/workflow/resources_sheetbook.py`、`src/scalim/workflow/resources_csv.py`）

## 3. 单测（路径/唯一性/清理）

- [ ] 3.1 新增测试覆盖：`create_temp_path` 返回路径位于目标输出目录下的私有临时目录内（例如 `.../.scalim-tmp-*/...`），且可用于 `replace` 原子提交
- [ ] 3.2 覆盖并发/多次调用唯一性（不得返回相同路径）
- [ ] 3.3 覆盖清理逻辑：replace 后私有临时目录能被 best-effort 清理（不因清理失败影响主流程）

## 4. 规范同步与验收门禁

- [ ] 4.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/yaml-dsl-file-resources/spec.md` 补充 “temp-path creation MUST mitigate TOCTOU via private temp dir” 的要求
- [ ] 4.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 4.3 运行 `just quick-qa-only-py`（或 `just qa`）作为最终验收

