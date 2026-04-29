## 1. Module Split

- [x] 1.1 新建 `src/scalim/execution/output_composition/specs.py` 并迁移 spec dataclasses + fingerprint helpers
- [x] 1.2 新建 `.../output_composition/sinks.py` 并迁移 sink 创建辅助函数
- [x] 1.3 新建 `.../output_composition/router.py` 并迁移 `RouterRowSink` 与内部 routing state
- [x] 1.4 新建 `.../output_composition/build.py` 并迁移 `required_demand_fields`/`build_output_composition` 与 plan builder
- [x] 1.5 将 `src/scalim/execution/output_composition.py` 收敛为 facade: 仅 re-export 稳定符号并保持 `__all__`

## 2. Tests

- [x] 2.1 为 fingerprint helpers 增加 unit tests(确保拆出后可独立测试)
- [x] 2.2 跑全量现有测试确保无行为回归

## 3. Verification

- [x] 3.1 运行 `just qa`
- [x] 3.2 运行 `just openspec-check`
