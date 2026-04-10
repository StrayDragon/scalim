## 1. 编译前端 SSOT（src/scalim，Python 3.6 兼容）

- [ ] 1.1 新增 `src/scalim/dsl/yaml_dsl/compiler_frontend/`（或等价路径）与公开入口：实现 front-end compilation 的分段 API（diagnostics 优先；full 产物按需）
- [ ] 1.2 复用现有 loader/validator/imports：把 `parse/imports 展开/schema+语义校验/location index/effective view` 收敛为编译前端实现（约束：不导入/不执行用户模块；不依赖 allowlist）
- [ ] 1.3 为前端产物定义可序列化快照（含 `schema_version`）：至少覆盖 diagnostics/effective view/import graph 的稳定输出，并补齐基础回归测试（验收：无 allowlist 也可稳定产出）

## 2. IR/Plan “No callables” 重构（纯描述 + 可序列化）

- [ ] 2.1 改造 `src/scalim/spec/ir/**`：移除所有 callable（包含 loader/params_builder/normalize.call_by、`DerivedFieldIr.calculator`、`FieldIr.transform/value_formatter`），引入 reference descriptor（`PythonReference`/`RuntimeHandleId`/value ops steps 等）
- [ ] 2.2 改造 YAML DSL conversion：`conversion_*.py` 只生成静态引用描述，不做 import/resolve；将 allowlist enforcement 从“compile 前置”迁移到 runtime linking
- [ ] 2.3 改造 planning/operators：operators 只保留 ID + 最小元信息；提供 `plan_snapshot`/`deps_snapshot`（显式 `schema_version`，稳定排序）供 LSP/viz 消费

## 3. Runtime linking（RuntimeBindings）与执行接入

- [ ] 3.1 引入 `RuntimeBindings` contracts 与错误模型（allowlist violation / resolver error），实现 run-scope 去重缓存与可观测性摘要
- [ ] 3.2 改造 execution：operator executors 从 `RuntimeBindings` 取 callable（不再从 IR 直接拿）
- [ ] 3.3 改造 runtime compiler：`runtime/compiler.py` 变为组合器（front-end compilation → runtime linking → execute），并确保 fail-fast 发生在执行之前

## 4. LSP package 瘦身（packages，Python >= 3.10）

- [ ] 4.1 将 `packages/scalim-yaml-dsl-lsp` 的语义实现迁移为调用编译前端 API：diagnostics-first；plan/deps on-demand/idle backfill；移除对 `scalim.dsl.yaml_dsl._internal.*` 的直接耦合
- [ ] 4.2 验收：跑 `c29` 的 LSP contract tests（SSOT=fixtures+snapshots），确保行为不漂移；若确需变更，按 `UPDATE_GOLDEN=1` 显式更新并在 PR 中说明
- [ ] 4.3 验收：补齐“LSP 不需要 allowlist 也能得到 plan/deps”的测试用例（对齐 `yaml-dsl-compiler-frontend` delta spec）

## 5. 生成物/文档边界与全量回归

- [ ] 5.1 如需调整 YAML DSL schema：只改 SSOT（`src/scalim/dsl/yaml_dsl/schema_dsl/**` 等），禁止手改任何 `*.gen.*`，并运行 `just gen-yaml-dsl-schema` + drift gate 校验
- [ ] 5.2 回归：更新/补齐 YAML DSL 相关单测与 notebooks 对拍样例（仅在必要时），并跑 `just qa`
- [ ] 5.3 运行 `just openspec-check`，确保变更工件结构与脱敏校验通过
