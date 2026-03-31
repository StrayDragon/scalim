## 1. 前置分析与切换 gate

- [ ] 1.1 盘点 `src/scalim/` 内所有直接依赖 `PyYAML` / `ruamel.yaml` 的调用面、类型耦合、错误假设与 dump 行为,整理为迁移 inventory。
- [ ] 1.2 对 `tests/fixtures/*.yaml` 与 `notebooks/marimo/**/declared_yaml_dsl/*.yaml` 建立 corpus parity 检查,确认 load 结果、duplicate key、parse location 与 dump 风格的差异清单。
- [ ] 1.3 在真实 Python 3.6 环境中补充 vendored import / load / compose / duplicate key / parse error smoke checks,形成默认后端切换的 go/no-go gate。

## 2. facade 与接入面收敛

- [ ] 2.1 设计并实现 repo-owned YAML facade/adapter,封装 safe load、duplicate key、compose/location index、parse error 与 dump 能力,避免业务层直接依赖第三方顶层 API。
- [ ] 2.2 将 demand loader、workflow loader、CLI validate、imports 相关入口收敛到统一 facade,并保持现有 ErrorEnvelope、定位口径与重复键语义不变。
- [ ] 2.3 为 facade 补充针对 removed API / backend swap 的回归测试,确认业务层不再直接依赖 `PyYAML` 风格符号。

## 3. 默认后端切换决策与运行时硬化

- [ ] 3.1 基于 1.x 的分析结果判断本 change 是否启用 vendored `ruamel.yaml` 为默认 backend;若 blocker 未清空,则保留 facade 与验证基线并记录 deferred decision。
- [ ] 3.2 若决定启用默认切换,完成 vendored default backend 切换、兼容适配与必要的测试更新;若决定暂缓,明确保留的默认 backend 与后续切换前提。
- [ ] 3.3 更新 vendors 运行时相关的手工 SSOT,至少覆盖 `src/scalim/vendor/README.md` 与 `src/scalim/vendor/yamlx/SOURCE.md`,确保 Python 3.6 / 无外部依赖 / vendored facade 约束表述一致。

## 4. 验收、文档与门禁

- [ ] 4.1 仅在实现影响 docs/specs 生成物或注入区块时,从对应 SSOT 运行 `just gen-docs` 刷新生成内容,不得手改 `.gen.` 文件或受控注入区块。
- [ ] 4.2 运行 `just openspec-check` 校验本 change 工件,并执行与本迁移相关的 targeted QA / py36 checks / no-external-yaml 回归。
- [ ] 4.3 记录最终验收结论: 是否已完成默认后端切换、是否存在已知 deferred blocker、以及未来 comment-preserving / round-trip 能力应由哪个 follow-up change 承接。
