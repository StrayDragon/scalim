## 1. LSP `$import` 导航能力

- [x] 1.1 在 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cursor_extraction.py` 增加 `$import` 光标抽取（支持 string 与 list element），输出 ref + range + yaml_path
- [x] 1.2 在 shared core 增加 `$import` ref 解析与 alias->fragment 路径解析（复用 `scalim.yaml` project discovery：`import_aliases`/`import_allowed_roots`/`allowed_yaml_roots`），并保证失败可诊断降级（warnings，不 crash）
- [x] 1.3 实现 fragment YAML 的 key 定位：读取 fragment 文本 ruamel compose，按 segments 下钻到目标 mapping，并返回 key 的 line/column 供 definition 跳转
- [x] 1.4 在 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py` 的 definition/hover 中接入 `$import` 分支（Python 引用未命中时再尝试 `$import`）
- [x] 1.5 增加 LSP server 回归测试（`tests/yaml_dsl/test_yaml_dsl_lsp_server_mvp.py` 或新文件）：覆盖 `$import` 的 go-to-definition 与 hover（unknown alias/越界路径等降级场景）

## 2. 修复 JSON schema 在 `$import` 场景下的假阳性（Missing `budget` 等）

- [x] 2.1 修改 schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/models/resources.py`（以及同类模式处），为 kind-based `if` 增加 `required: ["kind"]`，避免 `kind` 缺失时误触发 then 分支
- [x] 2.2 运行 schema 生成入口（SSOT → 生成物）：`uv run python scripts/gen-yaml-dsl-schema.py`（或直接 `just qa` 触发漂移门禁），提交生成物变更（禁止手改 `*.gen.*`）
- [x] 2.3 增加回归测试：解析 `src/scalim/dsl/by_yaml/schema/demand.gen.json`，断言 `definitions.book.allOf[*].if` 内含 `required: ["kind"]`；并添加一个 `$import`-based book mapping 的最小 schema 校验用例，确保不会要求 `budget`

## 3. 文档与手动验收

- [x] 3.1 更新 VSCode/LSP 集成文档：说明 `$import` 可跳转/hover；解释“编辑器 schema 不展开 imports”的现实边界与本次修复策略（schema 需对 `$import` 形态友好）
- [ ] 3.2 手动验收：VSCode 打开 `notebooks/.../declared_yaml_dsl/ecommerce_report.yaml`
  - `$import: fragments.report_book` 可跳转到 `ecommerce_report_fragments.yaml` 的目标 mapping
  - 不再出现 schema 的 `Missing property budget` 假阳性红线

## 4. 质量门禁

- [x] 4.1 运行 `just qa` 并确保工作区干净（`git status --porcelain` 无输出）
