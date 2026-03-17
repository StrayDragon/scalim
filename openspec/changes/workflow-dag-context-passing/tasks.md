## 1. Schema & Config Model

- [ ] 1.1 扩展 workflow JSON Schema: `workflow.runs[*].depends_on`/`workflow.runs[*].runtime_vars`(与 `$ctx` 引用节点)并保持旧配置兼容
- [ ] 1.2 扩展 `WorkflowRun`/`WorkflowConfig` 模型与解析器,并增加语义校验错误路径(例如 `workflow.runs.3.depends_on`)
- [ ] 1.3 补齐启动前 fail-fast 校验: 依赖引用存在/不自依赖/无环(cycle detection)并提供可读的错误信息

## 2. DAG Scheduler

- [ ] 2.1 在 `run_workflow` 引入 DAG 调度器: 依赖满足才入队,就绪队列按声明顺序稳定选择
- [ ] 2.2 定义并实现 DAG 场景下 `failure_policy=all_fail|primary_only` 的取消/跳过语义(依赖失败导致下游 cancelled)
- [ ] 2.3 保证返回 `outcomes` 顺序与 `workflow.runs` 声明顺序稳定对齐,并为 cancelled 提供可检查的错误摘要

## 3. ctx Store & runtime_vars Injection

- [ ] 3.1 定义 ctx 的最小契约(自动暴露字段集合/JSON-like 约束/size guardrails)并在实现中统一校验
- [ ] 3.2 实现 `$ctx` 引用节点的解析与错误诊断(缺失 key/上游未成功/路径非法)
- [ ] 3.3 实现 run-scoped runtime_vars 与 Python 入口 `runtime_vars` 的合并规则(建议 run-scoped 覆盖同名 key)
- [ ] 3.4 将 demand 编译改为“run 就绪后再编译”,确保 `$runtime` 在编译期能拿到最终注入值

## 4. share_preload_cache Interactions

- [ ] 4.1 定案 `share_preload_cache` 与 `$ctx` runtime_vars 的组合语义(增量预检查 vs 约束组合),并同步到 delta spec/主规范
- [ ] 4.2 按定案方案实现/调整 preload 规格冲突校验的触发时机与错误信息

## 5. Tests

- [ ] 5.1 `depends_on` 解析与校验测试(未知引用/自依赖/cycle)
- [ ] 5.2 并发下依赖调度测试(确保依赖完成前不启动下游)
- [ ] 5.3 outcomes 顺序稳定测试(与声明顺序对齐)
- [ ] 5.4 ctx → runtime_vars 注入集成测试(上游输出路径注入下游 loader params)
- [ ] 5.5 `failure_policy` + 依赖取消语义测试(all_fail vs primary_only)
- [ ] 5.6 `share_preload_cache` 与 DAG/ctx 组合场景测试(按定案语义)

## 6. Docs / Demos / Gates

- [ ] 6.1 更新 `docs/doc/yaml-dsl/workflow.md` 增加 DAG/ctx 写法与示例,并按 SSOT 规则运行 `just gen-docs`
- [ ] 6.2 若 schema 变更影响 editor/前端,同步生成并校验 workflow schema 的分发文件(按既有脚本与漂移门禁)
- [ ] 6.3 覆盖并回归 canonical demo: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`(如语义/字段影响到 workflow authoring)
- [ ] 6.4 通过门禁: `just qa` + `just openspec-check`

