# demo_big_data_report 的 Marimo Notebook 章节化重组：功能点扫描 → 章节划分 → shared 下沉建议

> 前提约束(用户要求)：**必须保留** `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report*`(当前为 `ecommerce_report.yaml` + `ecommerce_report_fragments.yaml`)。
>
> 本文处于 `$openspec-explore`：只做**真值扫描 + 设计建议**，不直接落地改代码/改目录。若你确认要我动手实现，请切换到 `/opsx:new` 或 `/opsx:ff`。

---

## 0) 基线事实(当前仓库真值)

### 0.1 demo_big_data_report 的“可运行真相源”(SSOT)已经分层

- Marimo UI(目前只有 1 本)：`notebooks/marimo/demo_big_data_report/demo_main.py`
- Headless gate(与 CI 一致)：`notebooks/marimo/run_examples.py` → `scalim_misc.demo_big_data_report.chapters.registry:run_all_chapters`
- 章节实现 SSOT(可复用、可对拍)：`packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/*.py`
- canonical YAML(被脚本/测试/文档引用)：`notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
  - 跨文件片段：`notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report_fragments.yaml`

### 0.2 当前 `demo_main.py` 的内容形态(为什么不利于“章节教学”)

`notebooks/marimo/demo_big_data_report/demo_main.py` 现在做三件事：

1) 演示 YAML 校验/加载( `ConfigValidator` + `YamlDemandLoader` )  
2) 一键跑完所有章节(表格只展示 `chapter_id/passed/summary` 的第一行)  
3) 演示 `scalim.dsl.by_yaml.run()`(保留为 skill 片段)

它更像“总入口 + gate 摘要”，但**每个能力点**(relations / outputs / observability / workflow / guardrails …)都被折叠成了一行 summary，读者要深入只能跳到 `scalim-misc` 章节源码看实现。

---

## 1) 功能点扫描(从“文档 + canonical YAML + 章节实现”抽取)

本节只列“demo_big_data_report 这一条主线确实暴露出来的能力点”，并把每个能力点落到：

- 文档入口(帮助读者读)  
- YAML 示例位置(帮助读者看配置长相)  
- 实现入口(帮助贡献者定位)  
- 章节/回归覆盖点(帮助你决定 notebook 如何切章)

### 1.1 YAML DSL：结构/复用/引用/关系/参数模板/输出/观测

| 能力点 | 文档入口 | 示例(真值) | 关键实现入口 | 现有回归/章节 |
| --- | --- | --- | --- | --- |
| schema vs validator 两层事实来源 | `docs/doc/yaml-dsl/syntax.md`(1,8) | `demo_main.py` 里直接调用 validator/loader | `src/scalim/dsl/by_yaml/config_parsing/validator.py` | `scalim_misc...chapters/yaml_dsl.py::run_yaml_dsl` |
| imports / `$import`(V1 同级文件限制) | `docs/doc/yaml-dsl/syntax.md`(3.4) | `ecommerce_report.yaml: imports:` + `main_source.params.$import` → `fragments.main_source_params` | `src/scalim/dsl/by_yaml/config_parsing/imports.py::load_and_expand_imports` | `run_yaml_dsl` 会 `load_and_expand_imports(yaml_path)` |
| YAML anchors/alias/merge(复用) | `syntax.md`(3) + `user-guide.md`(4.1) | `ecommerce_report.yaml: _templates` + `<<:` + `*alias` | **YAML 本身**(PyYAML)；框架只吃结果 | `run_yaml_dsl`(间接覆盖) |
| Python 引用 + allowlist 安全边界 | `syntax.md`(4) + `user-guide.md`(1.3/6.4) | `loader:` / `call_by:` 指向 `scalim_misc...loaders:*` | `src/scalim/dsl/by_yaml/runtime/compiler.py`(ensure allowlist) | `run_yaml_dsl` / `demo_main.py` |
| relations: 单级/多级/复合键 steps | `syntax.md`(5) + `user-guide.md`(3.5) | `ecommerce_report.yaml: relations:`(含复合键 `from/to: [..]`) | `src/scalim/dsl/by_yaml/runtime/_internal/conversion_relations.py`(路径随实现可能不同，以搜索 `RelationIr` 转换为准) | `scalim_misc...chapters/diagnostics.py`(统计) + `yaml_dsl`(端到端) |
| `lookup_cast` | `user-guide.md`(3.3.3/4.3) | `ecommerce_report.yaml: relations.*.steps[*].lookup_cast` + `sources.products.lookup_cast` | `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`(cast 编译) | `yaml_dsl`(端到端) |
| `lookup_chunk_size` | `user-guide.md`(sources) | `ecommerce_report.yaml: sources.customers.lookup_chunk_size: 5` | ref loader 调度 + chunking(执行层) | `yaml_dsl`(端到端) |
| params 模板：`$keys` | `syntax.md`(6) + `user-guide.md`(4.2.1) | `ecommerce_report.yaml: sources.*.params.ids: {$keys: {as: list|set}}` | `src/scalim/dsl/by_yaml/params_template.py` | `yaml_dsl`(端到端) |
| params 模板：`$rows`(batch/none) + rows barrier | `syntax.md`(6) + `user-guide.md`(4.2.2/6.3) | `ecommerce_report.yaml: customers_rows_cached/..nocache params.rows {$rows:{cache_mode:...}}` | `src/scalim/dsl/by_yaml/params_template.py` + 执行调度器对 `$rows` 的处理 | `scalim_misc...chapters/yaml_dsl.py` 对拍 `rows_*_match` 字段 |
| `cache_mode: preload_forever` | `user-guide.md`(4.4.2) + `workflow.md`(4) | `ecommerce_report.yaml: region_pricing/promotions/payment_methods/...` | pipeline preload：`src/scalim/execution/pipeline/base/pipeline.py` | `diagnostics.py`(cached_sources 统计) + `workflow_yaml.py`(share_preload_cache) |
| source normalize: `index_by_key` / `map_values`(take_first/project_fields/from_key) | `user-guide.md`(3.3.4) | `ecommerce_report.yaml: payment_methods.normalize` + `payment_methods_candidates.normalize` | `src/scalim/spec/ir/sources.py::SourceNormalizeIr` + 执行期 `apply()` | `yaml_dsl`(端到端) |
| derived fields: `compute`(安全表达式) | `user-guide.md`(3.4.2) | `ecommerce_report.yaml: fields.order_amount/tax_amount/no_promotion/... compute:` | `src/scalim/dsl/by_yaml/config_parsing/security.py::SecureComputeEngine` | `yaml_dsl`(端到端) |
| derived fields: `call_by`(函数调用) | `syntax.md`(4) | `ecommerce_report.yaml: fields.profit/final_price call_by:` | reference resolver + allowlist | `yaml_dsl`(端到端) |
| composed outputs(workbook) + where + aggregate + meta/audit | `syntax.md`(7) + `user-guide.md`(4.5) | `ecommerce_report.yaml: outputs/meta/audit` | `src/scalim/execution/output_composition.py` + by_yaml 编译层 | `scalim_misc...chapters/output_composition.py`(IR 侧对拍) + `yaml_dsl`(YAML 侧 smoke) |
| YAML observability: performance/relations report | `user-guide.md`(3.7.*) | `ecommerce_report.yaml: observability.performance/relations` | `src/scalim/dsl/by_yaml/runtime/observability.py`(编译) | `scalim_misc...chapters/observability.py`(Python 侧对拍) |

> 纠偏(真值)：当前 `ecommerce_report_fragments.yaml` 仅包含 `main_source_params`，并不包含 normalize 等片段；normalize 在 `ecommerce_report.yaml` 内部直接声明。

### 1.2 Workflow：多 run 编排 + share_preload_cache 的可观察断言

- 文档入口：`docs/doc/yaml-dsl/workflow.md`
- fixture 真值：
  - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_fixture.yaml`
  - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/workflow_fixture_demand.yaml`
- 回归 SSOT：`packages/scalim-misc/src/scalim_misc/demo_big_data_report/chapters/workflow_yaml.py`
  - 可观察点：`run_ids == ["r1","r2"]` + `preload_calls == 1` + `errors == []`

### 1.3 Execution/Planning/Sinks/Parallel/Observers/Guardrails/Retry：非 YAML 但属于“框架能力章节”

这些能力点不一定在 canonical YAML 中出现，但确实是 demo 主线“暴露出来的框架能力”：

- IR→Plan→Engine 最小主线：`chapters/basics.py`
- 多 sink 与 CSV 对拍：`chapters/sinks.py`
- 并发模式一致性：`chapters/parallel_mode.py`
- 可观测性预置(Performance/Trace/RowGap)：`chapters/observability.py`
- 内存优化 observer + 列式写入事件：`chapters/memory_opt.py`
- 诊断：对 IR 做静态统计：`chapters/diagnostics.py`
- Guardrails：quiet/fast_fail + 错误事件收集：`chapters/guardrails.py`
- Loader retry：YAML `retry` + 注入 `LoaderRetryPoliciesSpec`：`chapters/loader_retry.py`
- 输出编排/派生汇总(IR 侧)：`chapters/output_composition.py` → `derived_outputs_demo.py`
- 派生聚合 set 口径(IR 侧)：`chapters/derived_set_aggregations.py` → `derived_set_aggregations_demo.py`

---

## 2) Marimo Notebook 章节化：两种组织方案(建议先选)

### 方案 A(推荐)：1:1 对齐现有 `run_*()` 章节(“UI 薄封装”，与 gate 同源)

优点：
- 章节的“真相”依旧在 `scalim-misc`，Marimo 只是展示层，不会产生第二套真相
- `just examples` 失败时，你可以直接打开对应章节 notebook 做交互排查
- 最小改动：基本不需要调整现有章节实现/runner

代价：
- notebook 数量较多(目前 `registry.py` 有 12 个章节)

建议目录结构(不破坏现有入口)：

```text
notebooks/marimo/demo_big_data_report/
  demo_main.py                     # 保留：总入口/总览/跑全量
  chapters/
    01_basics.py
    02_yaml_dsl.py
    03_workflow_yaml.py
    04_sinks.py
    05_memory_opt.py
    06_observability.py
    07_parallel_mode.py
    08_diagnostics.py
    09_guardrails.py
    10_loader_retry.py
    11_output_composition.py
    12_derived_set_aggregations.py
  by_yaml_dsl/                      # 保留：canonical YAML + fixtures
    ecommerce_report.yaml
    ecommerce_report_fragments.yaml
    workflow_fixture.yaml
    workflow_fixture_demand.yaml
