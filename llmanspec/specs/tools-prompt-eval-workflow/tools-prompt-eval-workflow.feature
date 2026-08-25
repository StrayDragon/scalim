# language: zh-CN
# capability: tools-prompt-eval-workflow
# purpose: 定义仓库级 prompt 评测/回归工作流的最低要求,用于守护关键 skill/指令文本的质量与文档治理边界规则,并提供稳定的本地运行入口与 CI 产物。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: tools-prompt-eval-workflow

  @req:r82 @human
  场景: Prompt evaluation workflow exists
    - 系统 MUST 提供一套仓库级 prompt 评测/回归工作流,用于守护关键 skill/指令文本的质量与边界规则,并提供稳定的本地运行入口.

  @req:r326 @human
  场景: Governance boundary cases are covered
    - 评测集 MUST 覆盖 doc governance 相关的关键边界,至少包括: - 不修改 `*.gen.*` 文件 - 不修改 `AUTOGEN:*` 注入区块内容
  @req:r82 @human
  场景: local-entrypoint-runs-successfully
    - 必须成立：当 开发者运行评测入口命令；那么 评测流程 MUST 完成并返回 0
    当 开发者运行评测入口命令
    那么 评测流程 MUST 完成并返回 0
  @req:r326 @human
  场景: boundary-rules-are-evaluated
    - 必须成立：当 开发者运行评测入口命令；那么 评测集 MUST 包含针对上述边界的回归用例
    当 开发者运行评测入口命令
    那么 评测集 MUST 包含针对上述边界的回归用例
