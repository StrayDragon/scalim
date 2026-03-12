## 1. Workflow Schema & Config Model

- [ ] 1.1 定义 workflow 配置模型与解析器(包含 runs/options)并保证 Python 3.6 兼容
- [ ] 1.2 生成并提交 workflow JSON Schema(用于 editor/schema validate)与漂移测试门禁
  - 输出建议: `src/scalim/dsl/by_yaml/schema/workflow.gen.json`
  - 更新生成脚本(与 demand schema 同步): `scripts/gen-yaml-dsl-schema.py` / `scripts/gen-yaml-dsl-editor-schema.py`
- [ ] 1.3 若需要前端 editor 校验 workflow YAML,将 workflow schema 同步到前端并支持 schema 选择/校验(如变动过大,拆分到独立 frontend change)

## 2. Python Entrypoint & Runner

- [ ] 2.1 增加 Python 侧 workflow 入口 `scalim.dsl.by_yaml.run_workflow(...)`,不改动现有 `run()` 的 demand-only 语义
- [ ] 2.2 实现 runs 队列执行与 `max_concurrency` worker pool,并保证返回结果顺序确定
- [ ] 2.3 实现 `failure_policy=all_fail|primary_only` 的异常封装与返回结构(可检查 errors)

## 3. Shared preload_forever Cache

- [ ] 3.1 抽象线程安全的 workflow-scope `PreloadCache` 容器(按 `source_id` 管理与去重)
- [ ] 3.2 定义 preload 规格签名(至少覆盖 loader/params/normalize/key/lookup_cast 等关键字段)并实现启动前预检查冲突校验(冲突即 fail-fast,不执行任何 run)
- [ ] 3.3 打通执行层注入点:让单次 demand 执行可选择复用外部 `PreloadCache`(仅 workflow 场景启用)
- [ ] 3.4 并发下对单个 `source_id` 加锁,保证最多一次真实 loader 调用

## 4. Tests

- [ ] 4.1 workflow schema validate 与语义校验测试(缺字段/非法枚举/非法类型)
- [ ] 4.2 `failure_policy` 行为测试(首错中断 vs 跳过继续 + errors 可检查)
- [ ] 4.3 `max_concurrency` 并发测试(结果顺序稳定)
- [ ] 4.4 `share_preload_cache` 复用测试(计数断言只加载一次)
- [ ] 4.5 preload 规格冲突 fail-fast 测试(错误包含冲突 run id 与差异点)

## 5. Docs

- [ ] 5.1 按 SSOT 规则补充 workflow 语法与示例文档,并运行 `just gen-docs`(不手改 `.gen.`)
- [ ] 5.2 盘点下游适配与同步修改: 读取 `.tmp/known-outer-paths-using-this-package.txt` 并列出需要同步的下游目录(输出/文档中不得引用文件内容)
- [ ] 5.3 新增升级指南: `docs/doc/yaml-dsl/upgrades/YYYY-MM-DD-yaml-dsl-workflow.md`,并运行 `just gen` 注入升级索引

## 6. Gates / Archive

- [ ] 6.1 通过: `just gen`
- [ ] 6.2 通过: `just qa`
- [ ] 6.3 通过: `just openspec-check`
- [ ] 6.4 归档到: `openspec/changes/archive/YYYY-MM-DD-yaml-dsl-workflow/`
