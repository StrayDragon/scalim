## 1. `scalim.config.yaml`（SSOT 配置）

- [ ] 1.1 在本仓库新增 `scalim.config.yaml` v1 的解析与校验（library API，可被外部 LSP/编辑器复用）
- [ ] 1.2 为缺省场景实现默认推导规则（默认 globs + python roots）并补齐单测
- [ ] 1.3 增加文档说明（SSOT：OpenSpec specs；文档入口：`just gen-docs`；验收：`just qa`）

## 2. LSP 可复用的语义服务（不调用 CLI）

- [ ] 2.1 抽取/固化 demand Diagnostics 的 library API（parse/imports/validate/location attach）
- [ ] 2.2 提供 workflow schema-only Diagnostics helper（读取 `workflow.gen.json` 并输出可定位 issues）
- [ ] 2.3 提供 `loader`/`call_by` 的静态引用解析与 `ast` 符号定位 helper（禁止 import 执行）
- [ ] 2.4 补齐单测：引用解析、模块落盘、符号定位、相对引用路径规则

## 3. Schema 产出与分发（drift gates）

- [ ] 3.1 明确 schema SSOT：`src/scalim/dsl/by_yaml/schema/*.gen.json`（生成入口：`just gen`；验收：`scripts/gen-*.py --check` 与 `just qa`）
- [ ] 3.2 明确外部扩展仓库获取 schema 的策略（发布包/指定 tag 拉取），并记录到 docs（入口：`just gen-docs`）
- [ ] 3.3 为外部仓库提供最小示例与验收口径（schema 绑定可用、Diagnostics 可定位、Definition 可跳转）

## 4. 外部仓库交付（不在本仓库实现）

- [ ] 4.1 创建 `scalim-yaml-dsl-lsp` 仓库骨架（Python LSP server + VSCode extension）
- [ ] 4.2 实现 LSP server v1：Diagnostics/Definition/Completion/Hover（按本变更 specs）
- [ ] 4.3 实现 VSCode 扩展 v1：依赖 `redhat.vscode-yaml`、schema 绑定、读取并同步 `scalim.config.yaml`、venv 管理与 server lifecycle
- [ ] 4.4 增加 VSCode 集成测试（`@vscode/test-electron`）：schema 生效、跳转生效、保存后 Problems 可定位

## 5. Gates 与发布前检查

- [ ] 5.1 运行并通过 `just openspec-check`（sanitize + validate）
- [ ] 5.2 运行并通过 `just qa`（lint/type/tests + drift checks）

