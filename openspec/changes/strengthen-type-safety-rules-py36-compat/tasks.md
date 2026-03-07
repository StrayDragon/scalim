## 1. 基线与策略收敛

- [ ] 1.1 盘点 `basedpyright` 当前关闭项、`src/IMPL_ROOT/` 中的 `# type: ignore` 分布与适合进入 `strict-core` 的目录边界.
- [ ] 1.2 设计 `strict-core` / `compatible-dynamic` / `tooling-boundary` 三类策略,明确首批规则束与局部 suppression 约束.
- [x] 1.3 对齐 CI 质量门禁入口,让 `.github/workflows/ci.yaml` 直接使用 `just qa` 并移除重复的独立 `py3.6` job.

## 2. Phase 1 类型收紧实施

- [ ] 2.1 在核心稳定区开启首批规则束: `reportMissingParameterType`、`reportUnknownParameterType`、`reportUnknownArgumentType`、`reportUnknownVariableType`、`reportMissingTypeArgument`.
- [ ] 2.2 通过补充局部注解、类型别名、Protocol/TypedDict、兼容 shim 与窄 helper seam 收口 Phase 1 新增报错.
- [ ] 2.3 将 `src/IMPL_ROOT/` 中新增或存量的广义 suppression 收敛为局部、带规则代码且可审计的形式,避免继续扩大目录级放宽.

## 3. 验证与后续 ratchet

- [ ] 3.1 补充最小护栏,确保类型强化后 `just qa` 仍保持 Python 3.6 兼容检查通过.
- [ ] 3.2 运行 `openspec validate --all --strict --no-interactive` 与 `just qa`,确认提案落地后的质量门禁定义一致.
- [ ] 3.3 基于 Phase 1 的报错收口结果,评估是否继续解除 `reportIncompatibleMethodOverride`、`reportIncompatibleVariableOverride`、`reportUnnecessaryTypeIgnoreComment` 等 Phase 2 规则.
