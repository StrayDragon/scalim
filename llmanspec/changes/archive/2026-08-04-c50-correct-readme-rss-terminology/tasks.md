# Tasks: Correct README RSS terminology and restore reader-first onboarding

## 1. Contract and governed boundaries

- [x] 1.1 Update `governance-readme-examples` requirements and scenarios: generated visible YAML projection, local RSS delta proxy terminology, and versioned historical A/B claim boundaries.
- [x] 1.2 Bind this change to a non-default branch before editing the live spec, then land the spec commit on that branch.
- [x] 1.3 Run strict validation for the change/spec after the contract update.

## 2. Verified YAML projection

- [x] 2.1 Extend the README injector to derive a visible YAML fence from the executable minimal YAML SSOT, with a clearly marked `myapp.loaders` integration substitution and links to the runnable source/loader.
- [x] 2.2 Keep the Python IR controlled block as an advanced-source link rather than promoting its internal engine import.
- [x] 2.3 Add focused governance coverage for the generated YAML fence, source provenance, and rejection of handwritten/out-of-block drift.

## 3. Accurate local RSS illustration

- [x] 3.1 Rename the README-suite RSS helper and user-visible chapter wording to local RSS delta proxy semantics without changing the comparison's execution behavior.
- [x] 3.2 Update the renderer, README injection output, snapshot notes, and generated SVG assets so none claims sampled peak RSS or an RSS-savings guarantee.
- [x] 3.3 Keep proxy charts reproducible from `chart_snapshot.json`, non-SLA, and excluded from ratio hard gates.

## 4. Versioned performance evidence and README narrative

- [x] 4.1 Generate a README static historical A/B speedup chart from `docs/doc/assets/data/write-precompute-0.10.json`; do not duplicate benchmark values.
- [x] 4.2 Rewrite manual README sections into the reader-first structure, use the generated YAML quickstart, distinguish library users from repository contributors, and remove duplicated navigation/Pages/FAQ material.
- [x] 4.3 Present the 0.10.0 historical A/B boundary and 0.10.1 continuity link without promising general speed or memory outcomes.

## 5. Generate and verify

- [x] 5.1 Run the README generation entrypoint and confirm generated SVG/injected blocks are clean.
- [x] 5.2 Run the README example suite headlessly and verify its YAML success summary.
- [x] 5.3 Correct the two pre-existing py-doc-language annotations that block `just qa`, without changing documentation-governance behavior.
- [x] 5.4 Run the focused governance tests, strict SDD validation, and `just qa`; fix any failures without weakening the stated seams.
