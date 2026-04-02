## Context

关于 imports 的讨论,真正需要回答的不是“保留还是删除”,而是:

- demand authoring 还需要哪些可复用片段
- 哪些区域已经不再属于 YAML 主线,因此自然不该允许 `$import`
- workflow 是否要变成片段编排系统

在当前讨论中,已经有两点相对明确:

- demand 侧不应失去这项高价值复用能力
- workflow 不应扩张 imports expansion

因此这个 change 应聚焦于“scope boundary”,而不是重新争论 imports 是否存在。

## Goals

- 为 demand `imports` / `$import` 给出主线 authoring 允许范围
- 让 imports 规则与主线 DSL 收敛方向一致
- 避免 workflow 扩张出新的片段组合复杂度

## Non-Goals

- 不重新设计 imports expansion 算法
- 不替代 profile/preset 设计

## Current Direction

### 1. demand imports 保留,但只服务于 authoring 复用

当前结论已经比较明确:

- imports / `$import` 继续保留
- 它的目标不是 profile、preset 或 runtime control-plane
- 它的核心价值是跨文件共享 authoring 片段

这也与当前实现一致:

- imports 是编译前的文件片段展开
- `effective_yaml.py` 只负责把 demand YAML 渲染成展开后的 effective YAML
- `imports.py` 的能力重点是相对路径、`scalim.yaml` alias / allow-roots、trace 与错误定位

也就是说,imports 解决的是“如何复用配置片段”,不是“如何表达默认值覆盖策略”。

### 2. workflow 不引入 imports expansion

当前主线口径保持不变:

- workflow 作为 orchestration DSL,不承担片段编排系统角色
- workflow schema/runtime 也不应继续暴露 `$import`

这与 `c10` 已经接住的 schema/runtime 对齐问题一致: 当前 workflow loader / validator 并没有 imports expansion。

### 3. `resources.*` 仍有真实的跨文件复用价值

这里需要回答的核心问题是: `resources.*` 到底有什么值得 import 复用的内容。

结合当前代码与使用方式,典型复用场景至少有这几类:

- 多个报表共用同一类 Excel book 声明
  - 例如多个 demand 都输出到 `report` 这个 workbook id
  - 共享片段可统一 `kind: xlsx_file`、默认 `write_lock: true`、`allow_formulas: false`
- 多个报表共用同一类导出资源模板
  - 例如 `detail_csv`、`summary_csv` 这样的 file resource 片段
  - 共享 `kind: csv_file`、`encoding: utf-8`
- 多个报表共用同一类内存 workbook 预算
  - 例如 `xlsx_memory` 的 `budget.max_sheets/max_total_cells` 与 `export_xlsx`

一个直接例子是:

```yaml
imports:
  io: ./fragments/resources.yaml

resources:
  books:
    report:
      $import: io.report_book
  files:
    detail_csv:
      $import: io.detail_csv
```

其中 `./fragments/resources.yaml` 可以承载:

```yaml
report_book:
  kind: xlsx_file
  path: ./output/report.xlsx
  write_lock: true

detail_csv:
  kind: csv_file
  path: ./output/detail.csv
  encoding: utf-8
```

这类复用与 `meta/audit` 无关,也不依赖运行时 overlay 语义,因此它属于 imports 应继续支持的主线价值。

### 4. imports scope 只跟“是否仍属于 authoring surface”有关

因此本提案的推荐边界是:

- 允许 imports 进入 demand 的稳定 authoring 区:
  - `main_source`
  - `sources.*`
  - `fields.*`
  - `relations.*`
  - `resources.*` 中仍被认定为资源声明的部分
- 不允许 imports 继续进入明显的 runtime / control-plane 区:
  - `observability.*`
  - `guardrails.*`
  - `retry.*`
  - `batch_size`
  - workflow 任意节点

对 `resources.*` 的更细粒度限制,要跟 `c14` 的结论联动:

- 如果某一部分最终被明确归为 write-policy / runtime extras,它就不再属于 imports 主线覆盖范围
- 如果某一部分仍属于可移植资源声明,它就可以继续复用

### 5. `meta` / `audit` 不再主导 imports 规则

这里你的判断是对的:

- `meta/audit` 的问题本质是输出附加能力如何建模
- imports 的问题本质是跨文件共享哪些 authoring 片段

两者不是同一层级的问题。

因此本提案后续不会再以 `meta/audit` 作为 imports 策略的主要判断依据,而是回到更稳定的准则:

- 是否是 demand 主线 authoring
- 是否有真实的跨文件复用价值
- 是否会把 workflow / runtime policy 再次做大


## Dependencies

- 依赖 `c13-yaml-dsl-runtime-policy-boundary`
- 依赖 `c14-yaml-dsl-write-policy-and-output-extras`
- workflow imports 的禁止口径还应参考 `c10-yaml-dsl-schema-workflow-alignment`
