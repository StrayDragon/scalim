## 1. Multi-location Resolution

- [ ] 1.1 统一 core “定位”API 返回 `List[Location]`，并提供稳定排序 + 去重 helper（P0/P1/P2）
- [ ] 1.2 server handlers 全量透传多 locations（definition 等），并保持排序稳定（便于用户选择候选）
- [ ] 1.3 单元测试覆盖：多候选、去重、排序（按 uri → 行号稳定）

## 2. Cache / In-flight Dedup

- [ ] 2.1 增加 `(path, mtime_ns)` 缓存：file_text / ast_tree / yaml_data（LRU，上限可配置）
- [ ] 2.2 打开文档优先使用 LSP 内存态文本（不依赖 mtime）
- [ ] 2.3 并发请求对同一路径做 in-flight 去重（lock/task），避免重复 IO
- [ ] 2.4 测试覆盖：mtime 变化失效；并发 dedupe 不重复读/解析

## 3. Resolution Trace（结构化 trace）

- [ ] 3.1 定义 `ResolutionTrace` 数据结构，并贯穿 core（success/failure 都可解释）
- [ ] 3.2 server 侧可选择性暴露 trace（log/hover/diagnostics），不泄露 YAML 正文

## 4. Quick Fix 框架

- [ ] 4.1 建立“诊断 code → codeAction provider”的 SSOT 注册框架
- [ ] 4.2 为 1–2 个高频诊断接入 Quick Fix（供后续变更复用）

## 5. Validation

- [ ] 5.1 运行 `just openspec-check`
- [ ] 5.2 运行 `just qa`
- [ ] 5.3 运行 LSP notebooks regression（`tests/yaml_dsl/test_yaml_dsl_lsp_notebooks_regression.py`）
