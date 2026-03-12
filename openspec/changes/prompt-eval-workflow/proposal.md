## Why

仓库内的 skill、agent 指令与文档治理规则属于“高杠杆文本资产”: 一次改动可能导致路由错误、用例回答质量回退、误改生成物/注入区块等问题,且这些回归往往难以靠常规单元测试覆盖。

因此需要引入一套可复现的 prompt 评测/回归工作流,把关键交互用例固化为自动化评测,并提供稳定入口用于本地与 CI 运行。

**Status: DELAYED**: 在 `openspec/changes/README.md` 移除 DELAYED 标记之前,不得开始实现本 change。

## What Changes

- 建立仓库级 prompt 评测配置与最小评测集:
  - skill 触发/任务路由正确性(例如 YAML DSL skill 的分流与引用材料选择)
  - doc governance 边界遵守(不修改 `*.gen.*`,不修改 `AUTOGEN:*` 注入区块等)
  - 关键命令入口/规则文本的回归(例如 `AGENTS.md` 中的硬规则)
- 提供统一运行入口(例如 `just prompt-eval`),支持本地一键运行与 CI 集成(初期可作为非阻塞 job,后续再评估是否升级为门禁)
  - `just prompt-eval` 默认只跑确定性 core(无密钥/无网络也能跑)
  - 模型评测层采用 `promptfoo`(可选层,按需启用;可单独入口或环境变量开关)
- 评测结果以确定性方式输出到受控目录(例如 `.tmp/artifacts/`),便于 CI 上传与回归对比

## Capabilities

### New Capabilities
- `prompt-eval-workflow`: 定义仓库 prompt 评测对象、用例组织、运行入口与输出/回归对比约束(不引入运行时依赖,仅作为 dev/CI 工作流)。

### Modified Capabilities
<!-- none -->

## Impact

- 受影响范围(预期):
  - `openspec/specs/`: 新增 `prompt-eval-workflow/spec.md`
  - `scripts/` + `justfile`: 增加评测运行入口与报告导出
  - CI: 新增一个可选 job(初期非阻塞)
- 依赖影响:
  - 仅增加开发/CI 依赖(具体评测工具在 design 阶段确定),不影响 `src/scalim/` 的 Python 3.6 运行时依赖边界
