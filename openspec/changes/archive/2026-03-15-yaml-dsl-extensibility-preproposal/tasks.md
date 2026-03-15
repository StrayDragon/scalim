**状态: ✅ Review & Split 完成(实现已拆分为独立 changes)**

## 1. Review & Split (pre-proposal)

- [x] 1.1 Review `proposal.md` for full-scope acceptance (BUNDLE + ANALYZE + direct config)
- [x] 1.2 Confirm YAML shape and naming (`bundles/analyze/compute/components/outputs/aggregates/transform`)
- [x] 1.3 Confirm conflict policy defaults and required diagnostics
- [x] 1.4 Split implementation into multiple OpenSpec changes with clear dependency order

### Split Result (SSOT)

推荐依赖顺序(从底座到功能面):

1) `yaml-dsl-extensions-schema`
2) `yaml-dsl-extensions-host-core`
3) `yaml-dsl-extensions-transformers`
4) `yaml-dsl-extensions-compute`
5) `yaml-dsl-extensions-output-format-registry`
6) `yaml-dsl-extensions-custom-aggregates`
7) `yaml-dsl-extensions-analyze-cli`

实现任务已迁移到上述 changes 的 `tasks.md`(后续以拆分后的 changes 为 SSOT):

- schema: `openspec/changes/yaml-dsl-extensions-schema/tasks.md`
- host: `openspec/changes/yaml-dsl-extensions-host-core/tasks.md`
- transformers: `openspec/changes/yaml-dsl-extensions-transformers/tasks.md`
- compute: `openspec/changes/yaml-dsl-extensions-compute/tasks.md`
- output registry: `openspec/changes/yaml-dsl-extensions-output-format-registry/tasks.md`
- custom aggregates: `openspec/changes/yaml-dsl-extensions-custom-aggregates/tasks.md`
- analyze + CLI/docs: `openspec/changes/yaml-dsl-extensions-analyze-cli/tasks.md`

Notes:

- 本 preproposal 目录保留 `proposal.md`/`design.md`/`specs/**` 作为 umbrella reference。
- 实现 checklist 不再在此文件维护,避免与拆分后的 changes 重复/漂移。
