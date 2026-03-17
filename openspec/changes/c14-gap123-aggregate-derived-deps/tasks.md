## 1. Specs / Schema

- [ ] 1.1 同步 `outputs.*.aggregate.fields.*` 的新能力到 schema/hover(SSOT: `src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`; 生成入口: `just gen-docs`; 验收: `just qa`)
- [ ] 1.2 在 schema/hover 中明确 aggregate DAG 语义: 引用范围、执行顺序(依赖驱动)、循环依赖诊断与 top_k 的阶段化行为(SSOT 同上; 验收同上)

## 2. YAML 解析与编译期校验

- [ ] 2.1 增加 `aggregate.fields.*.compute: <expression>` 解析与校验(安全表达式引擎 + 依赖提取; 验收: gap01/03 MRE 编译通过)
- [ ] 2.2 放开 `rank.by`/`rank.order_by` 引用范围: 允许引用 `aggregate.group_by` + `aggregate.fields` 任意字段(含派生字段); 保持 `partition_by` 必须为 `group_by` 子集(验收: gap01/03 MRE 编译通过)
- [ ] 2.3 放开 `call_by/compute` 对其它 post 字段的依赖(验收: gap02 MRE 编译通过)
- [ ] 2.4 为 aggregate fields 构建依赖图并做循环依赖检测,输出可操作错误(验收: 新增 cycle 测试用例)

## 3. Runtime 规格编译(从 YAML config → IR/execution spec)

- [ ] 3.1 为 aggregate 引入可执行的“finalize DAG 计划”(稳定拓扑序 + 依赖列表),并纳入 fingerprint 以确保缓存/复现稳定(验收: tests + deterministic ordering suite)
- [ ] 3.2 为 `compute` 字段编译 calculator(复用 `SecureComputeEngine`),并作为聚合后派生字段的一种 producer(kind=compute)(验收: 单测覆盖)

## 4. Derived Outputs 执行语义升级

- [ ] 4.1 将 `RankedGroupByAggregator.finalize_rows` 从固定顺序升级为依赖驱动执行: pre-rank 派生 → rank → top_k/sort → remaining 派生(验收: gap01~03 运行用例 + 输出稳定性断言)
- [ ] 4.2 保持 `top_k` 与输出稳定排序的既有语义(尽量不引入破坏性行为变化); 若不可避免,在错误/文档中明确说明(验收: 既有 e2e tests 不回退)

## 5. Tests / Docs / Gates

- [ ] 5.1 基于 `.tmp/downstream_report/mre/gap01~03_*.yaml` 增加测试覆盖(建议用 `tests.yaml_fixtures.make_yaml_config` 生成等价 YAML,避免依赖 `.tmp` 路径); 验收: pytest
- [ ] 5.2 增加 aggregate DAG 的单测: rank-by-compute, post-depends-on-post, rank-after-post, cycle detection, topo order 稳定性; 验收: pytest
- [ ] 5.3 运行 `just gen-docs` 刷新生成物(若有)并通过 `just qa` 门禁; OpenSpec 工件通过 `just openspec-check`
