## Why

`notebooks/marimo/demo_big_data_report/` 被定义为仓库的**唯一主线教程**与 `just examples` 的确定性回归入口，但当前主线呈现与目标不一致：

- 章节仍包含较多 IR/Plan 等底层视角；对多数工程使用方而言成本高、维护负担大。
- YAML DSL 的能力覆盖没有形成“以 schema 为准”的可回归套件：部分能力只在 Python 章节里演示，难以防 drift。
- public API 覆盖章节与主线教学混杂，导致“为了覆盖而写章节”，主线叙事难以保持业务背景与可读性。

需要一次结构性收敛：以 **YAML DSL 场景化**为主线（电商/广告/客服），并把“覆盖回归（public API / hooks / ob）”迁出为独立 suite，同时保持对拍门禁不降级。

## What Changes

- 重组 `demo_big_data_report` 主线章节为 **YAML DSL 教学优先**：
  - 每章必须包含：背景介绍、假设的需求方需求（自然语言）、方案取舍、以及 deterministic 对拍断言。
  - 下线/移除 IR/Plan 相关章节（不再作为主线教学内容）。
- 在 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` 建立“互联网常见数据场景库”（第一版）：
  - 电商（保留并扩展现有 canonical example）
  - 广告（ads）
  - 客服（support）
  - 每个场景提供可校验的 demand/workflow YAML（必要时拆分多个文件 + fragments），并纳入 `just examples` 对拍范围。
- 增加以最新 schema 为准的 **capability coverage matrix**（schema key/definition → 覆盖 YAML/章节/断言），作为 drift 约束与维护入口。
- 将稳定公开入口模块 `__all__` 的覆盖回归从 `demo_big_data_report` 主线中迁出，形成独立 suite（仍纳入 `just examples`）：
  - 迁移/重命名 public API 相关章节到新目录（例如 `notebooks/marimo/example_public_api_suite/`）。
  - 更新 `notebooks/marimo/run_examples.py`、coverage 生成脚本与 pytest gate 以保持确定性回归不丢失。
- 同步更新 docs-site 的主线入口说明，使其反映新的 suite 结构与定位（不更改 canonical YAML SSOT 路径）。

## Capabilities

### New Capabilities

- `yaml-dsl-demo-scenarios-suite`: 定义 YAML DSL 场景库（电商/广告/客服）与 coverage matrix 的治理边界，并要求纳入 `just examples` 的确定性对拍。
- `marimo-example-public-api-suite`: 定义独立的 public API 覆盖 suite（`__all__` 覆盖 + hooks/ob 扩展点），要求与主线教学解耦但仍纳入 examples gate。

### Modified Capabilities

- `marimo-demo-big-data-report-chapters`: 调整主线章节集合（移除 public_api_* 与 IR 相关内容，改为 YAML 场景化主线）。
- `testing-quality`: 调整 “稳定公开入口模块 `__all__` 必须被 examples gate 覆盖” 的落点与要求（从 `demo_big_data_report/chapters/` 迁移到独立 suite，但保持门禁强度）。

## Impact

- `notebooks/marimo/`：新增/迁移 suite 目录；重排/改写主线章节；runner 扩展为多 suite；coverage 报告生成逻辑需同步。
- `notebooks/marimo/demo_big_data_report/by_yaml_dsl/`：新增 ads/support 场景 YAML 与 fragments/workflow；补齐 demand/workflow schema 能力覆盖缺口。
- `packages/scalim-misc/`：新增 ads/support 场景的确定性合成 loaders 与 oracle（纯 Python 真值或小型 golden fixtures）。
- `docs/doc/`：主线入口页与 YAML DSL 相关文档引用路径/描述更新（遵守生成物/注入区块治理规则）。
- `tests/`：public API suite gate 与 examples gate 对齐；确保 `just examples` 与 pytest 对拍稳定通过。

