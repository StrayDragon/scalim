## 1. 派生聚合配置与装配

- [x] 1.1 扩展派生聚合 spec: 支持 `group_by` / `dedup_by + group_by` / `two_stage_group_by`,并提供 `required_fields()` 与稳定指纹材料
- [x] 1.2 将 `run_parallel_mode` 传入派生聚合装配路径,对不支持 `adaptive` 的配置做 fail-fast(含可操作错误提示)

## 2. `count_distinct`

- [x] 2.1 扩展 `AggMetricSpec` 以表达复合 key(例如 `field_ids`),并新增 `count_distinct` metric state
- [x] 2.2 增加 `max_distinct` 护栏与 `max_distinct=0` warn(不改变语义),并定义溢出策略(`error` 为默认;可选 `truncate` 需可对拍)
- [x] 2.3 单元测试: 单字段/复合字段 distinct、缺失值语义、护栏触发行为与确定性

## 3. `dedup_by`

- [x] 3.1 实现 `dedup_by(key_fields, on_conflict=error|first|last)` 阶段,并在 `first/last` + `adaptive` 时 fail-fast
- [x] 3.2 将 `dedup_by` 作为 group_by 指标计算的前置阶段接入派生输出,并补齐冲突策略与护栏测试

## 4. `two_stage_group_by`

- [x] 4.1 定义 stage1/stage2 spec,实现“stage1 finalize → stage2 accumulate”流水线并固定输出顺序/tie-break
- [x] 4.2 补齐 `adaptive` 一致性边界校验: 任一阶段含顺序依赖语义时 fail-fast
- [x] 4.3 为 `repeat_paid_users` 场景补齐最小条件计数能力(例如 `count_true_gte(field_id, threshold)`),并增加对应单元测试

## 5. 诊断与指纹(meta/audit)

- [x] 5.1 为每个 derived target 生成稳定聚合指纹(不包含 callables),并写入 meta sheet(`derived.<target_id>.*`)
- [x] 5.2 护栏触发/截断/失败时写入结构化 audit 行(避免敏感数据泄露),并确保 message hash 稳定可对拍

## 6. 质量门禁

- [x] 6.1 更新 delta spec: `openspec/changes/derived-outputs-set-aggregations/specs/derived-outputs/spec.md`(明确 determinism/guardrails/meta-audit 边界)
- [x] 6.2 将 delta spec 同步到主规范: `openspec/specs/derived-outputs/spec.md`(按 OpenSpec 流程,避免直接手改生成物)
- [x] 6.3 盘点下游适配与同步修改: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并列出需要同步的下游目录(输出/文档中不得引用文件内容)
- [x] 6.4 运行 acceptance demo: `openspec/changes/derived-outputs-set-aggregations/acceptance/mvp_demo/run_demo.py`(脱敏,对齐口径与产物)
- [x] 6.5 运行相关测试集并修复(建议从 `pytest -k derived_outputs or output_composition` 开始)
- [x] 6.6 运行 `just qa` 与 `just openspec-check`(归档前必做)
- [x] 6.7 归档到: `openspec/changes/archive/YYYY-MM-DD-derived-outputs-set-aggregations/`
