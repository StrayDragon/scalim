## 1. Spec

- [x] 1.1 [blocked-by: c50 specs landed or concurrent] Amend `performance-observability`: write stage MUST reflect real sink-path time; MUST NOT rely solely on unplanned WRITE_* ops
- [x] 1.2 Clarify double-count rules (flush inside load/compute windows)

## 2. Instrumentation (vertical)

- [x] 2.1 Column-mode: time real column/sink writes into stage `write`
- [x] 2.2 Streaming-mode: time row flush/finalize into `write`; subtract/pause so loader/compute are not inflated
- [x] 2.3 Optional close/save: document bucket (write vs finalize) and fold into metrics without orphaning after BATCH_END

## 3. Tests (seams confirmed)

- [x] 3.1 Synthetic CSV and/or xlsx path: `stages.write > 0` after successful output
- [x] 3.2 Output bytes/rows unchanged vs uninstrumented control
- [x] 3.3 loader+compute+write vs batch wall within agreed tolerance (no gross double-count)

## 4. Docs

- [x] 4.1 Update observability docs: write attribution semantics; remove c50 "write incomplete" caveat when done
