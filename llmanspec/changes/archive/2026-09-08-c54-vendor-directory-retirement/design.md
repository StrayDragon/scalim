# Design: Stage C vendor/ 目录退役

## 关键设计决策

| 决策点 | 结论 | 理由 |
|---|---|---|
| litejinja2 落点 | `dsl/yaml_dsl/_internal/litejinja2/` | 唯一运行时消费方为 `config_parsing/template_precompile.py`，内聚最强；保名（Jinja2 兼容子集语义锚点） |
| importlibx 落点 | `_internal/utils/importlibx.py` | 跨切面（sinks/workflow/ob/dsl/typedefs），共享 util 位置；沿用 x 后缀惯例 |
| provenance 承载 | 从「vendor README 集中登记」改为「模块 docstring 各自承载」 | vendor README 随目录消亡；litejinja2 docstring 已有上游 pin + ratchet 说明，importlibx 为纯第一方无需 provenance |
| 治理脚本特例 | 删除 vendor 分支/排除项（非保留） | 目录不存在后特例是死配置；脚本对一般路径的逻辑不变 |
| r201 重写方向 | 「第一方迷你库 docstring provenance + 禁止重建 vendor 托管概念」 | 保留可审计意图，切换承载位置；锁定场景经 `rules_edit_acked` 修改 |

## 文档/生成边界

- **手工 SSOT**：迁址文件、import 点、`scripts/check-*.py`/`gen-docs.py`、pyproject coverage、根/llmanspec AGENTS.md。
- **生成物**：`docs/doc/getting-started/public-api.gen.md` 文案含 vendor 排除描述 → `just gen-docs` 刷新。

## Drift gate

- `llman sdd validate --all --strict --no-interactive`
- `just check-only-py`（重点：check-import-graph / check-complexity / check-cast-usage / check-no-branch / check-no-cover / api-surface——它们自身被修改）
- 发布前 `just qa`

## 风险与回滚

- 纯迁址 + 死配置删除，无行为变更；单 commit 可整体 revert。
- 相对导入深度逐文件核对（3/4/5 点深度不一）；governance 测试文件随迁改名。
- root 属主 `__pycache__` 残留（dataclassesx/yamlx/_yaml 等）无法删除——仅 gitignored 现场残留，不影响 git/构建，留给用户 `sudo rm -rf src/scalim/vendor` 一并清理。
