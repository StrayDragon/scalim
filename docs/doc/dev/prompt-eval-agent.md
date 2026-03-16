# Prompt 评测: Coding agent (T1)

??? note "适用读者"
    - 维护者/贡献者:希望评估 skill 在“真实工作流”(读写文件 + 运行命令)下的完成率
    - 需要做低频但更接近真实用户行为的回归(例如跨大版本升级)

`prompt-eval` 的 T1 与 T0 的区别:

- T0: 评估 prompt 输出本身(更省钱,更稳定)
- T1: 评估 coding agent 在隔离工作区内的真实执行(更贵,但更贴近用户)

本仓库的 T1 以 **可复现的临时工作区** 为准,每个 test case 都会生成独立 workspace,并在其中:

- 注入 `artifacts/skills/scalim-yaml-dsl/**` 的快照(用于对拍 baseline/candidate)
- 提供最小 fixture 项目与工具(避免依赖你本机的 scalim/uv 环境)

??? note "维护提示"
    - 配置 SSOT: `openspec/prompt-eval/promptfoo/promptfooconfig.agent.yaml`
    - workspace fixture: `openspec/prompt-eval/fixtures/agent_stub_project/`
    - assertions: `openspec/prompt-eval/promptfoo/assertions/`

## 前置条件

- 本机安装 `promptfoo` 且版本与 pin 一致: `openspec/prompt-eval/promptfoo/promptfoo-version.txt`
- 已设置模型侧环境变量(例如 `OPENAI_API_KEY`)
- 已安装 agent provider 的依赖(当前默认配置为 `openai:codex-sdk`)

## 运行

建议先 dry-run(不消耗 token,只做 config validate + workspace 准备):

```bash
PROMPT_EVAL_LLM_DRY_RUN=1 just prompt-eval-agent-tmp /tmp/scalim-prompt-eval-agent
```

如果你不介意产物落在仓库内(默认 `.tmp/artifacts/prompt-eval/`),也可以直接:

```bash
PROMPT_EVAL_LLM_DRY_RUN=1 just prompt-eval-agent
```

真实运行(会消耗 token):

```bash
just prompt-eval-agent-tmp /tmp/scalim-prompt-eval-agent
```

## A/B: baseline vs candidate

用 git ref(标签/commit)做 baseline,与当前工作区(candidate)对拍:

```bash
PROMPT_EVAL_LLM_BASELINE_REF=<tag-or-sha> just prompt-eval-agent-tmp /tmp/scalim-prompt-eval-agent
```

## 产物与对拍

以 `/tmp/scalim-prompt-eval-agent` 为例:

- `agent/summary.json`: 本次运行元信息 + 指向 baseline/candidate 的产物路径
- `agent/ab/baseline/` 与 `agent/ab/candidate/`: promptfoo 原始输出与失败摘要
- `agent/ab/compare.json`: baseline vs candidate 的对拍汇总
- `agent/workspaces/`: 每个 test case 的隔离工作区(包含注入的 skill 快照与 fixture)

## 省钱开关

T1 会更贵,建议先小样本跑通流水线:

- `PROMPT_EVAL_LLM_FILTER_FIRST_N=1` 只跑前 1 个用例
- `PROMPT_EVAL_LLM_FILTER_PATTERN=...` 正则过滤 test-case 描述
- `PROMPT_EVAL_LLM_FILTER_PROMPTS=...` 正则过滤 prompt id/label
- `PROMPT_EVAL_LLM_MAX_CONCURRENCY=1` 保持低并发(默认已是 1)

## 修改模型 / provider

T1 配置 SSOT: `openspec/prompt-eval/promptfoo/promptfooconfig.agent.yaml`

- 更换模型: 修改 provider 的 `model`
- 更换用户常用 provider: 直接替换 `providers` 配置(保持 output_schema 与 assertions 可用)

如果 promptfoo 报 provider 依赖缺失(例如 `openai:codex-sdk`),需要先安装对应依赖包(例如 `@openai/codex-sdk`)。
