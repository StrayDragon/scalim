## Why

`src/scalim/dsl/yaml_dsl/` 中异常包装存在 `from exc`（保留链，~44 处）和 `from None`（丢弃链，~16 处）两种不一致风格。`from None` 会丢失原始异常上下文，导致用户/开发者在排查错误时缺少根因信息。尤其在 `workflow_compile.py` 中，内部 `ValueError`/`TypeError` 被包装为 `ScalimWorkflowConfigError` 时使用 `from None`，导致配置错误的根因在 traceback 中完全不可见。

## What Changes

- 制定异常链规范：`src/scalim/` 内所有 `raise ... from` 统一使用 `from exc` 保留链，仅在显式需要隐藏内部实现细节的公共 API 边界才允许 `from None`。
- 修复 `workflow_compile.py` 中 4 处 `from None` 为 `from exc`。
- 修复 `workflow_config/_parse.py` 中 2 处 `from None` 为 `from exc`。
- 修复 `project_config.py` 中 2 处 `from None` 为 `from exc`。
- 审查 `yaml_load.py`、`loader.py`、`conversion_sources.py` 中的 `from None`，按规范判断是否需要修改。
- 添加治理测试或 ruff 规则检查新增的 `from None` 使用。

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- 涉及 `src/scalim/dsl/yaml_dsl/` 下约 8-16 处 `from None` 调用点。
- 用户可见变化：错误 traceback 将显示更完整的异常链（调试友好）。
- 不影响异常类型或消息内容。
