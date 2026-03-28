## 1. CSV 公式注入防护（默认 escape）

- [x] 1.1 复用/抽取统一的“疑似公式字符串”转义工具函数（与 Excel 规则一致），并在 CSV 写出路径中调用（覆盖 header 与 data）。
- [x] 1.2 为 `CSVSink`/`ColumnCSVSink` 增加显式 opt-out 开关（建议 `allow_formulas: bool = False`），并保证默认行为不破坏现有调用方（仅改变“疑似公式字符串”的写出）。
- [x] 1.3 为 CSV sinks 增加单测：默认 escape（含前导空白、已带 `'` 的字符串、header 行）；以及 allow 模式原样保留。

## 2. template_vars 预编译渲染后大小上限

- [x] 2.1 在 `template_vars` 启用时引入 `rendered_yaml_max_len`（或等价命名）配置，并在 demand/workflow 入口与 imports fragment 渲染后、YAML parse 前执行上限检查。
- [x] 2.2 增加单测：渲染后超限的 demand/workflow fail-fast；超限 fragment fail-fast 且包含 fragment 路径/import trace；错误信息不回显渲染正文。
- [x] 2.3 补齐/复核文档：说明 `template_vars` 的安全边界与渲染上限（SSOT 在 `docs/doc/**`；若涉及注入区块/生成物则用 `just gen-docs` 刷新并通过 drift gate）。

## 3. 高风险入口治理（docs/skills 禁止引用）

- [x] 3.1 增加 repo-level 静态治理检查：禁止 `docs/doc/**` 与 `artifacts/skills/**` 引用 `unsafe_entrypoints` 或其它明确标记为 non-public/unsafe 的导入路径（仅做“窄且确定”的路径黑名单扫描，失败给出迁移建议）。
- [x] 3.2 将治理检查接入 `just qa`（或等价 QA gate），并确保 CI/本地行为一致（不引入依赖网络的不稳定步骤）。

## 4. 验收与对齐

- [x] 4.1 运行 `just openspec-check`，确保增量 specs 结构校验与 sanitize 均通过。
- [x] 4.2 运行 `just qa`（至少覆盖相关单测与 drift checks），确保变更不会引入新的不稳定性或漂移。
