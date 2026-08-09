# Tasks: c40-yaml-runtime-policy-boundary

> 细项已锁：**1A**（并行嵌 sized）+ **2A**（RowsReuse→RuntimeOptions）+ **3A**（工厂 header 默认→`name`）。  
> 测试边界（seams）：`scalim.dsl.yaml_dsl.run` / `run_workflow` / `validate`（或 `scalim-cli yaml-dsl validate`）；复用现有 `tests/yaml_dsl/**`。

## A. 盘点

- [x] A.1–A.7 evidence / 合并 / 导出

## B. 设计收口

- [x] B.1–B.4 措施 I/II/III + oneof 原则  
- [x] B.5 细项 **1A + 2A + 3A**  
- [ ] B.6 `change start` + specs landing（I 迁出 + II 覆盖优先级 + III 工厂默认 MUST/文档口径）

## C. 实现（specs landing 且 readyToImplement 后）

### C1. 措施 I — `lookup_chunk_size`

- [ ] C1.1 `LookupChunking.off|sized(size, parallel=...)` + `DemandRunRuntimeOptions.lookup_chunking`  
- [ ] C1.2 收拢旧 `parallelize_lookup_chunks`（兼容或友好迁移提示）  
- [ ] C1.3 YAML `lookup_chunk_size` → fail-fast 友好文案  
- [ ] C1.4 测试 + docs/skill/upgrade  

### C2. 措施 II — SourceCache / RowsReuse

- [ ] C2.1 `SourceCache` + `source_cache` 覆盖（Python > YAML > none）  
- [ ] C2.2 `RowsReuse` + `rows_reuse` 覆盖（同挂 RuntimeOptions）  
- [ ] C2.3 测试与文档（两套拆名 + cache_pool 边界）  

### C3. 措施 III — 默认与工厂

- [ ] C3.1 省略 encoding ≡ utf-8 测试  
- [ ] C3.2 allow_formulas 默认 true + pathless 拒绝  
- [ ] C3.3 工厂 `header_fields_output_by` 默认改为 `name` + 回归  

## D. 入口

- [x] D.1 New knob gate  
- [ ] D.2 apply 后文档与 design 一致  

## 门禁

- [ ] B.6 后：相关 pytest + `just llmanspec-check`  
- [ ] `llman sdd validate c40-... --strict`  
