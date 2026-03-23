## 0. Dependencies（SSOT 先行，降低改动半径）

- [ ] 0.1 确保 `ordered-unique-ssot` 已落地（`ordered_unique_str` SSOT 可复用），本变更的 Stage 4 去重保序逻辑必须复用该 SSOT
- [ ] 0.2 确保 `output-aggregate-producer-keys-ssot` 已落地（aggregate producer keys SSOT 已统一），避免 staged 拆分过程中同时搬迁常量与语义

## 1. Baseline Tests（先固化行为，作为重构护栏）

- [ ] 1.1 新增单测：`outputs.*.from` cycle 检测确定性（错误信息包含发生 cycle 的 output name）
- [ ] 1.2 新增单测：unknown `from` 必须 fail-fast（错误信息包含目标 name 与 from name）
- [ ] 1.3 新增单测：fields/container 的继承缺失（base output 无 fields 但子 output 继承 fields）必须 fail-fast

## 2. staged parsing 拆分（SSOT：outputs-parser-staged-design）

- [ ] 2.1 提取 Stage 2：name index + from resolver（DFS + visiting set）为独立函数/小类，并接入 `_parse_outputs`
- [ ] 2.2 提取 Stage 3：语义校验为独立函数（保留现有规则；避免在 `_parse_outputs` 中隐式传播状态）
- [ ] 2.3 提取 Stage 4：required_field_ids 计算为独立函数，并确保去重保序语义明确（可复用 ordered-unique SSOT）
- [ ] 2.4 缩减 `_parse_outputs` 为 glue：按顺序调用 staged functions；尽量移除复杂度豁免或将其局限在 glue 层

## 3. 模块组织与可测试边界

- [ ] 3.1 （可选）在 `parsers/` 下新增 `outputs_*` 子模块承载阶段化实现，避免单文件继续膨胀
- [ ] 3.2 新增 staged tests：分别对 Stage 2/3/4 做最小 fixture 覆盖（避免仅靠 e2e）
- [ ] 3.3 增加 1 个 e2e smoke：通过 `YamlDemandLoader`/`ConfigValidator` 解析包含 outputs 的最小 YAML，确保 glue 未破坏

## 4. Final Gates

- [ ] 4.1 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
- [ ] 4.2 运行 `just qa`（或最小子集）确保无 lint/test 回归
