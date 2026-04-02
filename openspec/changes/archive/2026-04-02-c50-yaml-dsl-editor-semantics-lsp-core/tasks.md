## 1. 新包脚手架

- [x] 1.1 新增 `packages/scalim-yaml-dsl-lsp/pyproject.toml`（`requires-python >= 3.10`）与基础目录结构（`src/scalim_yaml_dsl_lsp/`）
- [x] 1.2 将新包纳入 workspace/锁文件口径（确保 `just uv-lock-check` / `just qa` 通过）
- [x] 1.3 明确依赖边界：core 仅依赖 `scalim`；`pygls/lsprotocol` 等放入可选 extra 或 server 子模块

## 2. 抽离 editor semantics core

- [x] 2.1 将 `src/scalim/dsl/by_yaml/editor_semantics.py` 的实现迁移到 `scalim_yaml_dsl_lsp.core`（按 design.md 的 API 形状）
- [x] 2.2 保证 core 满足 spec：静态解析、不执行用户代码、不改写进程级全局状态（例如 `sys.path`）
- [x] 2.3 将 roots 策略（`python_roots`/`allowed_yaml_roots`/`project_root`）的归一化与校验作为 core 的 SSOT，并补齐边界测试

## 3. 主包迁移与去兼容

- [x] 3.1 删除 `scalim.dsl.by_yaml.editor_semantics`，并将仓库内导入路径统一迁移到 `scalim_yaml_dsl_lsp.core`
- [x] 3.2 补充集成测试：确保旧 import 路径不可用，避免未来回退引入 shim

## 4. LSP/工具链对齐

- [x] 4.1 将未来/现有 LSP server 侧调用点统一指向 `scalim_yaml_dsl_lsp.core`（避免在 server 层重复实现 validator/schema 规则）
- [x] 4.2 若新增 docs：明确 SSOT 与生成边界；禁止手改 `*.gen.*` 与 `AUTOGEN` 区块；需要刷新时使用 `just gen-docs`

## 5. 验收与收尾

- [x] 5.1 跑通 `just qa`（含 lint/tests/drift/openspec gates）
- [x] 5.2 将 delta specs 同步到 `openspec/specs/`（如需要），并按流程归档该 change
