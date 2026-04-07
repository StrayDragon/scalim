# Downstream Adaptation Playbook

## 何时读取

- 你在本仓库升级了 YAML DSL(包含 breaking),需要盘点并同步下游项目的配置/用法
- 你希望“先做调研与风险评估”,等上游/依赖版本稳定后再批量升级下游
- 你需要在不泄露路径明细的前提下,输出可行动的下游改造清单

## 隐私与输出约束

- 允许读取 `.tmp/known-outer-paths-using-this-package.txt` 用于盘点与行动
- 输出/文档/报告中**不得**复述、枚举或总结该文件内容;只允许引用该文件路径本身
- 下游盘点建议统一用“行号 line N”标识下游条目,避免在 stdout 展示路径

## 两阶段策略(上游未稳定 → 上游稳定后切换)

### A. 上游未稳定时: 做“差异盘点”,不做强制升级

目标:
- 先把“需要改哪里”盘点清楚,把风险变成可分配任务
- 下游仍锁定旧版本(例如 v0.2.4)也没关系,此阶段不要求下游能通过 main 的新校验

推荐动作:

1) 确认下游清单文件健康(不泄露路径明细):

```bash
python3 scripts/check-known-outer-paths.py --file .tmp/known-outer-paths-using-this-package.txt
python3 scripts/check-known-outer-paths.py --file .tmp/known-outer-paths-using-this-package.txt --require-relative
python3 scripts/check-known-outer-paths.py --file .tmp/known-outer-paths-using-this-package.txt --check-exists
```

2) 用本仓库的“只读扫描脚本”生成行号级报告:

```bash
python3 scripts/scan-downstream-yaml-dsl.py
```

它会:
- 逐个扫描 `.tmp/known-outer-paths-using-this-package.txt` 的下游目录
- 对候选 YAML 执行 `uv run scalim-cli yaml-dsl validate --json`(`--type auto` 默认推断 demand/workflow;对 workflow 也可显式 `--type workflow`)
- 仅在 stdout 输出统计与行号,并写入 `.tmp/output/downstream-yaml-dsl-scan/line-<N>.json`

3) 把错误聚类为“可分配任务”(不做兼容层):

- 从每个 `line-<N>.json` 中提取 `issues[].message` 的前几个关键词/短语,按“同类错误”聚类
- 对每一类错误,用 upgrades 文档找到对应的迁移批次与迁移方式:
  - 入口: `artifacts/skills/scalim-yaml-dsl/references/upgrades/`
  - 或从 skill 的升级索引进入: `references/task-upgrade-legacy.md` (包含自动注入的升级批次索引)
  - 需要快速全文检索时: `rg -n "<keyword>" artifacts/skills/scalim-yaml-dsl/references/upgrades/*.md`

### B. 上游稳定后: 一步到位升级下游(不保留兼容)

目标:
- 下游全部切到新语义/新 schema,并以 `validate`/`schema validate` 作为门禁

推荐落地方式:

1) 下游仓库依赖版本先升级到目标版本(或切到稳定 tag),再改 YAML/代码
2) 直接把旧写法升级到新写法,不要做兼容分支逻辑
3) 每个下游改完必须跑:

```bash
uv run scalim-cli yaml-dsl schema validate <file.yaml>
uv run scalim-cli yaml-dsl validate <file.yaml>
```

对 workflow YAML(建议显式指定类型与 schema):

```bash
uv run scalim-cli yaml-dsl validate --type workflow <workflow.yaml>
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>
```

## 交付(报告)建议格式

- 汇总: 下游条目数、通过数、失败行号列表
- 失败分类(按行号聚合): runtime vars / output→outputs / bind→params templates / 其它 validator 错误
- 每个失败行号给出“最小处理建议 + 指向升级文档”
