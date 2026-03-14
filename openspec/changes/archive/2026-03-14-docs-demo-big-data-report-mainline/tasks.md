## 1. Specs 同步

- [x] 1.1 将本 change 的 delta spec 同步到主规范: `openspec/specs/docs-site/spec.md`(按 OpenSpec 流程)

## 2. 新增主线入口页

- [x] 2.1 新增文档页: `docs/doc/getting-started/demo-big-data-report.md`(主线教程入口;包含运行/对拍/排错命令与 SSOT/生成边界说明)
- [x] 2.2 在入口页中链接到:
  - `notebooks/marimo/demo_big_data_report/demo_main.py`
  - `notebooks/marimo/run_examples.py`
  - `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
  - `docs/doc/yaml-dsl/` 相关页面(语法/用户指南/升级指南/编辑器/Workflow)

## 3. 可发现性与导航

- [x] 3.1 更新 `docs/doc/getting-started/reading-guide.md` 引用该入口页(推荐阅读/入口索引)
- [x] 3.2 更新 `docs/doc/yaml-dsl/index.md` 增加该入口页链接(面向 YAML authoring 使用方)
- [x] 3.3 如导航未自动收录,在 `docs/zensical.toml` 增加该页面的 nav 入口

## 4. Doc governance / QA

- [x] 4.1 如涉及 injected blocks 或生成 reference,运行 `just gen-docs`
- [x] 4.2 通过: `just qa`
- [x] 4.3 通过: `just openspec-check`
