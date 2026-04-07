## Why

当前仓库把一部分“开发规范/静态门禁”(例如结构扫描、导入边界、脚本输出一致性)实现为 `pytest` 用例放在 `tests/governance/` 下，这会带来一些系统性摩擦：

- 静态门禁本质上不是业务行为测试，放进 `pytest` 会被覆盖率/xdist/pytest 插件行为绑架，难以做到“单点、可复用、可独立运行”的 gate。
- `pytest` 的默认 `--cov-fail-under=100` 配置会让“只跑某个 governance 测试文件”变得不稳定（容易触发 0% coverage 或不必要的全量执行），降低开发反馈速度。
- `tests/governance/` 目前混合了：脚本自身单测、运行时契约测试、静态扫描门禁，导致目录语义不清晰，也不利于后续扩展更多 check-* 规则。

我们需要把“规范门禁”与“业务/运行时契约测试”解耦：让静态 gate 以 `scripts/check-*.py` 的形式存在，并由 `just qa` 的快速检查阶段统一执行；而 `pytest` 继续专注于运行时行为与稳定契约。

## What Changes

- 将部分 **静态治理门禁** 从 `tests/governance/` 迁移为可复用的 `scripts/check-*.py` 脚本，并接入 `just qa` 的 `quick-check-only-py` 链路（fail-fast）。
- 为迁移出的 check 脚本补齐一致的 CLI 约定（至少 `--check`，必要时 `--report/--root`），并保持输出可定位（文件路径/行号/违规类型）。
- 调整 `tests/governance/` 的内容边界：保留运行时契约测试与 check 脚本的单元测试；移除/替换纯静态扫描类 pytest 门禁，避免重复 gate。
- 必要时调整 `justfile` 的任务编排，使静态门禁不再依赖 pytest 的覆盖率与执行模型。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `testing-quality`: 明确“静态规范门禁”优先落在 `scripts/check-*.py` 并由 `just qa` 在 pytest 之前执行；pytest 侧保留对脚本行为的单测与对运行时契约的验证。
- `tests-domain-suites`: 明确 `tests/governance/` 的职责边界（脚本单测 + 运行时契约），避免把静态扫描门禁长期当作业务单测的一部分。
- `module-organization`: 补充/明确与导入结构相关的治理要求（例如导入图无环、主包禁止函数内导入等）以及推荐的 gate 落点（`scripts/check-*`）。

## Impact

- 受影响目录：
  - `tests/governance/`（目录语义与内容边界调整）
  - `scripts/`（新增/增强 `check-*` 门禁脚本）
  - `justfile`（质量门禁编排调整）
  - `openspec/specs/**/spec.md`（作为 SSOT 的规范文本将被更新）
- SSOT / 生成物约束：
  - SSOT：`openspec/specs/**/spec.md`、`scripts/check-*.py`、`justfile`。
  - 生成物：任何包含 `.gen.` 的文件与 `BEGIN/END AUTOGEN:*` 注入区块都禁止手改；若本变更需要更新文档注入块，应通过 `just gen-docs` 生成并由漂移门禁校验。
  - skills 受控产物（如 `artifacts/skills/**` 下的 `*.gen.*`）若被间接影响，必须通过对应生成器（例如 `scripts/gen-agent-skill.py`）重建。
- 对运行时/用户 API：预期无影响（仅开发规范与质量门禁实现方式调整）。

