# prompt-eval-workflow Specification

**状态: ✅ 已实现**
## Purpose
定义仓库级 prompt 评测/回归工作流的最低要求,用于守护关键 skill/指令文本的质量与文档治理边界规则,并提供稳定的本地运行入口与 CI 产物。

## Related Code (as implemented)
- `justfile` (`prompt-eval`, `prompt-eval-check`, `prompt-eval-llm*`, `prompt-eval-agent*`)
- `scripts/prompt-eval.py` (确定性 core runner + 可选 promptfoo/agent 套件)
- `agentdev/prompt-eval/` (cases/fixtures/promptfoo SSOT)

## Requirements
### Requirement: Prompt evaluation workflow exists
系统 MUST 提供一套仓库级 prompt 评测/回归工作流,用于守护关键 skill/指令文本的质量与边界规则,并提供稳定的本地运行入口.

#### Scenario: Local entrypoint runs successfully
- **WHEN** 开发者运行 `just prompt-eval`
- **THEN** 评测流程 MUST 完成并返回 0
- **AND** 评测结果 MUST 输出到受控目录(例如 `.tmp/artifacts/`)以便 CI 上传与回归对比

### Requirement: Governance boundary cases are covered
评测集 MUST 覆盖 doc governance 相关的关键边界,至少包括:
- 不修改 `*.gen.*` 文件
- 不修改 `AUTOGEN:*` 注入区块内容

#### Scenario: Boundary rules are evaluated
- **WHEN** 开发者运行 `just prompt-eval`
- **THEN** 评测集 MUST 包含针对上述边界的回归用例
