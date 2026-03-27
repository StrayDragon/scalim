## 0. Baseline / Verification

- [x] 0.1 运行 `uv run scripts/check-cast-usage.py --report .tmp/artifacts/cast-usage.report.txt` 建立 `cast` 基线
- [x] 0.2 运行 `uv run scripts/check-no-cover.py --report .tmp/artifacts/no-cover.report.txt` 建立 `no cover` 基线
- [x] 0.3 按目录/职责分类命中,区分“应补类型/应补测试”与“必须 allow”的场景（见 `classification.md`）
- [x] 0.4 运行 `uv run scripts/check-object-type.py --report .tmp/artifacts/object-type.report.txt` 建立 `object` 基线

## 1. Tooling

- [x] 1.1 实现 `scripts/check-cast-usage.py`,支持文本/JSON 报告与 `--check`
- [x] 1.2 实现 `scripts/check-no-cover.py`,支持文本/JSON 报告与 `--check`
- [x] 1.3 为两类检查定义显式 allow 约定与理由校验,并明确这些注释属于治理标记
- [x] 1.4 在 `justfile` 增加 SSOT 入口: `report-*` / `check-*` 命令
- [x] 1.5 实现 `scripts/check-object-type.py`,支持文本/JSON 报告与 `--check`
- [x] 1.6 支持行级 `# pragma: allow-object <reason>` 与文件级 `# pragma: allow-object-file <reason>`,并将 `scripts/` 与 `vendor/` 视为白名单边界
- [x] 1.7 在 `justfile` 增加 SSOT 入口: `report-object-type` / `check-object-type`

## 2. Rollout

- [x] 2.1 优先重构低风险、可静态化的 `cast` 使用,减少不必要的类型逃逸
- [x] 2.2 优先移除可测试分支上的 `# pragma: no cover`,仅保留确属兼容/抽象边界的用法
- [x] 2.3 对确属必要的 `cast` / `no cover` 补充局部 allow 注释与原因
- [x] 2.4 将 `check-cast-usage` 与 `check-no-cover` 接入 `quick-check-only-py`,并在 `just qa` 中验证通过

## 3. Compatibility / Drift Gates

- [x] 3.1 确认 `src/scalim/` 中涉及兼容 typing 的实现继续使用 vendor shim 作为 SSOT,避免破坏 `Python 3.6` 边界
- [x] 3.2 若新增文档或规则说明,明确手写 SSOT 与生成入口,并通过 `just gen-docs` / drift check / `just qa` 验证一致性
