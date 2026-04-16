# 主线教程: demo_big_data_report

??? note "适用读者"
    - 想快速跑通一条端到端 demo 的使用方/贡献者
    - 需要一个稳定入口来复现/对拍/排错的排查者

本仓库的 **唯一主线教程** 收敛在 `notebooks/marimo/demo_big_data_report/`。这里把“从哪里开始、怎么跑、怎么对拍、失败怎么定位”串在一页里，避免在 YAML DSL 文档、示例目录与 `just` 入口之间来回猜。

## 1) 关键入口(SSOT)

- marimo 教程入口(交互式): [`notebooks/marimo/demo_big_data_report/demo_main.py`](#code=notebooks/marimo/demo_big_data_report/demo_main.py)
- public API 覆盖套件入口(交互式): [`notebooks/marimo/example_public_api_suite/demo_main.py`](#code=notebooks/marimo/example_public_api_suite/demo_main.py)
- `just examples` 集成对拍入口(headless/CI): `just examples`（入口实现位于 [`justfile`](#code=justfile) 的 `examples:` recipe）
- YAML DSL canonical example(SSOT): [`notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`](#code=notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml)

这些入口是“稳定入口”: 文档与回归门禁会围绕它们组织。

章节集合包含:

- 主线 demo 章节（面向工程使用方写 YAML 的主路径）
- YAML DSL fixtures（`chapters_of_yaml_dsl/declared_yaml_dsl/` 下的可校验示例）
- Python 导入入口与结构评估: [公共 API 导入指南](public-api.gen.md)

另外，本仓库维护一套 **独立** 的 public API 覆盖套件：`notebooks/marimo/example_public_api_suite/`，用于：

- 对稳定公开入口模块 `scalim.*.__all__` 做 fail-fast 覆盖断言
- 演示扩展点（hook/observer/events/components 注入）

该 suite 同样纳入 `just examples` 回归范围。

## 2) 怎么跑(推荐命令)

### 2.1 跑示例 + 对拍(推荐;与 CI 一致)

```bash
just examples
```

该入口会执行 `demo_big_data_report` + `example_public_api_suite` 的章节级对拍，并输出可定位的 PASS/FAIL 摘要；这是 `just qa` 的一部分。

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

## 4) doc governance 边界(避免手改生成物)

docs-site 的 SSOT 是 `docs/doc/`，但其中存在两类“不可手改”的内容:

- 文件名包含 `.gen.` 的页面为生成物(例如 `*.gen.md`)
- `<!-- BEGIN AUTOGEN:... -->` / `<!-- END AUTOGEN:... -->` 注入区块内部为生成内容

当你改了 SSOT 并需要刷新生成物时，使用:

```bash
just gen-docs
```

最终以 `just qa` 的漂移门禁为准。
