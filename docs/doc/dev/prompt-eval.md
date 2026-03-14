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

- 用例目录: `openspec/prompt-eval/cases/`
  - 每个用例子目录包含 `case.json` (必需)
  - 可选: `patch.diff` / fixtures 等(由用例定义决定)
- 输出目录: `.tmp/artifacts/prompt-eval/` (每次运行会清理后重建)
  - `summary.json`: runner/meta + 统计
  - `cases.jsonl`: 逐用例结果
  - `failures.md`: 失败摘要(用于快速定位)

## LLM 套件(延后)

`just prompt-eval-llm` 当前仅占位: 会返回非 0 并提示需要额外配置. 请先使用确定性 core (`just prompt-eval`) 收敛用例与回归口径.
