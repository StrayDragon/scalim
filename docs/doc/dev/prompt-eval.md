# Prompt 评测(workflow)

??? note "适用读者"
    - 项目贡献者:希望把 prompt/规范类改动收敛为可复现的回归信号
    - 需要在 CI 中观察(但暂不升级为门禁)的维护者

本仓库提供 `prompt-eval` 的确定性 core runner,用于对一组受控用例产出稳定的 PASS/FAIL 信号,并把结果写入受控目录供 CI 上传.

## 快速开始

```bash
just prompt-eval
```

CI/check 模式(确定性 core + 受控输出):

```bash
just prompt-eval-check
```

## 用例与产物

- 用例目录: `agentdev/prompt-eval/cases/`
  - 每个用例子目录包含 `case.json` (必需)
  - 可选: `patch.diff` / fixtures 等(由用例定义决定)
- 输出目录: `.tmp/artifacts/prompt-eval/` (每次运行会清理后重建)
  - `summary.json`: runner/meta + 统计
  - `cases.jsonl`: 逐用例结果
  - `failures.md`: 失败摘要(用于快速定位)

## LLM 套件(T0; promptfoo)

LLM 套件已接入 `promptfoo`(仅本地运行; 不是 `just prompt-eval` 的硬依赖)。

### 前置条件

- 本机安装 `promptfoo` 且版本与 pin 一致: `agentdev/prompt-eval/promptfoo/promptfoo-version.txt`
- 已设置 OpenAI 相关环境变量(例如 `OPENAI_API_KEY`)

### 运行

```bash
just prompt-eval-llm
```

为了避免误消耗 token,建议先 dry-run:

```bash
PROMPT_EVAL_LLM_DRY_RUN=1 just prompt-eval-llm
```

### A/B: baseline vs candidate

用 git ref(标签/commit)做 baseline,与当前工作区(candidate)对拍,不需要 checkout/stash:

```bash
PROMPT_EVAL_LLM_BASELINE_REF=<tag-or-sha> just prompt-eval-llm
```

产物:

- `.tmp/artifacts/prompt-eval/llm/ab/baseline/`
- `.tmp/artifacts/prompt-eval/llm/ab/candidate/`
- `.tmp/artifacts/prompt-eval/llm/ab/compare.json`

更多本地使用说明与省钱开关见: `agentdev/prompt-eval/promptfoo/README.md`

### 仓库外临时目录(避免 uv/.venv 冲突)

LLM 套件可以把产物写到仓库外(例如 `/tmp`)。

```bash
just prompt-eval-llm-tmp
```

## Coding agent 套件(T1; 昂贵)

本仓库也提供了一个更昂贵的 coding-agent 套件(基于 promptfoo + agent provider; 低频回归用)。

```bash
PROMPT_EVAL_LLM_DRY_RUN=1 just prompt-eval-agent-tmp /tmp/scalim-prompt-eval-agent
```

详细说明见: [Prompt 评测: Coding agent (T1)](prompt-eval-agent.md)
