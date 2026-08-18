# Tasks: 图存 source_id，策略只住目录

机械面（`to_source` → `to_source_id` 横扫测试）按「先契约与 intern，再机械改名」排，不强行垂直切片。不留 `to_source` 双字段。

Seam（已确认）：YAML `DemandRunOptions` + run；`DemandIr.from_irs`；ch164 不回退。无 `.feature` / 无 `bdd:`。RowsReuse 黑盒用 pytest，不加新 marimo 章。

## 0. Specs landing（propose / 绑定分支，apply 前）

- [ ] 0.1 `change start` 后改 `ir-source-relations` r694：signature 用 `to_source_id` + catalog binding；图 MUST NOT 嵌 live `SourceIr`
- [ ] 0.2 同一 spec 或新 `ir-source-catalog`：overlay 只写 `DemandIr.sources`；新 overlay 不得进 `LookupStepIr`/`FieldIr`
- [ ] 0.3 `yaml-dsl-runtime-policy-boundary` r1004：不改优先级句子；场景继续要求 Python `RowsReuse.none()` 禁用批次内复用（执行兑现由 task 2）
- [ ] 0.4 commit specs（Specs landing）。DoD: `llman sdd show c50-source-id-graph-refs --json` → `readyToImplement=true`

## 1. 失败黑盒先挂上（当前 API 即可）

- [ ] 1.1 pytest：YAML `$rows.cache_mode: batch` + `RowsReuse.none()`，两字段同一 rows relation，断言 **两次** loader miss（不得被 `load_ref_group_executed` 跳过）。DoD: **在 intern 落地前失败**（证明 r1004 缺口）
- [ ] 1.2 反向：YAML `none` + `RowsReuse.batch()` → 同 relation 一次逻辑 load。DoD: intern 前亦可能失败；intern 后必须绿
- [ ] 1.3 禁止只 assert `demand_ir.sources[].bind.cache_mode`

## 2. IR + intern + catalog 读点（一次切换，无双字段）

- [ ] 2.1 `LookupStepIr.to_source_id: str`；`FieldIr.source_id: str`；`get_to_key_or_source_key` 在 `to_field is None` 时要求 catalog
- [ ] 2.2 `DemandIr.from_irs` / YAML conversion 出口 intern：活 `SourceIr` 进 `sources`，图边只留 id；同 id 冲突 fail-fast
- [ ] 2.3 `resolve_step_binding(step, sources=...)`；pipeline / adaptive / load_ref executor / viz 传入 catalog；缺 id fail-fast
- [ ] 2.4 `resolve_lookup_source` **去掉** 嵌套句柄回退；改/删 `test_resolve_lookup_source_falls_back_to_nested_handle_when_catalog_empty`
- [ ] 2.5 `LookupSourceRefIrBase` 不再作为 step 字段类型；去掉其 overlay 字段或不再被图边实现
- [ ] 2.6 作者态 `RelationIr.infer_lookup_path` 仍吃活 `SourceIr`。DoD: task 1 黑盒绿；`test_apply_policies_updates_catalog_not_nested_field_handles` 改为 assert 图边是 id、与 catalog 非同一对象（无嵌套 SourceIr）

## 3. 机械改名调用点

- [ ] 3.1 `src/scalim/**`：`step.to_source` / `field.source.source_id` → id + catalog
- [ ] 3.2 tests / `scalim_misc.example_report_ir` / repro 脚本：`LookupStepIr(to_source=...)` → `to_source_id` + 显式 `sources=` 目录
- [ ] 3.3 DoD: 全库无 `LookupStepIr.to_source` 属性；`rg 'to_source=' src tests` 仅剩作者态 infer/join（若仍用参数名 `to_source` 表示活对象，与存盘字段分开）

## 4. 回归与文档

- [ ] 4.1 HANDOFF 复跑命令 + ch164 + ecommerce + big-data（miss/hit 拆开）全绿
- [ ] 4.2 skills / capability-matrix / user-guide：图边只存 id；新 overlay 加目录；指针到本 change
- [x] 4.3 删除 `notplan/source-catalog-ssot/`（内容已进本 change；勿留档 1/2/3）
- [ ] 4.4 `just gen-docs` 若触及注入块；禁止手改 `.gen.*`

## 5. 门禁

- [ ] 5.1 `just llmanspec-check`
- [ ] 5.2 相关 pytest 无回归；准备 `just qa`（verify）
