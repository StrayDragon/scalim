## 1. schema-serve

- [ ] 1.1 在 `src/scalim/cli/yaml_dsl.py` 注册 `yaml-dsl schema-serve` 子命令并补齐 `--host/--port` 参数
- [ ] 1.2 实现只读 HTTP server: 仅 serve `src/scalim/dsl/by_yaml/schema/*.gen.json`,并对非 allowlist/目录穿越请求返回 404
- [ ] 1.3 启动时输出可复制的 schema URL 列表(例如 `http://localhost:62831/demand.gen.json`)

## 2. upsert-lsp-comment

- [ ] 2.1 在 `src/scalim/cli/yaml_dsl.py` 注册 `yaml-dsl upsert-lsp-comment` 子命令并补齐 `--type/--schema-path` 参数与 paths
- [ ] 2.2 实现 schema-ref 解析规则: `--schema-path` 缺省为 `http://localhost:62831`,并支持 base URL/dir 与 full URL/file(以 `.json` 结尾视为 full)
- [ ] 2.3 实现 header upsert: 仅扫描文件头部注释块(前 N 行/遇到首个非注释内容即停止),缺失则插入首行,不一致则替换,一致则不写入
- [ ] 2.4 输出被修改/已是最新的文件列表,并为“路径不存在/不可读/不可写”提供明确错误与非零退出码

## 3. Tests

- [ ] 3.1 为 header upsert 逻辑补充单测: 插入/更新/幂等/遇到 `---` 或内容行停止扫描
- [ ] 3.2 为 schema-ref 解析补充单测: base URL 拼接、base 目录拼接、full `.json` 直用
- [ ] 3.3 为 schema-serve 补充最小 e2e 测试: 启动 server → GET `/<schema>.gen.json` 返回 200;GET 目录穿越返回 404

## 4. Generated / Doc Governance

- [ ] 4.1 明确本变更不修改 schema 生成物(`src/scalim/dsl/by_yaml/schema/*.gen.json`)
  - SSOT: `src/scalim/dsl/by_yaml/schema_dsl/**`
  - 生成入口: `scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`
  - 验收口径: `tests/test_yaml_schema_generation.py`(drift guard)
- [ ] 4.2 (可选)在 YAML DSL 文档/skill 中补充新命令示例,并遵循文档治理:
  - 不编辑 `.gen.` 文件与 `BEGIN/END AUTOGEN:*` 区块内部
  - 若触及注入块或生成文档,更新 SSOT 后运行 `just gen-docs`

## 5. QA Gates

- [ ] 5.1 运行 `just qa` 确认 lint/tests 与 drift checks 通过
- [ ] 5.2 运行 `just openspec-check` 确认 OpenSpec 工件 sanitize/validate 通过
