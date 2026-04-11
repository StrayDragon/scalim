## 1. 主包可选 dev 插件 hook（ImportError-safe）

- [ ] 1.1 在主包 schema 生成管线中新增极薄 hook（例如 `maybe_standardize_schema_docs(schema) -> schema`），内部 optional import `scalim_misc`；缺失时 MUST no-op（库用户 import/运行不失败）
- [ ] 1.2 调整 `src/scalim/dsl/yaml_dsl/schema_dsl/builder.py`（或相邻模块）在生成器路径调用该 hook；确保 hook 不进入 runtime 热路径

## 2. 迁移 standardizer 到 `packages/scalim-misc`

- [ ] 2.1 将 `src/scalim/dsl/yaml_dsl/schema_dsl/doc_standardizer.py` 的主体逻辑迁移到 `packages/scalim-misc/src/scalim_misc/`（保留同等能力：markdownDescription、snippets extractor、enum 语义校验、最小示例骨架等）
- [ ] 2.2 主包仅保留必要的薄适配层（如常量/接口），避免 gen-only 逻辑继续留在 `src/scalim/`

## 3. 生成入口与门禁（避免静默降级）

- [ ] 3.1 更新 `scripts/gen-yaml-dsl-schema.py` / `just gen-yaml-dsl-schema`：显式检查 `scalim-misc` 是否可用；若不可用：
  - CI 环境 fail-fast（非零退出码）
  - 本地开发输出明确 warning 并提示“生成结果将降级”（并给出安装 `scalim-misc` 的修复建议）
- [ ] 3.2 运行 `just gen-yaml-dsl-schema` 重新生成 `src/scalim/dsl/yaml_dsl/schema/*.gen.json`（禁止手改生成物），并确保 `tests/test_yaml_schema_generation.py` drift guard 通过

## 4. 测试与验收

- [ ] 4.1 增加测试覆盖：缺少 `scalim-misc` 时主包 import 与 runtime 不失败且 hook 正确 no-op（可通过 monkeypatch/import error 模拟）
- [ ] 4.2 在安装 `scalim-misc` 的环境下跑生成链路，确认生成结果不发生不可解释漂移
- [ ] 4.3 运行 `just openspec-check` 与 `just qa` 作为最终验收

## 5. 规范同步

- [ ] 5.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/yaml-dsl-schema/spec.md` 增加 “schema docs standardization via optional dev plugin” 的要求
