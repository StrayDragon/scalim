## 1. 统一 LSP contract tests harness（协议级黑盒）

- [x] 1.1 抽取 LSP subprocess + JSON-RPC/LSP client：将现有 `tests/yaml_dsl/test_yaml_dsl_lsp_server_*.py` 中重复的编码/初始化/等待逻辑收敛到 `tests/support/`（注意：`tests/support/` 不得被 YAML 字符串引用）
- [x] 1.2 在 harness 中默认禁用 didChange 防抖（`SCALIM_YAML_DSL_LSP_DID_CHANGE_DEBOUNCE_MS=0`），并统一超时/失败诊断（失败时输出最近 N 条收发消息）
- [x] 1.3 实现协议输出 normalize：将 workspace 绝对路径归一化为 `<WORKSPACE>`、对 diagnostics/completions/locations 做稳定排序、过滤不稳定字段（验收：同一测试在不同机器路径下稳定通过）

## 2. 场景化 fixtures + golden snapshots（可审查基线）

- [x] 2.1 以场景为单位整理 fixtures（SSOT=仓内文件）：新增 `tests/fixtures/yaml_dsl_lsp_contract/<scenario>/...`，覆盖 imports/$import、python reference、builtin callable、outputs.fields、YAML alias、code actions 的最小覆盖矩阵
- [x] 2.2 引入 snapshots（JSON）与显式更新流程（例如 `UPDATE_GOLDEN=1`）：默认对拍，不允许隐式更新；更新时需经过 review（验收：无 env 时不改快照，有 env 时可更新快照）
- [x] 2.3 将现有 LSP integration tests 迁移为 contract suite：用 harness + snapshots 替代散点 assert（保留必要的结构化断言），并确保默认 `pytest` 运行包含该 suite（本地/CI 一致）

## 3. 验收与稳定性

- [x] 3.1 稳定性：在本地重复跑关键用例（例如 3 次）确认无 flaky；再跑 `just test`
- [x] 3.2 门禁：运行 `just qa` 与 `just openspec-check`，确认无 drift 且 change 工件校验通过