```

### 方案 B：按“文档章节/读者心智”切(更适合教学，但不完全对齐 gate)

例如把 YAML DSL 单独拆成 3–4 本：

- `yaml_dsl_01_validate_and_compile`：schema/validator/imports/allowlist
- `yaml_dsl_02_relations_and_params`：relations/$keys/$rows/cache_mode/normalize
- `yaml_dsl_03_outputs_and_observability`：outputs/meta/audit/observability
- `workflow` 单独一本

优点：更像教程；每本更聚焦。  
代价：你需要决定“章节 SSOT”是继续复用现有 `run_yaml_dsl` 还是把它也拆成多个可回归子章节(否则 notebook 会再长出来一套逻辑)。

---

## 3) 每章 Notebook 的“写作模板”(建议固定，不然会再次碎片化)

每本 notebook 建议包含固定段落(读者体验 + 调试体验更稳定)：

1) **本章目标/覆盖点**(3–6 个 bullet，明确“看完会什么”)  
2) **真相源在哪里**(列出 `scalim-misc` 章节函数路径)  
3) **如何在 gate 里运行**：`just examples` + “如何只跑这一章”(直接调用 `run_*()` 的小 snippet)  
4) **核心代码推演**：展示 1 条最小调用链(例如 `PlanBuilder`/`ScalimEngine`/`run_yaml`)  
5) **结果展示**：把 `ChapterResult.summary/details` 结构化展示(表格 + 关键字段)  
6) **失败定位**：常见失败原因 + 去哪里看(实现文件/validator 错误/allowlist 等)

> 关键约束：notebook 不应保存“新的业务实现逻辑”。它只应调用 `scalim-misc` 的 SSOT 函数，然后把结果讲清楚。

---

## 4) shared 下沉到 `packages/scalim-misc` 的建议(让 notebooks 极薄)

目标：让每个 notebook 只剩 “markdown + 调用 + 展示”，避免复制粘贴。

建议新增(或抽取)的 helper 类型(均应 **不 import marimo**，以免 headless runner 被 UI 依赖污染)：

1) **路径/环境 helper**(避免每本 notebook 写一遍 sys.path hack)
   - `scalim_misc.notebook_support.pathing::ensure_repo_root_on_sys_path(__file__)`
   - `scalim_misc.notebook_support.paths::demo_big_data_report_yaml_path(__file__)`

2) **ChapterResult 展示适配**
   - `scalim_misc.demo_big_data_report.notebook_view::chapter_result_to_rows(result)`(把 details 展成 key/value 行)
   - `scalim_misc.demo_big_data_report.notebook_view::summarize_chapter_result(result)`(短摘要)

3) **YAML 片段提取(只为讲解/展示)**
   - `scalim_misc.notebook_support.yaml_excerpt::excerpt(path, start_regex=None, end_regex=None, max_lines=...)`
   - 或基于 YAML path 的 subtree dump：`extract_yaml(path, dotted_path="sources.payment_methods.normalize")`

4) **“只跑一章”的最小可运行入口**
   - 让每章 notebook 不需要知道 `build_test_config_small()` 等配置细节：
     - 例如为每个章节暴露 `run_*_default()`(内部用 `build_test_config_small`)  
     - 或提供 `registry.get_default_inputs()` 返回 cfg/targets/yaml_path

> 注意：`packages/scalim-misc` 已经是 scripts/tests 的依赖面(例如 doc 注入与 skill 生成)。因此这里的 helper 要尽量“纯、稳、无外部依赖”。

---

## 5) 删除/迁移影响(你后续真要精简时会踩的坑)

### 5.1 你可以删掉“UI notebook”，但不能先删 canonical YAML

`ecommerce_report.yaml` 的引用半径很大(脚本/测试/文档/技能生成)，详见 `_X/04-notebooks-and-examples.md` 中的引用点汇总。

因此本次“章节化重组”建议：

- **先新增** chapter notebooks(不改旧路径)，保持 docs/just/test 全部稳定  
- 再考虑是否把 `demo_main.py` 降级为纯 index/hub  
- 最后若要删 notebooks 目录：先迁移 canonical YAML 到 `examples/` 并全仓替换引用点(这是另一条工作流)

### 5.2 如果你重命名/移动 `demo_main.py`，需要同步更新

- `docs/doc/getting-started/demo-big-data-report.md`(marimo 教程入口写死)
- `justfile: notebook` recipe(目前直接运行 `demo_main.py`)
- 可能还有存在性测试：`tests/test_notebook_examples_readme_paths.py`(如仍约束这些路径存在)

---

## 6) 下一步(你确认后我再落地)

你只需要选一个方向：

1) **按现有章节 1:1 拆 notebook(推荐)**：我会新建 `notebooks/marimo/demo_big_data_report/chapters/*.py`，并把 `demo_main.py` 改成 hub(保留 skill markers)。
2) **按教学心智重切章节**：我会先给出新的章节目录与覆盖矩阵(哪些能力点在哪本)，再决定是否需要拆分 `scalim-misc` 章节 SSOT。

如果你希望我直接实现，请退出 explore：`/opsx:new marimo-demo-big-data-report-chapters`(逐步) 或 `/opsx:ff marimo-demo-big-data-report-chapters`(快速生成工件后实现)。

