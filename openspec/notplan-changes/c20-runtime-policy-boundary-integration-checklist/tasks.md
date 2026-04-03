## 1. Review scope

- [ ] 1.1 确认 checklist 首批只覆盖“已迁出 YAML 主线”的 runtime-only policy，避免范围失控。
- [ ] 1.2 确认 boundary coverage matrix 的固定分层是否为 schema/parse、compile/preload、runtime compile、workflow per-run、user-entry smoke。

## 2. Spec review

- [ ] 2.1 评审 `specs/testing-quality/spec.md` 中关于 boundary matrix 的规范要求是否足够明确、可落地。
- [ ] 2.2 评审 `specs/marimo-example-public-api-suite/spec.md` 中关于 notebook/public API smoke 职责的定位是否合理。

## 3. Implementation planning

- [ ] 3.1 确认首批试点 policy 清单（建议从 `demand_diagnostics`、`loader_retry`、`guardrails`、`batch_size` 开始）。
- [ ] 3.2 决定后续实施应落在哪些测试目录与 gate 中，并据此再进入正式 OpenSpec 主线变更。
