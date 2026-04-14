## 1. Core SSOT 收敛（描述留在 src/scalim）

- [x] 1.1 识别并抽取 `schema_dsl/builder.py` 中的内联描述性 schema 片段（workflow/scalim_yaml/imports 等）到 `src/scalim/dsl/yaml_dsl/schema_dsl/` 的 SSOT 模块
- [x] 1.2 为抽取后的 SSOT 模块补齐最小单测/治理断言，确保字段描述变更不会被遗漏
- [x] 1.3 更新/新增 delta specs（本 change 内）明确：哪些是 SSOT、哪些是生成物，以及唯一生成入口

## 2. 生成器下沉到 packages/scalim-misc

- [x] 2.1 在 `packages/scalim-misc` 新增 YAML schema generator 模块（builder + writer），以 core SSOT 作为唯一输入
- [x] 2.2 将 docs standardizer 阶段集成到 misc generator（不再由 core 通过 optional hook 反向加载）
- [x] 2.3 更新 `scripts/gen-yaml-dsl-schema.py`：改为调用 misc generator；CI 环境缺失 misc 时 fail-fast 并提示修复（保持“唯一入口”）

## 3. QA / drift gate / 类型治理调整

- [x] 3.1 调整 schema generation/drift 相关测试：从“import core builder”迁移为“通过生成入口或 misc generator”验证输出一致性
- [x] 3.2 清理 core → misc 的任何导入路径（包含动态导入），并增加最小门禁（测试或脚本）防止回归
- [x] 3.3 运行 `just gen-yaml-dsl-schema` 重新生成 `src/scalim/dsl/yaml_dsl/schema/*.gen.json`（禁止手改生成物）并确保 `just qa` 通过
