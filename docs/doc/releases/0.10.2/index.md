# 0.10.2 重点特性

??? note "适用读者"
    - 已在 **0.10.1**、准备升到 **0.10.2** 的使用方
    - 仍在 YAML 写 `lookup_chunk_size`，或需要 workflow 级低漂移观测的下游与 agent

**相对 `v0.10.1`：YAML 有一处强制迁移（lookup 分片）；观测能力为 opt-in。**  
本版两块：**(1)** `LookupChunking` 收口到 Python SSOT；**(2)** `scalim_run_stats/v1` + profiles + viz 旁路读数。  
typed `Event` 契约与 0.10.1 相同，不重复展开；见 [0.10.1 重点特性](../0.10.1/)。

## 一览

| 变更 | 默认影响 | YAML 要改吗 | 适配 SSOT |
|------|----------|-------------|-----------|
| `sources.*.lookup_chunk_size` 迁出 | **Breaking**（仍写则 fail-fast） | **是**（删字段） | [2026-08-09-lookup-chunking-python-ssot](../../../agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-09-lookup-chunking-python-ssot.md) |
| `LookupChunking` / `SourceCache` / `RowsReuse` | Python 运行策略；cache YAML 可留 | 否（cache） | 同上 + [yaml-runtime-policy-boundary](../../../agentdev/skills/scalim-yaml-dsl/references/yaml-runtime-policy-boundary.md) |
| `ObservabilityProfile` + `WorkflowStatsAccumulator` | **opt-in**；生产默认可 `components=[]` | 否 | [run-stats.md](../../viz/run-stats.md) + `agentdev/skills/scalim-run-stats/` |
| run_stats sibling + scalim-viz 面板 | 落盘旁路；不改业务 sink | 否 | 同上 |
| `RunOverrides` header 工厂默认 `name` | 仅旧工厂默认依赖者 | 否 | lookup upgrade 卡「相关覆盖」 |

```mermaid
flowchart TD
  U[从 0.10.1 升到 0.10.2] --> Y{YAML 仍有 lookup_chunk_size?}
  Y -->|是| L[删字段; DemandRunRuntimeOptions.lookup_chunking]
  Y -->|否| O{需要自我观测?}
  L --> O
  O -->|否| Done[生产保持 components 空]
  O -->|是| B[build_observability_profile BENCH]
  B --> R[读 run_stats.nodes / stages_total]
  R --> Done
```

## 迁移 / 适配清单（最短）

### 1. YAML `lookup_chunk_size` → Python `LookupChunking`（Breaking）

- **命中条件**：demand/workflow YAML 的 `sources.*` 仍写 `lookup_chunk_size`。
- **调整**：删 YAML 字段；在 `DemandRunRuntimeOptions.lookup_chunking` 用 `LookupChunking.sized(...)` / `.off()`。
- 片间并行：`LookupChunking.sized(n, parallel=True)` + `parallel_mode="adaptive"`。
- 何时用 / 用 `LOADER_CALL` 自证：见 user-guide §4.4.3 与 `ch164_public_api_lookup_chunking`。
- Before/After：见 yaml-dsl upgrade 卡（上表）。

### 2. 低漂移 run_stats（opt-in）

- 日常：`ObservabilityProfile.BENCH` → `accum.build_run_stats()`；workflow 读 **`nodes[]`**，勿读共享 Perf 末态。
- 落盘：`write_run_stats_sibling`（可与 viz 同目录旁路）；**勿**嵌入 `viz_snapshot.json`。
- 生产 / 正式非 DEBUG：保持 `components=[]`；开发服 / bench 才开 memory（需 `psutil`）。
- 门控与二开：见 [run-stats.md](../../viz/run-stats.md) 与 skill 卡 `task-downstream-env-gating` / `task-observer-hook-extension`。

### 3. 与 0.10.1 / 0.10.0

- typed Observer/Hook 仍收完整 `Event`（0.10.1）。
- write-precompute / fusion / chunk 并行契约与 0.10.0 一致。

## 发版引用（可贴 Release）

