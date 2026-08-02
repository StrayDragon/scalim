# 开发

??? note "适用读者"
    - 项目贡献者(开发/测试/代码质量)
    - 需要在本仓库内定位与修改实现的开发者

如果你还没跑通过项目,先看:

- [入门](../getting-started/index.md)

仓库约定与边界:

- [仓库开发约定](repo-guide.md)
- [文档治理与生成工作流](doc-governance.md)
- [发布前校准清单](pre-release-checklist.md)
- [`object` 类型标注治理](object-type-governance.md)
- [复杂度 QA harness](complexity-qa-harness.md)

常用命令:

```bash
just type-check
just test
just lintfix
just examples
just qa
just prompt-eval
just prompt-eval-agent
```

public API 治理/工具链（生成物写入 `.tmp/`，不要提交）：

```bash
just gen-public-api-jump-imports
just gen-public-api-exports-catalog
just check-public-api-curated-entrypoints
```

更多:

- [Prompt 评测(workflow)](prompt-eval.md)
- [Prompt 评测: Coding agent (T1)](prompt-eval-agent.md)
