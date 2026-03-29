from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, FrozenSet, Mapping, Tuple

from scalim_misc.notebook_support.pathing import find_repo_root

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class PublicApiManifest:
    path: Path
    curated_entrypoints: Tuple[str, ...]
    stable_modules: Mapping[str, FrozenSet[str]]
    internal_prefix_suggestions: Mapping[str, str]


def load_public_api_manifest(start: str | Path) -> PublicApiManifest:
    repo_root = find_repo_root(start)
    path = repo_root / "openspec" / "ssot" / "public_api_manifest.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    curated = tuple(str(x) for x in raw.get("curated_entrypoints", []))
    stable_raw = raw.get("stable_modules", {})
    stable_modules = {str(k): frozenset(str(x) for x in v) for k, v in stable_raw.items()}
    internal = {str(k): str(v) for k, v in (raw.get("internal_import_prefix_suggestions", {}) or {}).items()}
    return PublicApiManifest(
        path=path,
        curated_entrypoints=curated,
        stable_modules=stable_modules,
        internal_prefix_suggestions=internal,
    )
