## Hotspot Inventory

### DSL runtime / validator
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validators/fields.py`
  - Current responsibilities: source field collection, derived field validation, output field validation, dependency checks, source/data-key ambiguity checks.
  - Stable entrypoints to preserve: `IMPL_ROOT.dsl.by_yaml.config_parsing.validator`, `IMPL_ROOT.dsl.by_yaml.config_parsing.loader`.
  - Internal split target: field collection, derived rules, output rules, shared issue helpers.
- `src/IMPL_ROOT/dsl/by_yaml/runtime/conversion.py`
  - Current responsibilities: lookup cast registry, config-to-IR orchestration, source/main-source conversion, relation path resolution, derived/call_by compilation, binding/params builder helpers.
  - Stable entrypoints to preserve: `IMPL_ROOT.dsl.by_yaml.runtime.conversion`, `IMPL_ROOT.dsl.by_yaml`, `IMPL_ROOT.dsl.by_yaml.runtime.introspection`.
  - Internal split target: lookup cast helpers, source conversion, relation conversion, binding/request helpers.

### hooks / observability / visualization
- `src/IMPL_ROOT/hooks/base.py`
  - Current responsibilities: hook protocol/base class, subscription parsing, cache rebuild, dispatch safety, event trigger helpers.
  - Stable entrypoints to preserve: `IMPL_ROOT.hooks.base`.
  - Internal split target: protocol/base, subscription/cache helpers, dispatch/event emission helpers.
- `src/IMPL_ROOT/ob/manager.py`
  - Current responsibilities: observer registration, wants inference, subscription cache, capture/replay state, event recording, typed emit helpers, pickle/lock recovery.
  - Stable entrypoints to preserve: `IMPL_ROOT.ob.manager`.
  - Internal split target: subscription/cache helpers, capture state helpers, event emission helpers.
- `src/IMPL_ROOT/ob/presets/viz.py`
  - Current responsibilities: config/path resolution, event writer lifecycle, viz metadata enrichment, event/trace payload mapping, snapshot writing.
  - Stable entrypoints to preserve: `IMPL_ROOT.ob.presets.viz`.
  - Internal split target: config/path helpers, emitter helpers, metadata/snapshot helpers, event mapping helpers.

### adaptive execution
- `src/IMPL_ROOT/execution/adaptive/loadref_scheduler.py`
  - Current responsibilities: worker resolution, process task runner, dependency layering, per-layer execution orchestration, scheduling decisions, result commit flow.
  - Stable entrypoints to preserve: `IMPL_ROOT.execution.adaptive.loadref_scheduler`.
  - Internal split target: worker/layer helpers, task runner helpers, scheduler orchestration over existing `*_unit.py` modules.

## Implementation Order
1. Baseline documentation and protective tests.
2. DSL runtime / validator refactor.
3. hooks / observer / viz refactor.
4. adaptive scheduler refactor.
5. External consumer compatibility pass, targeted validation, final cleanup.

## Review Boundaries
- Refactor only internal organization; do not change public import paths or runtime semantics.
- Preserve Python 3.6 compatibility and existing `typing_extensionsx` boundaries.
- Each hotspot slice is reviewable on its own; avoid opportunistic cleanups outside the six hotspot modules and their direct regression tests.
- If a controlled external consumer uses an impacted entrypoint, upgrade that call site to the new supported style without recording the real project path in change artifacts.
