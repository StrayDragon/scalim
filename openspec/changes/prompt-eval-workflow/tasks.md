**Status: READY**: 可开始实现本 tasks（先实现确定性 core; 模型评测保持可选层,不作为默认依赖）。

## 1. 运行入口与产物输出

- [ ] 1.1 新增 `just prompt-eval` 入口(默认只跑确定性 core),确保本地运行返回 0 且错误可见
- [ ] 1.2 实现 prompt-eval core runner 脚本骨架(用例发现/执行/汇总/退出码)
- [ ] 1.3 评测结果输出到 `.tmp/artifacts/prompt-eval/`(至少包含 `summary.json` 与逐用例明细),并保证确定性排序/序列化
- [ ] 1.4 增加 `--check` 模式(或 `just prompt-eval-check`),用于 CI 中只做校验与受控输出
- [ ] 1.5 为模型评测提供独立入口(例如 `just prompt-eval-llm`)或开关(例如 `PROMPT_EVAL_LLM=1`),并确保默认不要求密钥/网络/Node

## 2. Doc governance 边界用例(确定性核心)

- [ ] 2.1 实现 generated 文件边界验证器: 任何变更触达 `*.gen.*` 路径默认判定失败(除非用例声明允许)
- [ ] 2.2 实现 injected-block 边界验证器: 检测 `BEGIN/END AUTOGEN:<id>` 区块内部内容被改动时判定失败
- [ ] 2.3 添加 diff fixture 与回归用例,至少覆盖: 修改 `*.gen.*`(失败)、修改 `AUTOGEN:*` 区块内部(失败)、仅修改区块外部上下文(通过)
- [ ] 2.4 将上述用例纳入 `just prompt-eval` 默认评测集,确保可复现且稳定

## 3. 关键规则与路由回归(最小集)

- [ ] 3.1 增加 `AGENTS.md` 硬规则的回归用例(例如 doc governance 边界与生成入口提示),避免关键约束文本被误删/漂移
- [ ] 3.2 增加一个“skill 路由/引用材料选择”的最小回归用例占位(先做确定性断言/静态校验,后续可升级为 `promptfoo` 模型评测)

## 4. CI 集成(先非阻塞)

- [ ] 4.1 新增 CI job 运行 `just prompt-eval` 并上传 `.tmp/artifacts/prompt-eval/` 目录
- [ ] 4.2 初期将该 job 设为非阻塞,并记录未来升级为门禁的条件(覆盖率/稳定性/漂移策略)

## 5. 可选模型评测(后续扩展)

- [ ] 5.1 采用 `promptfoo` 作为模型评测 runner,并 pin 版本(可复现),保持为可选层(不成为 `just prompt-eval` 的硬依赖)
- [ ] 5.2 建立 `promptfoo` 配置 SSOT 目录与最小样例(仅占位,不追求覆盖率)
- [ ] 5.3 增加端到端模型交互用例: YAML DSL skill 的分流与引用材料选择
- [ ] 5.4 增加端到端模型交互用例: doc governance 边界在真实交互中的遵守(对 diff 应用同一套验证器)
- [ ] 5.5 固定模型参数与回归对比口径(例如 temperature/seed/评分阈值),并将模型评测输出隔离到独立子目录(例如 `.tmp/artifacts/prompt-eval/llm/`),早期只作为观察信号
