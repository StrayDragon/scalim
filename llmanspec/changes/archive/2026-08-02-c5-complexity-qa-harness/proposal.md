---
depends_on: []
branch: sdd/c5-complexity-qa-harness
base_sha: 385eb688a8e60d15cb805fb2b1c295055de4241f
checkpointed: true
checkpoint_sha: 385eb688a8e60d15cb805fb2b1c295055de4241f
---

# 复杂度 QA harness：用函数级闸替代纯行数硬闸

> **加塞**：`c5` 优先于 c20/c30 实现流插入。动机：`just qa` / `quick-check` 中的 `check-module-size` 以**文件/目录物理行数**硬失败，逼机械拆文件、对「多薄函数 vs 难读分支」不敏感；c10 落地时已显式感到不合理。

## Why

现状：

| 闸 | 行为 | 问题 |
|----|------|------|
| `scripts/check-module-size.py` | 热点路径 `_HOTSPOT_LIMITS` 超行数 → `--check` 失败 | 行数是粗代理；同 LOC 可极简可极乱 |
| `governance-module-organization` **r253** | MUST：单模块超过约定阈值（例 >1000 行）须拆分 | 合约把 LOC 写成硬 MUST，与脚本同构 |
| ruff `C901` + `check-noqa-c901` | 函数圈复杂度豁免须带 plan | **已是函数级**，但与 module-size 双轨且不同指标 |

目标（对齐 `code-complexity-qa-harness` skill）：

1. **硬闸**：函数级 **cognitive（Sonar）+ cyclomatic（McCabe）**，仅 ENTRY/热点集合，阈值 = **采基线 + 小余量**（禁止抄行业默认 15 直接 HARD）。
2. **软雷达**：更广 `src/scalim` top-N，不失败（`just complexity`）。
3. **LOC**：降为 **SHOULD** + 可选极高「硬味天花板」（防无底崩溃）；**移除**「行数超限即 QA 红」作为主复杂度故事。
4. 工具为 CLI/脚本依赖（`.tools/` / `uvx` pin），**不**进应用 `dependencies`。

## What Changes

- 新脚本：`scripts/check-complexity.py`（`--check` HARD / `--radar` 软报），接入 `just qa` / `quick-check`（替换或降级 `check-module-size --check`）。
- `check-module-size.py`：改为报告-only 或 SHOULD 警告；可选保留极高顶（如 ≥2500）作 OPTIONAL 硬味。
- Specs landing：改写 `governance-module-organization` **r253**（及 scenario `module-size-guardrail-fails-fast`）→ 复杂度 MUST + LOC SHOULD；与 r645（C901）交叉引用、不双 SSOT。
- 文档：`docs/doc/dev/` 短文说明阈值 SSOT、如何放宽、与 pragma allow-c901 关系。
- 采基线证据：`.tmp/evidence/complexity-baseline/`（可复跑；稳定摘要写入 change `mvp/` 或 evidence 钉死表）。

**不改**

- 业务运行时行为。
- 强行全仓 cognitive≤15。
- 把 cccc-rs 当 Python 主闸（实测对 `.py` 0 functions；本仓以 Python 为主）。

## 工具选型（调研结论）

| 候选 | 结论 |
|------|------|
| **cccc-rs** | 本机有；**不解析 Python**（`--ext py` → 0 functions）→ 不作主闸 |
| **radon** (`cc`) | McCabe；`uvx` 易用；与现有 C901 同族 → **cyclomatic 主源** |
| **cognitive-complexity** (Sonar 算法 Py 包) + 薄封装 | **cognitive 主源**（不依赖 flake8 插件进产品依赖） |
| **lizard** | 便宜 CCN/长度探针；可作雷达辅，不作唯一真理 |
| ruff C901 | 保留；与 harness 互补（豁免治理仍走 `check-noqa-c901`） |

## 初始阈值规划（Apply 前须用全 ENTRY 复测校准）

预扫（radon `cc -n C`，热点子集）显示烫点例：

- `compile_output_composition_from_yaml` ≈ **cyclo 39**
- `ParserOutputsMixin._parse_output_aggregate_field_agg` ≈ **32**
- `ValidatorSourcesMixin._validate_sources` ≈ **28**

建议 **第一期 HARD ENTRY** = 今日 `_HOTSPOT_LIMITS` 路径集合（文件级入口，按文件内 **max 函数** 计）：

```text
MAX_CYCLOMATIC  = max(基线_max_cyclo, 已知烫点) + 3..5   # 预估落在 42–45，校准后钉死
MAX_COGNITIVE   = 同法采基线 + 3..5                      # 禁止未扫先写死 15
LOC_SHOULD      = 显著低于舒适区（例单文件 ~800–1000 提示）
LOC_HARD_TASTE  = 可选 ~2500（仅防崩溃；不替代复杂度闸）
```

数字以 Apply 任务「采基线」输出为准写入脚本常量 + spec，防漂移。

## Capabilities

### Modified

- `governance-module-organization`：r253 从 LOC 硬闸改为复杂度硬闸 + LOC SHOULD；场景更新。

### New（可选）

- `quality-complexity-harness`：仅当不想挤进 governance 时；**优先改 r253 单 SSOT**。

## Impact

- **兼容**：默认行为不变；QA 失败条件从「行数」改为「ENTRY 函数复杂度超阈」。
- **维护**：少逼无意义拆文件；烫点用 radar 可见。
- **风险**：已知高 cyclo 函数若阈值设太紧会红 → 必须基线校准；允许 `# pragma`/allowlist 绑定 plan（对齐 C901）。

## Ethics

- `ethics.risk_level`: low
- `ethics.prohibited_actions`: 无基线用行业默认硬闸全树；把复杂度 CLI 塞进 runtime 依赖；静默删 r645
- `ethics.required_evidence`: ENTRY 基线表 + `--check` 绿 + 压低阈值时非零退出
- `ethics.refusal_contract`: 无基线不得合入 HARD 阈值
- `ethics.escalation_policy`: 若须大面积 noqa 才能绿 → 停并改 ENTRY/阈值，勿默默放宽

## Open Questions — **已决议（按推荐）**

1. HARD ENTRY = 今日 `_HOTSPOT_LIMITS` 路径集合。**已决议：是。**
2. LOC 硬味天花板。**已决议：保留**，`LOC_HARD_TASTE ≈ 2500`（OPTIONAL 失败；不替代复杂度闸）。
3. cognitive 工具。**已决议：`cognitive-complexity` + `radon`**（cccc-rs 不作 Python 主闸）。