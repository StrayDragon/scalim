## 1. Review scope

- [x] 1.1 确认 checklist 首批只覆盖“已迁出 YAML 主线”的 runtime-only policy，避免范围失控。
- [x] 1.2 确认 boundary coverage matrix 的固定分层（含 `workflow preflight`）：schema/parse、compile/preload、runtime policy merge、preflight、runtime compile、user-entry smoke。
- [x] 1.3 确认 workflow lifecycle 的 SSOT 分层与 preflight 插入点：runtime policy merge 之后、engine execute 之前。
- [x] 1.4 确认 preflight 的失败语义为 fail-fast + 直接 raise，整体 workflow 失败（不做 per-run 继续跑）。

## 2. Spec review

- [x] 2.1 评审 `specs/testing-quality/spec.md` 中关于 boundary matrix 的规范要求是否足够明确、可落地。
- [x] 2.2 评审 `specs/marimo-example-public-api-suite/spec.md` 中关于 notebook/public API smoke 职责的定位是否合理。

## 3. Implementation planning

- [x] 3.1 确认首批试点 policy 清单（建议从 `demand_diagnostics`、`loader_retry`、`guardrails`、`batch_size` 开始）。
- [x] 3.2 决定后续实施应落在哪些测试目录与 gate 中，并据此再进入正式 OpenSpec 主线变更。
- [x] 3.3 列出“可推理子集”的 runtime-only diagnostics 清单，并确认 v1 仅覆盖 `validate_unique_field_names`，其余逐步纳入。
- [x] 3.4 决定 `scalim-cli yaml-dsl validate`(workflow validate) 保持 authoring-only 语义，不做 policy-aware 参数化；policy-aware 校验由 workflow preflight / 后续独立入口承载。
