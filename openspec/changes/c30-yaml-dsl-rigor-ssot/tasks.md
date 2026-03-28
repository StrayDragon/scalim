## 1. 统一 YAML load facade（含 duplicate keys 与 loc）

- [ ] 1.1 新增 `yaml_load` 单点模块：支持从 text/file 加载；默认启用 duplicate key 检测；产出 location index（行列定位）。
- [ ] 1.2 引入稳定 ErrorEnvelope（Python 3.6 兼容结构），并为 YAML parse/validate 错误统一映射到该结构（包含 `code/source_path/loc/path/message`）。
- [ ] 1.3 迁移 CLI validate 首先复用该 facade（最小风险入口），并保证 `--json` 输出结构稳定。

## 2. 迁移 workflow validate 与 compile/run 到统一实现

- [ ] 2.1 迁移 workflow validate 使用同一 `yaml_load` + ErrorEnvelope（包括 fragments 的一致处理，若 workflow 支持 imports）。
- [ ] 2.2 迁移 demand compile/run 使用同一 `yaml_load` + ErrorEnvelope（消除多套 loader/定位实现）。
- [ ] 2.3 增加一致性回归：同一份 YAML 在 CLI/compile/workflow validate 下的错误结构与定位口径一致（至少覆盖 duplicate key、语法错误与缺字段校验）。

## 3. schema_dsl 作为枚举/默认值 SSOT（消除口径漂移）

- [ ] 3.1 盘点 validator/parser 中的 enum/默认值重复定义，将其收敛为引用 schema_dsl 导出（不再复制常量）。
- [ ] 3.2 增加一致性自检（测试或脚本）：schema 允许的枚举 == runtime 接受的枚举（覆盖核心字段）。

## 4. schema 分发链路收敛（Python → editor）

- [ ] 4.1 明确 canonical schema 输出位置（Python 侧），并把 editor schema 的复制/打包收敛到单一脚本入口。
- [ ] 4.2 更新 drift checks：当 canonical schema 变化而 editor schema 未同步时 fail-fast，并提示对应生成入口（遵循现有 `just` 入口约定）。

## 5. 文档与验收

- [ ] 5.1 更新 YAML DSL 文档：说明错误结构与定位的一致性（SSOT 在 `docs/doc/yaml-dsl/**`；生成/注入区块按 `just gen-docs` 刷新）。
- [ ] 5.2 运行 `just qa`、`just examples`（如受影响）与 `just openspec-check`，确保门禁通过且无生成物漂移。

