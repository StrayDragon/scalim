## 1. Project Config + Schema (Python 3.6 boundary)

- [ ] 1.1 扩展 `src/scalim/dsl/yaml_dsl/_internal/config_parsing/project_config.py`：新增 `yaml_dsl.lsp.reference_sync` 解析与 fail-fast 校验（未知 key / 类型错误直接报错）
- [ ] 1.2 扩展 schema SSOT `src/scalim/dsl/yaml_dsl/schema_dsl/models/scalim_yaml.py`：为 `yaml_dsl.lsp.reference_sync.*` 增加 JSON Schema 定义（类型/约束/默认值）
- [ ] 1.3 刷新生成物 `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json`（生成入口：`just gen-yaml-dsl-schema`；禁止手工编辑）
- [ ] 1.4 运行 drift/gate：`just schema-drift-check` + `just py36-compat-check`（确保 SSOT→生成物一致，且不破坏 Python 3.6 兼容）

## 2. LSP Reference Sync Core (packages/scalim-yaml-dsl-lsp)

- [ ] 2.1 新增 YAML 引用扫描器（模块/文件名待定）：抽取 `loader` / `call_by` head / `retry.should_retry` 的 Python 引用（支持 block scalar），并输出结构化引用列表
- [ ] 2.2 新增引用索引管理器：读写 `.scalim/index/refs.gen.json`（版本化 + mtime 增量 + 原子写入 + 并发锁 + JSONDecodeError 降级为空索引）
- [ ] 2.3 新增 stubs/markers 生成器：根据索引生成 `.scalim/stubs/**.pyi`（稳定排序，包含 `# pragma: scalim-yaml-ref` 与 YAML 引用明细注释）
- [ ] 2.4 新增一致性检查器：对索引内 `symbol_key` 做静态解析（复用 `resolve_python_definition()`）并产出不一致项列表（含 reason）
- [ ] 2.5 在 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py` 集成引用同步的调度（复用 `_DID_CHANGE_DEBOUNCE_SECS` + task cancel + semaphore 节流；不得阻塞事件循环）
- [ ] 2.6 新增 LSP executeCommand：
  - `scalim.dumpYamlPythonReferences`（按 document URI 返回 refs + python_locations）
  - `scalim.checkYamlPythonConsistency`（返回不一致项列表）
- [ ] 2.7 Diagnostics 集成：当 `reference_sync.enabled=true` 且 `show_inconsistency_diagnostics=true` 时，将 broken refs 追加进 YAML diagnostics（稳定 code，例如 `broken-yaml-python-ref`）

## 3. CLI Integration (packages/scalim-cli)

- [ ] 3.1 新增子命令组：`scalim-cli yaml-dsl ref-sync`（argparse wiring）
- [ ] 3.2 实现 `ref-sync generate`：扫描目标路径集合 → 写入索引 → 生成 stubs（幂等输出）
- [ ] 3.3 实现 `ref-sync check-consistency`：输出 linter 风格摘要；`--json` 输出结构化 payload；存在不一致项时返回非 0
- [ ] 3.4 （可选 MVP）实现 `ref-sync fix-consistency --interactive`：逐项确认后写回 YAML（未确认不得改写）

## 4. Tooling / Docs / QA

- [ ] 4.1 更新 `.gitignore`：忽略 `.scalim/`（引用索引与 stubs/diagnostics）
- [ ] 4.2 评估并落地本地 QA 稳定性策略：确保生成的 `.scalim/` 不会导致 `just qa`（ruff check .）不稳定（例如加入 ruff exclude 或保证生成物 ruff-clean）
- [ ] 4.3 为扫描器/索引/一致性检查新增最小单测（pytest；覆盖 call_by head、多行 block scalar、增量更新回收旧引用）
- [ ] 4.4 更新 docs 或 fixtures：给出 `scalim.yaml yaml_dsl.lsp.reference_sync` 示例与排障指引（若涉及注入块，按 doc-governance 走 `just gen-docs`）
- [ ] 4.5 运行质量门禁：`just type-check-packages-yaml-dsl-lsp` + `just check-only-py`（必要时再跑 `just qa`）
