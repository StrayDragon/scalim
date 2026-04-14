## 1. Cursor Extraction

- [x] 1.1 在 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cursor_extraction.py` 增加 `workflow.runs[*].demand` 的光标抽取（单行 scalar + range 计算）。
- [x] 1.2 为 `demand:` 为空值且光标位于冒号后空白的场景添加保守 fallback（参考 `imports.*` 的 line-based fallback 行为）。

## 2. Definition Handler

- [x] 2.1 在 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py` 增加 workflow demand 的 definition handler，并接入 definition handler 链。
- [x] 2.2 复用 `scalim.dsl.yaml_dsl.workflow_config.resolve_workflow_demand_path` 解析 demand path：
  - 相对路径基于 workflow YAML 所在目录；
  - `allowed_yaml_roots` 使用 editor discovery；
  - `path_aliases` 默认使用 `scalim.yaml` 的 `yaml_dsl.import_roots[].alias`（若可用）。
- [x] 2.3 完善失败降级与可诊断日志（解析失败/越界/未知 alias 返回空结果，不得 crash）。

## 3. Verification

- [x] 3.1 增加最小测试覆盖（优先单元测试 cursor extraction + path resolve 的核心分支；若 repo 现有测试框架不覆盖该包，则添加同层 pytest 测试并在 CI/`just qa` 可运行）。
- [x] 3.2 运行 `just openspec-check` 验证 OpenSpec 工件；运行 `just qa` 作为质量门禁（lint/tests + drift checks）。
