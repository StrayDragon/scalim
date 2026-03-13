## Why

仓库已经把 `notebooks/marimo/demo_big_data_report/` 作为“唯一主线教程 + 集成对拍入口”,但目前 docs-site 缺少一个**可发现的入口页**把这条主线明确讲清楚,导致读者容易在 YAML DSL 文档、示例目录与 `just` 入口之间来回猜。

同时,随着 YAML DSL/workflow/outputs 等能力迭代,需要一个稳定的文档入口持续说明:
- canonical demo 在哪里
- 如何运行/对拍/在 CI 回归
- 示例与生成/治理边界(哪些是 SSOT,哪些是生成物)

## What Changes

- 在 `docs/doc/` 增加一页“主线教程: demo_big_data_report”入口文档:
  - 指向 `marimo` 教程入口(`demo_main.py`)与 `just examples` gate(`run_examples.py`)
  - 说明 canonical YAML 示例路径与其在 skill/reference 导出中的角色
  - 给出最小命令序列(跑起来/对拍/排错)与常见坑位提示
- 更新 `docs/doc/getting-started/reading-guide.md` 与相关索引页,把该入口页纳入推荐阅读/导航路径,避免分散引用。
- 遵循 doc governance:
  - 不手改 `*.gen.*` 文件
  - 不手改 `AUTOGEN:*` 注入区块内部
  - 需要注入/生成时通过 `just gen-docs` 刷新并由 `just qa` 漂移门禁兜底

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `docs-site`: 增加并要求 docs-site 提供“唯一主线教程入口页”,并确保从 getting-started/索引路径可发现。

## Impact

- 受影响模块(预期):
  - `docs/doc/getting-started/**` 与可能新增的 tutorial 页面
  - `docs/zensical.toml`(如需补 nav 入口)
  - 文档生成与漂移门禁(`just gen-docs` / `just qa`)的相关流程(不改变规则,只新增受控内容)
