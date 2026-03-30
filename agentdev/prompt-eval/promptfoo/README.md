# promptfoo (LLM suite) - local-only

本目录是 `promptfoo` 的 SSOT(仅本地运行; 不接入 CI)。

## 版本 pin

本仓库的 `promptfoo` 版本 pin 见 `agentdev/prompt-eval/promptfoo/promptfoo-version.txt`。

本机需安装对应版本(推荐用全局包管理器,例如 `pnpm add -g promptfoo@<version>`),并确保 `promptfoo --version` 与 pin 一致。

## 运行

只跑确定性 core(不消耗 token):

```bash
just prompt-eval
```

运行 LLM suite(会真实消耗 token):

```bash
just prompt-eval-llm
```

如果你担心 `uv/.venv` 冲突,或希望把所有产物写到仓库外的临时目录:

```bash
just prompt-eval-llm-tmp
```

也可以显式指定输出目录(目录在仓库外即可; 作为参数传入):

```bash
just prompt-eval-llm-tmp /tmp/scalim-prompt-eval
```

只做配置校验(dry-run; 不触发任何模型调用):

```bash
PROMPT_EVAL_LLM_DRY_RUN=1 just prompt-eval-llm
```

常用省钱开关(建议先用最小集验证流水线,再扩大覆盖):

- `PROMPT_EVAL_LLM_FILTER_FIRST_N=...` 只跑前 N 个 test-case(按配置顺序)
- `PROMPT_EVAL_LLM_FILTER_PATTERN=...` 正则过滤 test-case `description`
- `PROMPT_EVAL_LLM_FILTER_PROMPTS=...` 正则过滤 prompt id/label
- `PROMPT_EVAL_LLM_MAX_CONCURRENCY=...` 降低并发(默认 2)
- `PROMPT_EVAL_LLM_NO_CACHE=1` 禁用 promptfoo cache(默认启用,可减少重复消耗)

## A/B: baseline vs candidate (不 checkout / 不 stash)

用 git ref(标签/commit)做 baseline,并与当前工作区(candidate)对拍:

```bash
PROMPT_EVAL_LLM_BASELINE_REF=<tag-or-sha> just prompt-eval-llm
```

产物输出到:

- `.tmp/artifacts/prompt-eval/llm/ab/baseline/`
- `.tmp/artifacts/prompt-eval/llm/ab/candidate/`
- `.tmp/artifacts/prompt-eval/llm/ab/compare.json`

默认模型(可在 `agentdev/prompt-eval/promptfoo/promptfooconfig.yaml` 修改):

- `openai:chat:gpt-5.1-codex-mini` (temperature=0, seed=0, max_tokens=700)

产物输出:

- `.tmp/artifacts/prompt-eval/llm/summary.json`
- `.tmp/artifacts/prompt-eval/llm/promptfoo-output.json`

## T1: coding agent 套件(昂贵; 低频回归)

本仓库的 T1 使用 `openai:codex-sdk` provider(见 `agentdev/prompt-eval/promptfoo/promptfooconfig.agent.yaml`)。

前置条件:

- `promptfoo` 已安装且版本与 pin 一致
- 已安装 `@openai/codex-sdk` (promptfoo 的可选依赖; 缺少会导致 config validate 失败)
- 已设置 OpenAI 相关环境变量(例如 `OPENAI_API_KEY`)

运行(会真实消耗 token; 建议先 dry-run):

```bash
PROMPT_EVAL_LLM_DRY_RUN=1 just prompt-eval-agent
```

仓库外临时目录(推荐; 避免 uv/.venv 冲突):

```bash
PROMPT_EVAL_LLM_DRY_RUN=1 just prompt-eval-agent-tmp /tmp/scalim-prompt-eval-agent
```

A/B 对拍(基线 vs 当前工作区; 不 checkout / 不 stash):

```bash
PROMPT_EVAL_LLM_BASELINE_REF=<tag-or-sha> just prompt-eval-agent-tmp /tmp/scalim-prompt-eval-agent
```

产物输出到(默认基于 `.tmp/artifacts/prompt-eval/`):

- `agent/summary.json`
- `agent/ab/{baseline,candidate}/`
- `agent/ab/compare.json`
