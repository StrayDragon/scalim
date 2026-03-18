## 1. 校验与依赖推导

- [ ] 1.1 更新 relation validator：在 `src/scalim/dsl/by_yaml/config_parsing/validators/relations.py` 允许 `from` 引用顶层 derived fields（仅 main_source 侧），并在 `to` 侧保持禁止。
- [ ] 1.2 实现 “pre-relation 可计算” 判定：在编译/校验阶段构建 `pre_ref_derived` 集合；当 derived 被 relation `from` 引用但不满足条件时 fail-fast，错误必须包含阻塞依赖链摘要。
- [ ] 1.3 回归 cycle detection：针对 derived↔relation 的环依赖提供更友好的报错（至少指出参与环的字段/step）。

## 2. 规划/执行顺序

- [ ] 2.1 修改 `src/scalim/planning/builder_helpers/operators.py`：在 `LOAD_REF` 之前插入 pre-ref derived 的 compute operators（保持拓扑序），确保 join key 在 LoadRef 前可用。
- [ ] 2.2 增加回归测试：验证在开启该能力时，LoadRef 的 lookup key 能读到 derived 值且结果正确（broadcast constant key 为最小用例）。

## 3. 规范与文档

- [ ] 3.1 更新增量规范 `openspec/changes/c40-relations-derived-from/specs/source-relations/spec.md`：定义允许范围、pre-ref 约束与场景。
- [ ] 3.2 （可选）在 YAML DSL user guide 增加一段“relation join key 的 derived 限制与示例”。

## 4. 门禁

- [ ] 4.1 运行 `just openspec-check` 确保 OpenSpec 工件结构与脱敏规则通过。
- [ ] 4.2 运行 `just qa`（至少覆盖 relations/plan builder 相关单测）确保无回归。

