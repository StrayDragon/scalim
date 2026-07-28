# 发布前校准清单

??? note "适用读者"
    - 准备打版本 tag / 发版的维护者
    - Agent：按本页做 `last-tag → HEAD` 校准，勿跳步

本页是发版前的**人工校准方法**（质量门禁仍以 `just qa` 为准）。目标：在 bump / tag 之前，确认范围、破坏性变更、文档与公开面没有明显遗漏。

## 0) 前置

- 工作树干净，或明确哪些改动属于本 release。
- 已跑通 `just qa`（本清单**不替代** qa；勿在校准流程里重复跑完整 qa，除非用户要求）。
- 确定基线 tag：`git describe --tags --abbrev=0`（通常为上一发布 tag，如 `v0.9.18`）。

## 1) 划定范围（last tag → HEAD）

```bash
git log --oneline <tag>..HEAD
git diff --shortstat <tag>..HEAD
git diff --stat <tag>..HEAD -- src/scalim/ tests/ docs/doc/ agentdev/skills/ AGENTS.md
```

整理主题桶（建议 3–6 条），例如：breaking / 新 API / perf / docs-only / 治理归档。忽略纯 gen/archive 噪声时，仍要确认对应 **人工文档与 migration** 已落地。

## 2) Breaking 与边界（必查）

对照 `AGENTS.md` Hard Rules，至少确认：

- YAML vs Python policy：book **write** 是否仍只在 Python `ResourcesPolicy` / `BookWritePolicy`；YAML 不得回潮 `write_defaults`；book **budget** / `BookBudgetPolicy` 已移除（残留 `budget` 仍 fail-fast，应删字段，勿再当 current API）。
- 若有 breaking：skill upgrade SSOT（`agentdev/skills/scalim-yaml-dsl/references/upgrades/`）与站点 upgrades 索引是否已挂上；迁移文案是否可被下游照做。
- Enum / policy SSOT：公开构造函数是否仍 **strict-in Enum**；wire/state 是否仍 emit builtin `str`。
- 运行时边界：`src/scalim/` Python 3.6 兼容、相对 import、`.gen.*` 未手改。

## 3) 公开面与文档漂移

对范围内每个用户可见变化，核对：

| 面 | 查什么 |
| --- | --- |
| Public API | `# pragma: scalim-public-api` / `docs/doc/getting-started/public-api.gen.md`（改 SSOT 后走 gen，不手改 `.gen.`） |
| Agent skills | 相关 `SKILL.md` + `references/`（含 upgrades / guidance） |
| 人类文档 | `docs/doc/` 入口页、专页、`capability-matrix` / `review-checklist` / `user-guide` / `workflow` 等是否互相矛盾 |
| 架构图 | `docs/doc/architecture/arch.md` 的 sinks / 分层图是否漏掉新的稳定类型 |
| 阅读地图 | `getting-started/index.md`、`reading-guide.md`、`zensical.toml` nav 是否挂上新专页 |
| 示例 | `packages/scalim-misc` / `notebooks/` 是否仍演示已删除 YAML 字段 |

可选：对 `.tmp/known-outer-paths-using-this-package.txt` **只做路径级影响盘点**，勿复述文件内容。

## 4) llmanspec / futures

- 本 release 落地的 active change 是否已 archive（或明确留到下一版）。
- `llmanspec/futures/**`：已完成条目是否标 `done`；刻意不做的是否仍为 `later`/`drop`，避免发版说明与 future 打架。
- 打开的无关 `llmanspec/changes/*` 不自动阻塞发版；若行为已合入但 change 未归档，记入 release notes 风险。

## 5) 版本与产物（qa 之后）

```bash
just bump-versions <X.Y.Z>          # dry-run
just bump-versions <X.Y.Z> YES      # 写入主包/子包/前端 + constants + lock
```

确认：`pyproject.toml`、`packages/*/pyproject.toml`、`frontend/scalim-viz/package.json`、`src/scalim/_project_constants.py` 版本一致。

## 6) Release notes（最少集）

无根级 CHANGELOG 时，tag / GitHub release 正文至少包含：

1. **Breaking**（迁移一步怎么做）
2. **新能力**（默认是否 opt-in；与 YAML books / composition 的互斥）
3. **Perf / 行为修正**（用户可感知的）
4. **文档入口**（1–3 个链接）

## 7) Tag 与推送

- commit bump（及本清单触发的文档补丁）
- `git tag v<X.Y.Z>`（注释可复用 notes 摘要）
- 按维护者习惯 push commit + tag（本清单不规定远端权限细节）

## 快速勾选（复制用）

- [ ] 范围：`<tag>..HEAD` 主题桶已写清
- [ ] Breaking / YAML·Python 边界已核对；upgrade 文案齐全
- [ ] Public API + skills + 人类文档 + 架构图/导航无显见漂移
- [ ] 示例无已删字段；futures/archive 状态不矛盾
- [ ] `just qa` 已通过（本轮预先完成即可）
- [ ] `bump-versions` 已 apply，版本面一致
- [ ] Release notes 已写；准备 tag
