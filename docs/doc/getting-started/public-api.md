# 公共 API 导入指南

??? note "适用读者"
    - 使用方:在 Python 里调用 Scalim,希望导入路径稳定、可回归
    - 贡献者:需要扩展/治理 public API,避免“看起来能 import 但其实是内部实现细节”

本仓库将“public API”定义为:用户在 Python 侧可稳定导入、并被回归门禁覆盖的一组 `scalim.*` 模块与符号。
核心约束来自三处(约定优先):

- `__all__` 治理规则(模块内符号级): [`scripts/check-api-surface-governance.py`](#code=scripts/check-api-surface-governance.py)
- 用户材料导入边界(文档/示例/skills): [`scripts/check-user-material-import-boundaries.py`](#code=scripts/check-user-material-import-boundaries.py)
- 示例覆盖(可交互/可对拍): `notebooks/marimo/example_public_api_suite/`(见 [主线教程](demo-big-data-report.md))

## 1) 推荐导入（Tier 1:稳定入口）

下表中的模块是我们在文档中明确推荐的稳定入口(约定):优先从这些 facade 模块导入,避免引用内部实现细节。

| 模块 | 说明 | 常见场景 |
| --- | --- | --- |
| `scalim.dsl.by_yaml` | YAML DSL 官方运行入口 + 运行期契约 | 运行 demand/workflow YAML |
| `scalim.dsl.by_yaml.tools` | YAML DSL 辅助工具(输出配置/路径推导) | 工具链集成/排错 |
| `scalim.dsl.by_yaml.workflow` | workflow 配置(稳定导入路径) | 解析/校验 workflow YAML |
| `scalim.dsl.by_yaml.workflow_types` | workflow 类型(拆分给 typing/依赖方用) | 仅用类型,或避免重导入 |
| `scalim.dsl.by_yaml.workflow_paths` | workflow 路径解析(稳定导入路径) | 解析 workflow 引用的 demand 路径 |
| `scalim.spec.ir` | IR(中间表示)数据结构(稳定导入路径) | 写自定义组件/扩展点/高级调试 |
| `scalim.workflow.loaders` | workflow 内置 loader 的上下文与实现 | 在自定义 loader/运行器中复用 |
| `scalim.planning` | 规划层入口 | 规划/编排/可视化分析 |
| `scalim.execution` | 执行层入口 | `ScalimEngine` 执行 |
| `scalim.ob` | 可观测性入口 | 构建 observer manager / 采集事件 |
| `scalim.events` | 事件 envelope + 事件类型常量 + 事件目录查询入口 | 写 Observer/Hook；按 `event_type` 订阅/过滤 |
| `scalim.sinks` | sink 契约与常用 sinks | 使用内置 sinks / 实现自定义 sink |
| `scalim.sinks.rows` | workflow typed rows artifact 稳定入口 | `InMemoryRows` 中间态 / 转换与适配 |

最常见的“只关心导入”的用法:

```python
from scalim.dsl.by_yaml import RunOverrides, compile, run, run_workflow
```

需要工具链能力(例如输出配置/基准路径推导)时:

```python
from scalim.dsl.by_yaml.tools import derive_base_module_path, load_output_config
```

需要 workflow 配置类型/校验能力时:

```python
from scalim.dsl.by_yaml.workflow import WorkflowConfig, load_workflow_config
```

需要 IR(中间表示)类型时,推荐“模块导入”减少符号级耦合:

```python
from scalim.spec import ir as ir
```

需要事件常量/目录查询入口时:

```python
from scalim.events import Event, EVENT_PIPELINE_START, get_event_catalog
```

需要常用 sinks 时:

```python
from scalim.sinks import CSVSink, InMemoryRowSink
```

需要 workflow typed rows artifact (`InMemoryRows`) 时:

```python
from scalim.sinks.rows import InMemoryRows, InMemoryRowsSink
```

## 2) 其它可用导入（Tier 2:可用但不在稳定白名单）

这些模块当前也对外导出了 `__all__`,但**不在 Tier 1 curated 白名单**内:适合高级用户/贡献者使用,但不建议“把它当成稳定入口依赖”。
如果你确实需要依赖它们,建议:

- pin 版本 + 自己维护回归(尤其是导出面较大的模块)
- 优先通过更上层的稳定入口间接使用(例如优先用 `scalim.dsl.by_yaml.*`)

常见的 Tier 2 模块(非穷举):

- `scalim.exceptions`:异常 taxonomy
- `scalim.hooks`:hook 扩展点导出
- `scalim.planning`:计划/编排相关导出
- `scalim.execution`:执行相关导出
- `scalim.ob`:observer 相关导出

## 3) 治理与验收（对贡献者）

### 3.1 `__all__` 的含义

- 对外“公开导出”的 **符号级契约**: `from <module> import <name>` 的稳定集合
- 要求 **显式** 定义,避免“无意暴露内部实现”

### 3.2 治理脚本:禁止隐式暴露内部模块

`scripts/check-api-surface-governance.py` 强制:

- `__all__` 不得导出(非 dunder 的) `_name`
- `_internal/` 与 `_*.py` 这类内部实现模块必须显式 `__all__ = []`(或 `()`)封堵导出面

### 3.3 如何自查

```bash
python3 scripts/check-api-surface-governance.py --check
python3 scripts/check-user-material-import-boundaries.py --check
pytest -q tests/public_api/test_example_public_api_suite.py --no-cov
just qa
```

## 4) 结构评估与打分（阶段性）

**综合评分: 9.1/10**

理由(摘要):

- 优点:Tier 1 入口清晰,有 `__all__` 白名单 + gate,回归成本低
- 优点:YAML DSL 运行入口(`scalim.dsl.by_yaml`)与 workflow/IR 的稳定导入路径已明确拆出
- 代价:仍有部分 Tier 2 模块导出面偏大/偏“平铺”,但它们不在 curated 白名单内；若需依赖建议自行 pin 版本并维护回归

导出规模不在文档里维护数值快照:以 `__all__` 治理规则 + 示例覆盖为准。

## 5) 代价与优化方向（Brainstorming）

这里的“优化”指结构与治理成本,不是添加新功能。

### 5.1 主要代价点

- 部分 Tier 2 模块的导出面仍可能偏大且平铺:
  - 使用方容易“随手 import 一个看起来能用的符号”并形成隐式依赖
  - 贡献者很难判断“删/改一个符号是否 breaking”

### 5.2 可选优化方向（不落地,仅用于评估）

1) **文档侧收敛(最低成本)**:保留现状,但把“推荐导入组合”写清楚,并将 Tier 2 明确标为高级入口(本页已做)。
2) **引入更细粒度稳定子模块(中成本,可能 breaking)**:为部分高 churn 的 Tier 2 领域引入稳定分组模块,并把推荐导入从“平铺符号”转向“分组模块”。
3) **收窄导出面(高成本,明确 breaking)**:对代表性的大导出面模块做显式收敛,只保留“长期承诺”的符号;该方向建议用 OpenSpec 变更管理并配合版本策略,避免静默破坏下游。
