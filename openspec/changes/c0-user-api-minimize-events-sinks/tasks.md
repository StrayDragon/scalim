## 1. Audit & Target Surface

- [ ] 1.1 盘点 `scalim.events` / `scalim.sinks` 的用户可见导入使用(以 `docs/doc` + `notebooks/marimo` 为准),确定目标稳定导出集合
- [ ] 1.2 明确哪些导出属于内部实现/测试便捷并将被移除(记录在 change 的实现摘要或文档中)

## 2. Shrink `scalim.events` Facade (BREAKING)

- [ ] 2.1 调整 `src/scalim/events/__init__.py`：仅保留事件 envelope/事件类型常量/目录查询/归因 key 等稳定符号,不再 re-export 全量 typed payload 数据类
- [ ] 2.2 迁移仓内引用点(tests/packages/notebooks)以消除对被移除符号的依赖；tests 需要 typed payload 时改为从内部模块导入

## 3. Shrink `scalim.sinks` Facade (BREAKING)

- [ ] 3.1 调整 `src/scalim/sinks/__init__.py`：保留 sink 契约与常用 sinks,移除内部 helper/中间态工具在包根的聚合导出
- [ ] 3.2 迁移仓内引用点(tests/packages/notebooks)以消除对被移除符号的依赖；内部实现/测试需要 helper 时改为从内部模块导入

## 4. Governance Gates + User-Visible Materials

- [ ] 4.1 更新 curated public surface gate：将 `scalim.events`/`scalim.sinks` 纳入白名单并对其 `__all__` 做精确断言
- [ ] 4.2 扩展“用户可见材料扫描”门禁：禁止 `docs/doc`、`notebooks/marimo`、`artifacts/skills` 中出现 `scalim.events._*` 与 `scalim.sinks._internal.*`
- [ ] 4.3 同步 docs：更新 `docs/doc/getting-started/public-api.md` 的导入建议与结构评估(不手改 `.gen.*` 与 injected blocks；必要时跑 `just gen-docs`)

## 5. Validation / Acceptance

- [ ] 5.1 运行 `just qa` 并修复直到通过
- [ ] 5.2 运行 `just openspec-check`
- [ ] 5.3 若变更完成且无 blocker：`openspec sync`/`openspec archive` 并为本 change 创建独立 commit

