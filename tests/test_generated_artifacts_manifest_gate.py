from pathlib import Path


def _load_check_generated_artifacts_module():
    # scripts/ 下的脚本使用 `-` 命名,不能用常规 import;这里用动态加载保证可测.
    import importlib.util

    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "check-generated-artifacts.py"
    spec = importlib.util.spec_from_file_location("check_generated_artifacts", str(script_path))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_artifacts_manifest_gate_fails_fast_on_unclaimed_gen_file() -> None:
    mod = _load_check_generated_artifacts_module()

    tracked = [
        "docs/doc/specs/openspec-index.gen.md",
        "src/scalim/_project_constants.py",
    ]
    claimed_globs = [
        "src/scalim/_project_constants.py",
    ]

    unclaimed = mod._unclaimed_generated_files(tracked, claimed_globs)
    assert unclaimed == ["docs/doc/specs/openspec-index.gen.md"]


def test_generated_artifacts_manifest_gate_accepts_claimed_gen_file() -> None:
    mod = _load_check_generated_artifacts_module()

    tracked = [
        "docs/doc/specs/openspec-index.gen.md",
    ]
    claimed_globs = [
        "docs/doc/**/*.gen.md",
    ]

    unclaimed = mod._unclaimed_generated_files(tracked, claimed_globs)
    assert unclaimed == []
