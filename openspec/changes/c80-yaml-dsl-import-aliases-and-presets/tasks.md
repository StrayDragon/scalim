## 1. 项目级配置（`scalim.yaml`）

- [ ] 1.1 定义并解析 `scalim.yaml`：支持 `yaml_dsl.import_aliases` 与 `yaml_dsl.import_allowed_roots`，并提供清晰的类型校验与错误信息
- [ ] 1.2 实现 `scalim.yaml` 定位策略（从 demand YAML 向上查找，nearest-wins），并在 imports 渲染链路中注入 project config
- [ ] 1.3 增加显式 override（优先 Python API）：允许调用方直接指定 `scalim.yaml` 路径或 project root；override 存在时 MUST 不再向上查找（保证 CI/容器可预测）

## 2. Imports 解析接入 aliases 与 roots 治理

- [ ] 2.1 扩展 imports path 解析：当配置存在时支持 `<prefix>/...`（如 `@/x.yaml`、`COMMON:/x.yaml`），并先应用 alias 再做 v2 归一化与安全校验
- [ ] 2.2 实现 `import_allowed_roots` 校验：对 `resolve()` 后的目标路径做 root containment 检查，越界 fail-fast，错误至少包含解析基准与目标绝对路径
- [ ] 2.3 保持默认行为不变：未配置 `scalim.yaml` 时继续拒绝预留前缀与除 `scalim://` 之外的 URI scheme
  - 约束：roots containment 的实现与错误格式 MUST 复用 `yaml-path-escape-hardening` 的 allow-roots helper（避免两套策略漂移）

## 3. `scalim://` presets（本地只读 + 白名单）

- [ ] 3.1 建立 preset registry（白名单/注册表）：preset id → 包内资源（或内容），拒绝未知 id，禁止任意包内路径 passthrough
- [ ] 3.2 实现 `scalim://...` 资源加载（建议 `pkgutil.get_data`，兼容 Python 3.6 与 zipimport），并在 render 时展开为 effective YAML
- [ ] 3.3 （可选）新增 explain/provenance 输出接口（结构化 SSOT），记录每个导入片段来源（file path / preset id）；CLI 若需要人类友好输出，在 CLI 层渲染但底层结构必须统一

## 4. Schema 生成物与验收口径（SSOT/生成入口/漂移门禁）

- [ ] 4.1 更新 schema SSOT：`src/scalim/dsl/by_yaml/schema_dsl/` 中的 `imports` path 规则，允许 `@/...`、`NAME:/...` 与 `scalim://...`（运行时校验仍为准）
- [ ] 4.2 刷新生成物（禁止手改 `.gen.*`）：运行 `just gen-yaml-dsl-schema` 与 `just gen-yaml-dsl-editor-schema` 并提交输出文件变更  
  - SSOT：`src/scalim/dsl/by_yaml/schema_dsl/`  
  - 输出：`src/scalim/dsl/by_yaml/schema/*.gen.json`、`frontend/scalim-yaml-dsl-editor/**/schema/*.gen.json`
- [ ] 4.3 增加测试覆盖：alias 映射、allowed roots 越界拒绝、`scalim://` preset 展开（使用临时目录/临时文件，避免依赖真实项目结构）
- [ ] 4.4 验收：运行 `just qa`（含 `schema-drift-check`）与 `just openspec-check`
