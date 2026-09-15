# 主线教程: demo_big_data_report

??? note "适用读者"
    - 想快速跑通一条端到端 demo 的使用方/贡献者
    - 需要一个稳定入口来复现/对拍/排错的排查者

本仓库的 **唯一主线教程** 收敛在 `notebooks/marimo/demo_big_data_report/`。这里把“从哪里开始、怎么跑、怎么对拍、失败怎么定位”串在一页里，避免在 YAML DSL 文档、示例目录与 `just` 入口之间来回猜。

## 1) 关键入口(SSOT)

- marimo 教程入口(交互式): [`notebooks/marimo/demo_big_data_report/demo_main.py`](repo:notebooks/marimo/demo_big_data_report/demo_main.py)
- public API 面章节(同一套件内): [`chapters_of_ir/`](repo:notebooks/marimo/demo_big_data_report/chapters_of_ir)（`ch130`–`ch184`，与主线 `ch010`–`ch120` 同一 registry）
- `just examples` 集成对拍入口(headless/CI): `just examples`（入口实现位于 [`justfile`](repo:justfile) 的 `examples:` recipe）
- YAML DSL canonical example(SSOT): [`notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`](repo:notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml)

这些入口是“稳定入口”: 文档与回归门禁会围绕它们组织。

### 根 README 的「第一口」就在本主线内

根 `README.md` 的三个受控示例不再是独立套件，而是主线章节的投影（同一份真相）：

| README 区块 | 主线章节 SSOT |
| --- | --- |
| 可以用 Python 编写需求 | [`chapters_of_ir/ch010_basics.py`](repo:notebooks/marimo/demo_big_data_report/chapters_of_ir/ch010_basics.py)（可见 cells 逐 cell 投影为 fence） |
| 也可以用 YAML DSL 配置需求 | [`chapters_of_yaml_dsl/ch005_yaml_dsl_min.py`](repo:notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch005_yaml_dsl_min.py) + [`min_report.yaml`](repo:notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/min_report.yaml) |
| naive vs Scalim 内存对比 | [`chapters_of_ir/ch020_memory_compare.py`](repo:notebooks/marimo/demo_big_data_report/chapters_of_ir/ch020_memory_compare.py) |

注入器与图表生成器：`packages/scalim-misc/src/scalim_misc/readme_examples_gen.py` / `readme_charts_gen.py`；
刷新入口 `just gen-readme-examples`（或 `just gen-docs`），drift 由 `just qa` 内的 docs 检查兜底。

三条轨道(同一套件、同一个 `just examples` 入口):

| 轨道目录 | 编号 | 面 |
| --- | --- | --- |
| `chapters_of_yaml_dsl/` | `ch005`–`ch150` | 声明面: YAML DSL + workflow(含 README 第一口的 `ch005` 与 canonical `ecommerce_report.yaml`) |
| `chapters_of_ir/` | `ch010`–`ch120` + `ch130`–`ch184` | 装配面: Python IR 手写主线 + public API 覆盖(含 README 第一口的 `ch010`/`ch020`) |
| `chapters_of_scenarios/` | `ch210`–`ch260` | 场景面: hooks/events 与阶段调度的应用形态 |

- Python 导入入口与结构评估: [公共 API 导入指南](public-api.gen.md)
- `scalim.*.__all__` 的 Tier1 覆盖由 `chapters_of_ir/` 内的 `ch130`–`ch184` 承担；扩展点(hook/observer/events/components 注入)在同一批 cells 内演示, 不再有独立套件目录。
- 对拍零件与 loader 模块在 `packages/scalim-misc/src/scalim_misc/`(`notebook_support/*` + `demo_big_data_report/*`); 教学主流程全部在 cells 内。

## 2) 怎么跑(推荐命令)

### 2.1 跑示例 + 对拍(推荐;与 CI 一致)

```bash
just examples
```

该入口会执行唯一套件 `demo_big_data_report` 的三条轨道(声明面 + 装配面 + 场景面, 当前 52 章; 含 README 第一口的 ch005/ch010/ch020), 并输出可定位的 PASS/FAIL 摘要；这是 `just qa` 的一部分。只想跑单条轨道时可用 `SCALIM_EXAMPLES_SUITES=demo_big_data_report just examples`。

### 2.2 跑整套门禁(改动后验收)

```bash
just qa
```

## 3) 怎么看 YAML / Workflow / 编辑体验

本主线 demo 的 YAML 是 canonical 示例，它也被用作:

- YAML DSL 语法/用户指南的真实参照
- schema 补全与 drift gate 的回归入口之一
- Workflow 能力(多 demand 编排)的最小可复现实例

相关文档入口(按常见阅读路径):

- [YAML DSL 语法速查](../yaml-dsl/syntax.md)
- [YAML DSL 用户指南](../yaml-dsl/user-guide.md)
- [Workflow](../yaml-dsl/workflow.md)
- [配置补全与编辑体验](../yaml-dsl/editor.md)
- [升级指南](../yaml-dsl/upgrades/index.md)
- keys lookup 分片：YAML 主线 `ch010` / `ch050` 用 Observer + Hook 订阅 `LOADER_CALL` 核对 `chunk_offset`；选型见 [用户指南 §4.4.3](../yaml-dsl/user-guide.md#443-lookupchunking-keys-python-runtime) 与 public API `ch164_public_api_lookup_chunking`

## 4) doc governance 边界(避免手改生成物)

docs-site 的 SSOT 是 `docs/doc/`，但其中存在两类“不可手改”的内容:

- 文件名包含 `.gen.` 的页面为生成物(例如 `*.gen.md`)
- `<!-- BEGIN AUTOGEN:... -->` / `<!-- END AUTOGEN:... -->` 注入区块内部为生成内容

当你改了 SSOT 并需要刷新生成物时，使用:

```bash
just gen-docs
```

最终以 `just qa` 的漂移门禁为准。
