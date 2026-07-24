---
depends_on: []
---

## Why

`score_by_rank` 是一个 bespoke builtin，实现 `score = base - (rank - 1) * step`（3 个算术运算），其能力已被通用 `compute` 表达式严格覆盖。

与刚刚移除的基数护栏体系（`46aac9ef`，`llmanspec/changes/archive/2026-07-24-c15-remove-derived-outputs-cardinality-guardrails`）属同一模式：薄封装提供有限价值、底层有更通用的替代路径、维护成本分散在 schema/parser/runtime/enum 四层。

### 维护成本 vs 使用量

| 指标 | 数据 |
|---|---|
| 实际使用的 YAML 文件 | **1 个**（`ecommerce_rank_score_report.yaml`） |
| 维护代码行数（schema + parser + runtime + enum） | ~240 行 |
| 涉及测试文件 | 8 个 |

维护代码分布：

| 模块 | 代码量 |
|---|---|
| `output_enums.py` | `AGG_POST_PRODUCER_KEYS` 中 1 项 |
| `models/outputs.py` | 42 行（oneOf variant 完整 schema 定义） |
| `demand.gen.json` | ~70 行（生成物） |
| `parsers/outputs.py` | `_parse_output_aggregate_field_score_by_rank`（33 行）+ 分支判断 + dep 提取 + 交叉校验（~50 行合计） |
| `output_composition_yaml.py` | `_compile_score_by_rank_post_field`（35 行）+ 分支判断（~45 行合计） |
| 测试 | 8 个文件，约 30 处引用 |

## What Changes

- **`AGG_POST_PRODUCER_KEYS` 移除 `"score_by_rank"`**：枚举 SSOT 收窄
- **Schema models/outputs.py 移除 `score_by_rank` oneOf variant**：~42 行 schema 定义删除
- **Parser 移除 `_parse_output_aggregate_field_score_by_rank` + 分支 + 交叉校验**：~50 行
- **Runtime bridge 移除 `_compile_score_by_rank_post_field` + 分支**：~45 行
- **残留 fail-fast**：YAML 中出现 `score_by_rank` → parser 报错并提示迁移为 `compute`
- **唯一使用方迁移**：`ecommerce_rank_score_report.yaml` 中 `score_by_rank: {rank_field: rank, base: 100, step: 3}` → `compute: "100 - (rank - 1) * 3"`
- **测试更新**：8 个测试文件改用 `compute` 等价表达式

## Capabilities

- `execution-derived-outputs`
- `yaml-dsl-write-policy-and-output-extras`

## Impact

- **BREAKING**：指纹变化（`score_by_rank` 指纹行消失）、`AGG_POST_PRODUCER_KEYS` 枚举变更
- **迁移**：1 个 YAML 文件 + 测试中的 score_by_rank 替换为 compute；Oracle 文件（`ecommerce_rank_score_oracle.py`）无需改动
- **净减代码**：~240 行
