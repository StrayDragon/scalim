import importlib
import json
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, Iterator, List, Mapping, Sequence, Tuple

import pytest


def _public_api_manifest_path() -> Path:
    return _repo_root() / "openspec" / "ssot" / "public_api_manifest.json"


def _load_public_api_manifest_stable_modules() -> Mapping[str, FrozenSet[str]]:
    path = _public_api_manifest_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    stable = raw.get("stable_modules", {})
    if not isinstance(stable, dict):
        raise TypeError("invalid stable_modules type: {}".format(type(stable).__name__))
    out: Dict[str, FrozenSet[str]] = {}
    for module_name, exports in stable.items():
        if not isinstance(module_name, str):
            raise TypeError("invalid stable_modules key type: {}".format(type(module_name).__name__))
        if not isinstance(exports, list) or not all(isinstance(x, str) for x in exports):
            raise TypeError("invalid exports for {}: {}".format(module_name, type(exports).__name__))
        out[str(module_name)] = frozenset(str(x) for x in exports)
    return out


def test_curated_public_modules_import_smoke() -> None:
    stable_modules = _load_public_api_manifest_stable_modules()
    for module_name in stable_modules:
        _ = importlib.import_module(module_name)


def test_curated_public_modules_use_explicit_all_whitelists() -> None:
    stable_modules = _load_public_api_manifest_stable_modules()
    missing: Dict[str, Sequence[str]] = {}
    stale: Dict[str, Sequence[str]] = {}
    for module_name, expected in stable_modules.items():
        mod = importlib.import_module(module_name)
        declared = tuple(getattr(mod, "__all__", ()))
        declared_set = frozenset(str(x) for x in declared)

        missing_names = tuple(sorted(expected - declared_set))
        stale_names = tuple(sorted(declared_set - expected))
        if missing_names:
            missing[module_name] = missing_names
        if stale_names:
            stale[module_name] = stale_names

    assert not missing, "curated module __all__ missing names:\n{}".format(missing)
    assert not stale, "curated module __all__ contains stale names:\n{}".format(stale)


def test_by_yaml_tools_smoke() -> None:
    from scalim.dsl.by_yaml.tools import derive_base_module_path, load_output_config

    repo_root = _repo_root()
    yaml_path = str(repo_root / "tests" / "fixtures" / "order_report.yaml")

    cfg = load_output_config(yaml_path)
    assert isinstance(cfg, dict)
    for required_key in ("params", "field_name_mapping", "output_fields", "outputs"):
        assert required_key in cfg

    base_module_path = derive_base_module_path(yaml_path, sys_path=[str(repo_root)], cwd=str(repo_root))
    assert base_module_path == "tests.fixtures"


def test_public_template_sandbox_rejects_unknown_values() -> None:
    from scalim.dsl.by_yaml._public_template_sandbox import validate_public_template_sandbox

    with pytest.raises(ValueError, match="template_sandbox"):
        _ = validate_public_template_sandbox("nope")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _iter_text_files(roots: Iterable[Path], *, suffixes: Tuple[str, ...]) -> Iterator[Path]:
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts:
                continue
            if p.suffix not in suffixes:
                continue
            yield p


def _find_banned_lines(text: str, *, banned: Tuple[str, ...]) -> List[Tuple[int, str]]:
    hits: List[Tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for token in banned:
            if token in line:
                hits.append((lineno, token))
    return hits


def test_user_visible_materials_must_not_promote_internal_module_paths() -> None:
    repo_root = _repo_root()
    manifest = json.loads(_public_api_manifest_path().read_text(encoding="utf-8"))
    internal = manifest.get("internal_import_prefix_suggestions", {})
    if not isinstance(internal, dict) or not internal:
        raise AssertionError("manifest internal_import_prefix_suggestions missing/invalid")
    banned = tuple(str(x) for x in internal.keys())
    roots = (
        repo_root / "docs" / "doc",
        repo_root / "notebooks" / "marimo",
        repo_root / "artifacts" / "skills",
    )

    violations: List[str] = []
    for p in _iter_text_files(roots, suffixes=(".md", ".py")):
        text = p.read_text(encoding="utf-8")
        for lineno, token in _find_banned_lines(text, banned=banned):
            rel = p.relative_to(repo_root).as_posix()
            violations.append("{}:{}: {}".format(rel, lineno, token))

    assert not violations, "internal module paths must not appear in user-visible materials:\n{}".format("\n".join(violations))
