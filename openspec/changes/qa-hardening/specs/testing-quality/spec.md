## ADDED Requirements

### Requirement: `just qa` 的 py36 兼容性门禁必须依赖 docker 且不得静默降级
系统 MUST 将 “py36 兼容性” 作为强门禁执行,并确保其语义不依赖当前开发机 Python 解释器的偶然行为.

具体要求:
- 当运行 `just qa`(或其子任务)触发 py36 兼容性检查时,检查 MUST 在 docker 中执行
- 当 docker 不可用时,检查 MUST 失败并给出明确指引(安装/启动 docker),不得静默降级为静态兜底检查并输出 warn 继续通过

#### Scenario: docker 不可用时 fail-fast
- **GIVEN** 开发机未安装或不可用 docker
- **WHEN** 开发者运行 `just qa`(或相关 py36 检查任务)
- **THEN** 命令 MUST 失败并提示需要安装/启动 docker
