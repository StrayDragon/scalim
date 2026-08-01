# Tasks: c10-write-precompute-derived-fields

> 规划壳；**尚未** `change start` / Specs landing。Apply 前须 Branch binding 后改 live specs。

## 0. Specs landing（start 之后）

- [x] 0.1 在 live `execution-hotpath-fastpaths` 增补/改写 MUST（late 判定、禁止 `$ctx` late、副作用时机、事件 phase、fast_fail+discard、内存有界）；**不**新建平行 capability
- [ ] 0.2 `llman sdd validate <id> --strict --no-interactive` 全绿

## 1. 判定与计划面

- [ ] 1.1 实现 late 字段集合推导（仅 Plan/IR 显式依赖）；单测：被其它 derived / LoadRef 消费 → 不 late
- [ ] 1.2 排除含 `$ctx`/`ctx_attr` 的 call_by；单测锁定

## 2. 执行面（垂直切片：识别 → 跳过 early compute → write-precompute → 测试）

- [ ] 2.1 Compute 路径跳过 `late_fields`
- [ ] 2.2 **切片 A（行 sink）**：Row emission 写出前算 late 子图 + row-local deps cache；不落 BatchContext
- [ ] 2.3 值相等对拍（compute_expr + 无 ctx call_by）
- [ ] 2.4 `FIELD_COMPUTE` + `scalim_compute_phase` meta；未订阅 observer 时无额外税
- [ ] 2.5 **切片 B（列 sink）**：`write_column` 前物化该 late 列（算完即写、默认不驻留）；MVP 对比 eager vs late 驻留/RSS

## 3. 护栏与模式

- [ ] 3.1 quiet / fast_fail 与写出前缀行为：测试 + spec 表述一致
- [ ] 3.2 列路径拓扑 /「late 依赖 late」按 design open question 收口并单测

## 4. 证据与回归

- [x] 4.0 **复杂基准（Apply 前）**：`mvp/repro_complex_baseline.py --write-baseline`；`evidence/baseline-complex.json` 中 row/column `golden_ok` 须为 true；实现后同参复跑不得破坏黄金值
- [x] 4.0b **规模矩阵**：`mvp/run_scale_matrix.py` — sim `smoke,small,medium,large`（~5/15/30GiB）+ engine `smoke,*_engine` 代理；交叉校验全绿后写 `evidence/baseline-matrix-*.json`
- [ ] 4.1 行路径：`mvp/repro_row_late_vs_eager.py`（实现后补 engine late A/B）
- [ ] 4.2 列路径（含链式暂留）：`mvp/repro_column_late_vs_eager.py` + complex baseline 列段；实现后补 engine late A/B
- [ ] 4.3 `just bench` / `bench-compare`：seq 相关 group 不回退
- [ ] 4.4 Python 3.6 smoke（`.tmp/venvs/py36-scalim`）

## 5. 文档

- [ ] 5.1 开发者文档：write-precompute 行为、call_by 时机后移说明（用户面保持「无需改脚本」）
- [ ] 5.2 若触及 public API 目录，更新 reading-guide / public-api 仅当确有导出符号
