# Design: c0-remove-score-by-rank-builtin

## Decision

移除 `score_by_rank` 内置后置派生字段，由 `compute` 表达式等价替代。

## 等价性验证

`score_by_rank` 实现 `base - (rank - 1) * step`（3 个算术运算）。`SecureComputeEngine` 中的 `compute` 表达式可严格等价：

| 验证项 | 结果 |
|---|---|
| `extract_compute_dependencies("100 - (rank - 1) * 3")` | 正确提取 `['rank']` |
| `engine.compile(expr, deps)(rank=1)` | `100` |
| `engine.compile(expr, deps)(rank=2)` | `97` |
| `engine.compile(expr, deps)(rank=3)` | `94` |
| `allowed` 依赖校验（`agg.group_by ∪ agg_field_ids`） | rank 字段在允许范围内 |
| CSV 输出 `str()` 对拍 | 完全一致 |

唯一细微差异：`score_by_rank` 返回 `Decimal`，`compute` 返回 `int`。但 CSV 输出相同（`str(94) == str(Decimal('94'))`），且 compute engine 内置 `Decimal`/`dec` 函数供需要高精度（如 `step=3.5`）时使用：

```yaml
compute: "dec(100) - (dec(rank) - 1) * dec(3.5)"
```

## Migration

```yaml
# 改前
score:
  score_by_rank:
    rank_field: rank
    base: 100
    step: 3

# 改后
score:
  compute: "100 - (rank - 1) * 3"
```

残留 `score_by_rank` 字段在 parser 层 fail-fast 并给出迁移提示。

## 运行期 / IR Spec — 无改动

`score_by_rank` 通过 `PostFieldSpec(kind="score_by_rank", calculator=...)` 注册，移除编译函数后框架自然不再处理该 kind。`PostFieldSpec` 和 `DerivedGroupBySpec` 均不耦合具体 post-field kind，无需改动 `derived_outputs.py` / `specs.py`。

## Scope

- 仅影响 `AGG_POST_PRODUCER_KEYS` 枚举、YAML schema、parser、runtime bridge
- Oracle 文件（`ecommerce_rank_score_oracle.py`）无需改动（纯 Python 实现，不依赖 scalim 内部）
