# Tasks: c20-compute-expr-rowwise-fusion

> 已 `change start` → 分支 `sdd/c20-compute-expr-rowwise-fusion`。
> 决策收口见 `design.md`「已决议」与下方对照。

## 已决议（Apply 前钉死）

| ID | 决议 |
|----|------|
| Q1 | 融合组 deps **完全相同**（第一期不放宽重叠） |
| Q2 | **行** streaming / 非流式行可融合；**列 sink 不融合** |
| Q2b | 组内任一字段 EXP `call_by` memo 生效 → **整组不融合** |
| Q3 | 融合路径（无 memo）`calc_calls == N×M` 硬门禁；减次数另开 multi-output |
| 组织 | 与 c10 **两 change**；共享「依赖→算法→值」物化原语；late 行内复用归 c10 |

## 0. Specs landing（start 之后）

- [x] 0.1 新增 `execution-compute-rowwise-fusion` MUST：候选规则、外壳、值/调用次数等价、内存有界、与 hotpath 关系；写入 Q1–Q3 / Q2b
- [x] 0.2 校验 strict

## 1. 规划：分组

- [x] 1.1 在 **同一** compute segment（pre-ref 或 post-ref）上识别 fusion groups：互不依赖 + **deps 完全相同** + `compute_expr` 或无 ctx `call_by`
- [x] 1.2 排除：`$ctx`（`call_ctx_key`）、`is_constant_compute`、列 sink、EXP memo 命中字段所在组；单测锁定

## 2. 执行：融合循环（垂直切片）

- [x] 2.1 实现 row-wise 执行（先 `compute_expr`）
- [x] 2.2 扩到无 ctx `call_by`；**调用计数 == N×M** 对拍（Q3）
- [x] 2.3 安全外壳：fast_fail / wants `FIELD_COMPUTE`|`OPERATOR_SPAN` → 回退 field-major；测试锁定

## 3. Streaming / 组合 / memo

- [x] 3.1 行路径开融合（含 streaming）；列路径强制 field-major（Q2-B）；与 row emission 集成测
- [x] 3.2 EXP memo 与融合互斥（Q2b）：controller 对该字段 allowed → 整组禁用；测例
- [x] 3.3 文档：不减少 call_by 次数；multi-output 另案；与 c10 边界（late 行内复用归 c10）

## 4. 证据与回归

- [x] 4.1 本 change 内 MVP：`mvp/repro_nxm_framework_tax.py`（说明见 `mvp/README.md`）；融合实现后在同目录加 engine A/B（fused on/off）
- [ ] 4.2 可选补充 `.tmp/repro/rowwise-fusion/` 大形状；RSS ≤10%
- [ ] 4.3 `just bench-compare`；py3.6 smoke

## 5. 维护性收尾

- [x] 5.1 融合入口单一、可日志 `fused_group_size` / `disabled_reason`（含 `memo` / `column_sink` / `ctx`）
- [x] 5.2 避免与 c10 late 路径重复实现行内 cache
