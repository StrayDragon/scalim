## 1. Schema & Config Model

- [ ] 1.1 设计并扩展 workflow JSON Schema: `workflow.resources`(workbooks/csvs) + `workflow.runs[*].write_to`(workbook_sheet/csv)并保持旧配置兼容
- [ ] 1.2 扩展 workflow 配置模型与解析器,补齐语义校验(资源 id 唯一/引用合法/字段组合合法/冲突策略枚举)
- [ ] 1.3 明确本 change 与 `c20-workflow-dag-context-passing` 的依赖关系,并在实现中复用同一套 DAG 调度/确定性顺序

## 2. Resource Runtime (Workbook / CSV)

- [ ] 2.1 抽象 workflow-scope 资源容器接口: create/open → write/append → commit(原子替换) / discard(失败丢弃)
- [ ] 2.2 workbook: 复用 `ExcelWorkbookSink`,补齐“失败时 discard/不落盘”的控制能力(必要时新增 wrapper)
- [ ] 2.3 csv: 提供可多段 append 的容器(支持 header 策略与原子替换);避免为每段单独落盘并覆盖
- [ ] 2.4 对同一资源的写入实现互斥/串行化,并将顺序绑定到 workflow 声明顺序

## 3. Workflow Runner Integration

- [ ] 3.1 将资源管理集成到 workflow runner: 对绑定 `write_to` 的 run,将其输出路由到共享资源 writer
- [ ] 3.2 定案并实现 demand YAML 中 `output/outputs` 与 workflow `write_to` 的交互策略(忽略/覆盖/报错/告警)
- [ ] 3.3 补齐 `failure_policy` 下的资源 commit/discard 行为(全失败丢弃 vs best-effort 保留)并提供可配置项

## 4. Merge Semantics

- [ ] 4.1 workbook_sheet: 支持 `mode=replace|append` 与 sheet 冲突策略(error/overwrite/skip 至少支持 error)
- [ ] 4.2 append: 实现 `align_by=strict_equal`(MVP)与 `header=once|never|each`(至少 once)
- [ ] 4.3 csv append: 字段对齐与 header 策略(至少 strict_equal + header once)

## 5. Tests

- [ ] 5.1 workbook 多 sheet 合并测试(最终只保存 1 个 workbook,且包含所有 sheets)
- [ ] 5.2 并发下写入互斥与确定性顺序测试(不依赖完成顺序)
- [ ] 5.3 append 合并测试(字段集合不一致 fail-fast;一致则追加成功)
- [ ] 5.4 failure_policy 下的 commit/discard 行为测试(all_fail vs primary_only)

## 6. Docs / Demos / Gates

- [ ] 6.1 更新 `docs/doc/yaml-dsl/workflow.md` 增加共享资源与写出示例,并运行 `just gen-docs`
- [ ] 6.2 覆盖并回归 canonical demo: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`(如 workflow authoring surface 受影响)
- [ ] 6.3 若 schema 影响 editor/前端,同步生成并校验 workflow schema 的分发文件(按既有脚本与漂移门禁)
- [ ] 6.4 通过门禁: `just qa` + `just openspec-check`
