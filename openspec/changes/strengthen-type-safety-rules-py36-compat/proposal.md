## Why

当前仓库已经具备 `basedpyright`、`just qa`、Python 3.6 兼容检查与 `typing_extensionsx` 兼容层,但类型安全策略仍偏“能过即过”: 目前 `src/IMPL_ROOT/` 只强制了少量规则,`notebooks` / `cli` 存在大范围放宽,`src/IMPL_ROOT/` 内仍有一批 `# type: ignore`,而很多规则仍停留在全局关闭状态.

下一步不适合直接做“一刀切 strict”,因为仓库明确要求保持 Python 3.6 运行时兼容,且 DSL/runtime/可观测性链路包含不少动态边界.因此需要先形成一份可评审的分层收紧提案,明确哪些规则可以先解除、哪些区域继续保守、以及如何在不破坏 `py3.6` 兼容的前提下逐步收口.同时,既然 `just qa` 已经覆盖 `py36-compat-check` 与 `py36-typingext-check`,CI 中重复的独立 `py3.6` job 也应同步收敛,避免质量门禁漂移.

## What Changes

- 发起一轮“类型安全强化 + Python 3.6 兼容保持”的提案,把静态类型收紧从零散修补提升为明确的分层治理策略.
- 引入新的 `static-type-safety` capability,定义类型检查分层、首批可收紧规则、`py3.6` 兼容边界以及 suppression 收口原则.
- 修改 `testing-quality`,要求 CI 以 `just qa` 作为唯一权威的非 bench 质量门禁入口,不再保留与之重复的独立 `py3.6` 检查 job.
- 形成 3 套可比较方案并明确推荐路线: 全量 strict、一轮性阶段收紧、仅记录不收紧;本提案选择“按边界分层、按规则分批 ratchet”的方案.
- 立即落一项低风险治理: 精简 `.github/workflows/ci.yaml`,移除与 `just qa` 重复的独立 `py3.6` job,并让主 QA job 直接执行 `just qa`.

## Capabilities

### New Capabilities
- `static-type-safety`: 定义 `basedpyright` 的分层收紧策略、首批规则束、`py3.6` 兼容 typing 约束与 suppression 审计要求.

### Modified Capabilities
- `testing-quality`: 明确 CI 的权威 QA 入口是 `just qa`,并禁止在该入口已覆盖 `py3.6` 检查时继续保留重复 job.

## Impact

- 主要影响 `pyproject.toml` 中的 `basedpyright` 配置、`src/IMPL_ROOT/` 的局部类型标注与 suppression 方式、以及后续相关回归测试.
- 会影响 `.github/workflows/ci.yaml` 的门禁组织方式,但不改变现有质量覆盖范围.
- 不计划改变用户侧运行 API;重点是提升内部类型可验证性、降低未来重构风险,并保持 Python 3.6 + `typing-extensions==4.1.1` 兼容前提不变.