```text
## 亮点（相对 0.10.1）

- Breaking（YAML）：sources.*.lookup_chunk_size 迁出；改 DemandRunRuntimeOptions.lookup_chunking=LookupChunking...
  agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-09-lookup-chunking-python-ssot.md
- Opt-in：scalim_run_stats/v1 + ObservabilityProfile；生产默认可静默；viz 可读 sibling run_stats.json
  docs/doc/viz/run-stats.md
- 文档：下游环境门控 / Observer·Hook 二开 skill 卡
总览：docs/doc/releases/0.10.2/index.md
```

## 升级提示（复制到下游代理 / 聊天中）

请将以下代码块粘贴到已打开的**下游**仓库编码代理中。目标：**扫描 + 按需迁移**（除非你明确要求编辑，否则先出报告）。

````markdown
# 任务：升级 / 扫描此仓库，检查 Scalim v0.10.2 适配点（基准 0.10.1）

你正在处理一个依赖于 `scalim` 的**下游**项目。目标版本：**0.10.2**（相对 **0.10.1**）。

## 结论先行
- **YAML Breaking**：`sources.*.lookup_chunk_size` 已迁出；继续写会 fail-fast。删字段，改用 `DemandRunRuntimeOptions.lookup_chunking` + `LookupChunking.sized(...)` / `.off()`。
- **观测为 opt-in**：生产 / 正式非 DEBUG 可保持 `components=[]`；不要默认挂 memory / DEBUG。
- typed Observer/Hook 仍收完整 `Event`（0.10.1 契约不变）。
- 0.10.0 的 write-precompute / fusion / chunk 并行默认与开关不变（并行请挂在 `LookupChunking.sized(n, parallel=True)` + `parallel_mode="adaptive"`）。

## SSOT
- 总览：https://github.com/StrayDragon/scalim/blob/v0.10.2/docs/doc/releases/0.10.2/index.md
- Lookup 升级卡：https://github.com/StrayDragon/scalim/blob/v0.10.2/agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-09-lookup-chunking-python-ssot.md
- Agent 指引：https://github.com/StrayDragon/scalim/blob/v0.10.2/agentdev/skills/scalim-yaml-dsl/references/0.10.2-release-highlights.md
- Run stats：https://github.com/StrayDragon/scalim/blob/v0.10.2/docs/doc/viz/run-stats.md
- 生产静默门控：https://github.com/StrayDragon/scalim/blob/v0.10.2/agentdev/skills/scalim-run-stats/references/task-downstream-env-gating.md

## 步骤
1. 记录当前 `scalim` 固定版本（`pyproject.toml` / requirements / lock / vendored `libs/scalim`）。
2. 扫描（仓库根目录；跳过 `.git` / `.venv` / `node_modules`）：

```bash
rg -n --hidden -g '!**/.git/**' -g '!**/node_modules/**' -g '!**/.venv/**' -g '!**/__pycache__/**' \
  'lookup_chunk_size' .

rg -n --hidden -g '!**/.git/**' -g '!**/.venv/**' \
  'LookupChunking|parallelize_lookup_chunks|ObservabilityProfile|build_observability_profile|WorkflowStatsAccumulator|write_run_stats_sibling|et_scalim_run_stats' .
```

3. 对每个命中分类：`HIT-LOOKUP-CHUNK` | `HIT-OBS-MIGRATE` | `OK` | `FALSE-POSITIVE`
4. 若有 `HIT-LOOKUP-CHUNK`：删 YAML 字段；按升级卡改 `lookup_chunking={...: LookupChunking.sized(...)}`；跑一条最小 demand/workflow。
5. 若下游自研 stats / StageMemory：优先迁到内置 profiles + `scalim_run_stats/v1`；生产非 DEBUG 保持静默。
6. 输出简短 Markdown 报告：仓库 / 分支 / scalim 版本 / 结论（`no impact` / `needs lookup_chunking migration` / `needs obs migration` / `uncertain`）。
````

## Agent skill

- 本版 agent 摘要：`agentdev/skills/scalim-yaml-dsl/references/0.10.2-release-highlights.md`
- Lookup 分片迁移：`agentdev/skills/scalim-yaml-dsl/references/upgrades/2026-08-09-lookup-chunking-python-ssot.md`
- Run stats 装配：`agentdev/skills/scalim-run-stats/SKILL.md`
- 生产静默 vs 开发服：`agentdev/skills/scalim-run-stats/references/task-downstream-env-gating.md`
- Observer/Hook 扩展：`agentdev/skills/scalim-public-api/references/task-observer-hook-extension.md`
