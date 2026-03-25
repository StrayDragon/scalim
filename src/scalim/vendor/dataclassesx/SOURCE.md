# dataclassesx provenance

## Upstream

- PyPI distribution: `dataclasses==0.8`
- Upstream repository: https://github.com/ericvsmith/dataclasses
- License: Apache-2.0 (see `LICENSE.txt`)

## Vendored files

- `_backport.py`
  - Source file: `dataclasses.py` from `dataclasses==0.8`
  - Local modifications: only a small header comment block was added to disable ruff lint/format for this vendored file.

## Update procedure

1. Fetch the target upstream version of `dataclasses` (must remain Python 3.6-compatible).
2. Replace `_backport.py` with the upstream `dataclasses.py` content.
3. Update `LICENSE.txt` if upstream changed it.
4. Update this file and `src/scalim/vendor/README.md` with the new version.
5. Run `just py36-typingext-check` and `just quick-check-only-py`.

