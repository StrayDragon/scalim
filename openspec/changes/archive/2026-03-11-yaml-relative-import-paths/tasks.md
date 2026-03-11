## 1. Resolver 与相对引用归一化

- [x] 1.1 在 `SecurePythonReferenceResolver` 增加相对引用归一化能力(支持 `.`/`..` 前缀),并确保归一化发生在 allowlist/security check 之前
- [x] 1.2 实现基于 `yaml_path` + `sys.path` 推导“当前 module 路径”的函数,并为不可推导场景给出明确错误信息
- [x] 1.3 为相对引用的归一化与越界错误添加单元测试(含 dotted/class-style 两类引用)

## 2. YAML 语义校验与解析入口适配

- [x] 2.1 放宽 loader 引用格式校验,允许 module path 以 `.`/`..` 开头(覆盖 `main_source.loader` / `sources.*.loader` / `*.retry.should_retry`)
- [x] 2.2 放宽 `call_by` 中 reference 的格式校验,允许相对 module 引用
- [x] 2.3 补充校验回归测试: 相对引用语法合法/非法(空 module、超出根、非法 identifier 段等)

## 3. 编译链路接入 `yaml_path` 基准

- [x] 3.1 在 `run/compile(yaml_path, ...)` 的编译链路中计算 base module,并传入 resolver(确保 `ConfigToIRConverter`/retry/call_by 都走同一 resolver)
- [x] 3.2 对无 `yaml_path` 的调用链(例如 `load_string` + converter)在遇到相对引用时 fail-fast,并给出需要提供基准的提示

## 4. Schema/编辑器/文档同步

- [x] 4.1 更新 YAML DSL schema meta: `main_source.loader` / `sources.*.loader` / `*.retry.should_retry` / `call_by` 的 hover 文案补充相对引用说明与示例
- [x] 4.2 运行 `just gen-yaml-dsl-schema` 与 `just gen-yaml-dsl-editor-schema` 并修复 drift
- [x] 4.3 更新文档示例(至少 `docs/doc/yaml-dsl/user-guide.md`): 增加相对引用示例与 allowlist 配置提示

## 5. Agent Skill 与生成物更新

- [x] 5.1 更新 `yaml-dsl-agent-guidance` 的 guidance/references,补充相对引用与 allowlist 说明
- [x] 5.2 运行 `just gen-agent-skill` 并校验生成物一致

## 6. 验证

- [x] 6.1 运行 `just qa`(含 openspec-check)确保无 lint/test/spec 校验回归
- [x] 6.2 改造 `.tmp/known-outer-paths-using-this-package.txt`: 尽量用相对路径(相对 `REPO_ROOT`),并补充解析/检查脚本支持相对路径(输出不得泄露路径明细)
