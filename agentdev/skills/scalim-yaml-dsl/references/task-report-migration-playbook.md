# Report Migration Playbook

## 何时读取

- 用户要把旧批量报表脚本渐进迁移到 Scalim YAML DSL
- 用户强调“先做可对拍、可渐进替换、后续可继续收敛”
- 你需要判断哪些逻辑写进 YAML,哪些逻辑暂留 Python

## 场景定义

这是一个脱敏后的通用迁移场景,不是某个真实业务项目的复述。

如果需要举例,统一使用占位路径、占位 marker、占位模块名:

- 路径: `/path/to/report_task/__init__.py`
- marker: `__yaml_dsl_reimpl__`
- 模块: `myapp.bll.export_service:load_orders`

不要在 skill 文案或交付中复述真实项目名、绝对业务路径、私有模块名或私有 marker。

## 先做调研,不要先写代码

先分析:

1. 原入口脚本及其直接依赖
2. 主数据链路
3. 宽表结构
4. 聚合逻辑
5. 分 sheet 逻辑
6. 最终导出逻辑

重点判断:

- 是不是“大宽表 + 分组拆多 sheet”
- 是否依赖多轮 runtime state
- 是否需要 compare-friendly 双路由
- 哪些 loader 可以直接引用下游 BLL/服务方法
- 哪些逻辑超出 DSL 当前能力边界

## 迁移决策表

### 优先下沉到 YAML

- 主数据源定义
- 字段映射
- `sources`
- `relations`
- 顶层派生字段
- `outputs.*.fields` 的字段编排
- 可直接复用的 BLL/服务 loader 引用

### 先留在 Python

- 复杂 workbook 组装(例如跨 sheet 公式/样式/引用,或需要复用旧导出器能力)
- 多轮 runtime state / state map
- compare 路由
- 回滚观察逻辑
- 当前 DSL 无法自然表达的跨行/跨轮聚合
- 必要的最薄 loader 适配层

## 推荐结构

```text
report_task/
  __init__.py
  reimpl_scalim/
    __init__.py
    report_task.demand.yaml
```

默认目标是:

- `reimpl_scalim` 里只有一个 YAML 和一个 `__init__.py`
- 不默认拆 `_loaders.py` / `_helpers.py` / `_adapters.py`

## 路由策略

如果任务要求 compare 或渐进替换,可以保留最小双路由边界:

```python
def report_task(param, request):
    marker = "__yaml_dsl_reimpl__"
    values = list(getattr(param, "multi_search_list", []) or [])
    use_new = marker in values
    if use_new:
        values = [item for item in values if item != marker]
        param.multi_search_list = values
        return run_reimpl_scalim(param, request)
    return run_legacy(param, request)
```

要求:

- 只剥离 marker
- 正常输入值全部保留
- 只保留最小 legacy 路由边界

## Loader 选择策略

优先直接引用下游 BLL/服务方法:

```yaml
main_source:
  loader: "myapp.bll.export_service:load_orders"
```

只有在下面两种情况才加 Python 适配层:

- loader contract 不满足 YAML DSL 预期
- 需要补齐 DSL 暂不擅长的运行时上下文或状态

## 多 sheet 宽表场景

如果本质是“同一份宽表分发到多个 sheet”,优先直接用 YAML `outputs` 表达:

- 先用 YAML 描述整张宽表(字段/关联/派生字段)
- 用多个 `outputs` + `where` 分发到不同 sheet
- 多目标共享同一 workbook 时,为每个 output 显式设置 `to.book/to.sheet`;并发写同一 output root 依赖“版本目录隔离”(通过 `scalim.shortcuts.resources.outputs` 定位最新产物,或显式指定版本目录)
- 只有在需要复杂格式/样式/跨 sheet 自定义公式等能力时,才保留薄 Python 组装层

### 宽表峰值与 OutputWriteLayout / StreamingColumnExcelSink

- **SSOT**：站点 `docs/doc/getting-started/excel-column-residency.md`（选型 / 正确性 / 无 auto）；agent 边界见 `references/streaming-column-excel-guidance.md`；upgrade 卡 `references/upgrades/2026-08-11-output-write-layout.md`。
- YAML/workflow Excel **不会**自动使用 `StreamingColumnExcelSink`(组合层是行 sink)。
- 砍列 hold 的 `pre_close` 峰 → Python **`OutputWriteLayout.COLUMN_WINDOW`**（或手写 sink）；不要在 YAML 加 streaming / layout knobs。
- shared-book 物化峰值是另一条线(futures spill),与本 sink 解耦。

## 方案阶段输出要求

在真正实现前,先明确:

- 哪些逻辑保持不动
- 哪些逻辑迁到 YAML
- 哪些逻辑暂留 Python
- 为什么暂留 Python
- 如果 DSL 能力补齐,下一步怎么继续下沉

如果发现能力缺口,同时给出:

- 临时 patch 方案
- 可接受的 hook / event 扩展点
- 值得向 Scalim 提需求的点

## 实施阶段约束

- 未明确要求兼容时,直接按新写法重构
- 如果任务目标是渐进对拍,只保留最小 compare 路由
- 输出接口优先保持稳定
- 优先给用户留下可复用模板,而不是临时拼接代码

## 校验与交付

至少完成:

```bash
uv run scalim-cli yaml-dsl schema validate <file.yaml>
uv run scalim-cli yaml-dsl validate <file.yaml>
```

交付时明确:

- 与原实现的关键差异
- 当前哪些地方仍留在 Python
- 为什么这种拆分适合渐进迁移
- 未来如何继续收敛到更纯的 Scalim 实现
- 缺失哪些运行环境依赖,导致哪些验证还没做

## 需要全量语法时

- [syntax-catalog.gen.md](syntax-catalog.gen.md)
- [generated/example-full/ecommerce_report.gen.yaml](generated/example-full/ecommerce_report.gen.yaml)
