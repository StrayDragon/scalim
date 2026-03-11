import sys
from pathlib import Path

import pytest

from scalim.dsl.by_yaml import RunOptions, compile as compile_yaml
from scalim.dsl.by_yaml.config_parsing.call_by import CallByParseError, parse_call_by
from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml.runtime.errors import ResolverError
from scalim.dsl.by_yaml.runtime import compiler as compiler_module
from scalim.dsl.by_yaml.runtime.references import SecurePythonReferenceResolver, derive_base_module_path
from scalim.dsl.by_yaml.schema_dsl.models import DemandConfig, DerivedFieldConfig, LoaderRetryConfig, MainSourceConfig, SourceConfig


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _purge_modules(prefix: str) -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            del sys.modules[name]


def _prepare_pkg(tmp_path: Path) -> Path:
    _write_text(tmp_path / "relpkg/__init__.py", "")
    _write_text(tmp_path / "relpkg/sub/__init__.py", "")
    _write_text(
        tmp_path / "relpkg/sub/loaders.py",
        "\n".join(
            [
                "def dummy_main_loader(**_kwargs):  # type: ignore[no-untyped-def]",
                "    return []",
                "",
                "def ping():",
                "    return 'sub'",
                "",
            ]
        )
        + "\n",
    )
    _write_text(
        tmp_path / "relpkg/common.py",
        "\n".join(
            [
                "def ping():",
                "    return 'common'",
                "",
            ]
        )
        + "\n",
    )
    yaml_path = tmp_path / "relpkg/sub/config.yaml"
    _write_text(
        yaml_path,
        "\n".join(
            [
                "name: demo",
                "main_source:",
                "  source_id: orders",
                '  loader: ".loaders:dummy_main_loader"',
                "  fields:",
                "    status:",
                "      extract: status",
                "",
            ]
        ),
    )
    return yaml_path


def test_derive_base_module_path_supports_sys_path_overrides(tmp_path: Path) -> None:
    yaml_path = tmp_path / "relpkg/sub/config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    base = derive_base_module_path(
        str(yaml_path),
        sys_path=[None, "", "relative_root", str(tmp_path)],  # type: ignore[list-item]
        cwd=str(tmp_path),
    )
    assert base == "relpkg.sub"


def test_derive_base_module_path_returns_empty_when_yaml_dir_is_sys_path_root(tmp_path: Path) -> None:
    yaml_path = tmp_path / "config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    base = derive_base_module_path(str(yaml_path), sys_path=[str(tmp_path)], cwd=str(tmp_path))
    assert base == ""


def test_derive_base_module_path_reads_sys_path_when_not_provided(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = tmp_path / "pkg/config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    monkeypatch.setattr(sys, "path", [str(tmp_path)])
    base = derive_base_module_path(str(yaml_path))
    assert base == "pkg"


def test_derive_base_module_path_errors_on_missing_yaml_path() -> None:
    with pytest.raises(ResolverError, match="yaml_path is required"):
        derive_base_module_path("")


def test_derive_base_module_path_errors_when_no_candidate_sys_path_prefix(tmp_path: Path) -> None:
    yaml_path = tmp_path / "relpkg/sub/config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    with pytest.raises(ResolverError, match="not under any sys\\.path entry"):
        derive_base_module_path(str(yaml_path), sys_path=[], cwd=str(tmp_path))


def test_derive_base_module_path_errors_on_non_identifier_segment(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad-name/sub/config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    with pytest.raises(ResolverError, match="not a valid Python identifier"):
        derive_base_module_path(str(yaml_path), sys_path=[str(tmp_path)], cwd=str(tmp_path))


def test_secure_resolver_normalizes_relative_reference_and_enforces_allowlist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = _prepare_pkg(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _purge_modules("relpkg")

    base = derive_base_module_path(str(yaml_path))
    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["relpkg"]), base_module_path=base)

    assert base == "relpkg.sub"

    assert resolver.resolve(".loaders:ping")() == "sub"
    assert resolver.resolve(".loaders.ping")() == "sub"
    assert resolver.resolve("..common:ping")() == "common"

    with pytest.raises(ResolverError, match="not in the allowed modules list"):
        SecurePythonReferenceResolver(allowed_modules=frozenset(["relpkg.sub"]), base_module_path=base).resolve("..common:ping")


def test_secure_resolver_errors_when_base_module_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = _prepare_pkg(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _purge_modules("relpkg")

    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["relpkg"]))
    with pytest.raises(ResolverError, match="requires a base module path"):
        resolver.resolve(".loaders:ping")


def test_secure_resolver_errors_for_relative_syntax_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = _prepare_pkg(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _purge_modules("relpkg")

    base = derive_base_module_path(str(yaml_path))
    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["relpkg"]), base_module_path=base)

    with pytest.raises(ResolverError, match="missing module path after leading dots"):
        resolver.resolve(".:ping")
    with pytest.raises(ResolverError, match="Invalid class-style reference"):
        resolver.resolve(".loaders:ping:extra")
    with pytest.raises(ResolverError, match="Invalid relative dotted reference"):
        SecurePythonReferenceResolver().resolve(".ping")
    with pytest.raises(ResolverError, match="goes beyond root"):
        resolver.resolve("....loaders:ping")
    with pytest.raises(ResolverError, match="illegal identifier segment"):
        resolver.resolve(".bad-name:ping")


def test_compile_raises_clear_error_when_relative_reference_cannot_derive_base_module(tmp_path: Path) -> None:
    yaml_path = _prepare_pkg(tmp_path)
    _purge_modules("relpkg")

    with pytest.raises(ResolverError, match="Cannot derive base module path"):
        compile_yaml(
            str(yaml_path),
            allowed_modules=frozenset(["relpkg"]),
        )


def test_compile_accepts_relative_and_absolute_loader_refs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = _prepare_pkg(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _purge_modules("relpkg")

    _ = compile_yaml(str(yaml_path), allowed_modules=frozenset(["relpkg"]))

    abs_yaml_path = tmp_path / "relpkg/sub/abs.yaml"
    _write_text(
        abs_yaml_path,
        "\n".join(
            [
                "name: demo",
                "main_source:",
                "  source_id: orders",
                '  loader: "relpkg.sub.loaders:dummy_main_loader"',
                "  fields:",
                "    status:",
                "      extract: status",
                "",
            ]
        ),
    )
    _ = compile_yaml(str(abs_yaml_path), allowed_modules=frozenset(["relpkg"]))


def test_config_validator_and_call_by_parser_accept_relative_references() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "retry": {"should_retry": ".retry:should_retry"},
        "main_source": {
            "source_id": "orders",
            "loader": ".loaders:load_orders",
            "fields": {
                "status": {"extract": "status"},
            },
        },
        "sources": {},
        "fields": {
            "text": {"call_by": ".call_by_fns:echo(status)"},
        },
    }
    validator.validate(config)

    parsed = parse_call_by(".call_by_fns:echo(status)")
    assert parsed.reference == ".call_by_fns:echo"


def test_config_validator_and_call_by_parser_reject_invalid_relative_references() -> None:
    validator = ConfigValidator()
    bad = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": ".:load_orders",
        },
        "sources": {},
        "fields": {},
    }

    with pytest.raises(ConfigValidationError):
        validator.validate(bad)

    bad_dotted = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": ".load_orders",
        },
        "sources": {},
        "fields": {},
    }
    with pytest.raises(ConfigValidationError):
        validator.validate(bad_dotted)

    bad_retry = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "abs.mod:load_orders"},
        "sources": {},
        "fields": {},
        "retry": {"should_retry": ".:should_retry"},
    }
    with pytest.raises(ConfigValidationError):
        validator.validate(bad_retry)

    with pytest.raises(CallByParseError, match="Invalid call_by reference"):
        parse_call_by(".:echo(status)")


def test_validator_retry_block_must_be_mapping() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "retry": ["bad"],
        "main_source": {
            "source_id": "orders",
            "loader": "abs.mod:load_orders",
            "fields": {"status": {"extract": "status"}},
        },
        "sources": {},
        "fields": {},
    }

    with pytest.raises(ConfigValidationError) as excinfo:
        validator.validate(config)
    assert any("retry: 'retry' must be a dictionary" in item for item in excinfo.value.errors)


def test_validator_retry_should_retry_allows_null() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "retry": {"should_retry": None},
        "main_source": {
            "source_id": "orders",
            "loader": "abs.mod:load_orders",
            "fields": {"status": {"extract": "status"}},
        },
        "sources": {},
        "fields": {},
    }
    report = validator.validate_report(config, enable_jsonschema_validation=False)
    assert report.errors() == []


def test_validator_retry_should_retry_must_be_string() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
        "retry": {"should_retry": 123},
        "main_source": {
            "source_id": "orders",
            "loader": "abs.mod:load_orders",
            "fields": {"status": {"extract": "status"}},
        },
        "sources": {},
        "fields": {},
    }

    with pytest.raises(ConfigValidationError) as excinfo:
        validator.validate(config)
    assert any("retry.should_retry" in item and "must be a string" in item for item in excinfo.value.errors)


def test_run_options_accepts_allowed_modules_for_relative_loader_smoke() -> None:
    # Ensure the public-facing typing contract remains stable when the options object is constructed.
    _ = RunOptions(allowed_modules=frozenset(["relpkg"]))


def test_config_uses_relative_references_return_paths() -> None:
    base = DemandConfig(
        name="demo",
        main_source=MainSourceConfig(source_id="orders", loader="abs.mod:fn"),
    )
    assert compiler_module._config_uses_relative_references(base) is False  # noqa: SLF001

    src_loader = DemandConfig(
        name=base.name,
        main_source=base.main_source,
        sources={
            "s1": SourceConfig(source_id="s1", loader=".loaders:fn", key="id"),
        },
    )
    assert compiler_module._config_uses_relative_references(src_loader) is True  # noqa: SLF001

    src_retry = DemandConfig(
        name=base.name,
        main_source=base.main_source,
        sources={
            "s1": SourceConfig(
                source_id="s1",
                loader="abs.mod:fn",
                key="id",
                retry=LoaderRetryConfig(should_retry=".retry:should_retry"),
            ),
        },
    )
    assert compiler_module._config_uses_relative_references(src_retry) is True  # noqa: SLF001

    global_retry = DemandConfig(
        name=base.name,
        main_source=base.main_source,
        retry=LoaderRetryConfig(should_retry=".retry:should_retry"),
    )
    assert compiler_module._config_uses_relative_references(global_retry) is True  # noqa: SLF001

    main_retry = DemandConfig(
        name=base.name,
        main_source=MainSourceConfig(
            source_id="orders",
            loader=base.main_source.loader,
            retry=LoaderRetryConfig(should_retry=".retry:should_retry"),
        ),
    )
    assert compiler_module._config_uses_relative_references(main_retry) is True  # noqa: SLF001

    derived_call = DemandConfig(
        name=base.name,
        main_source=base.main_source,
        derived_fields={
            "d1": DerivedFieldConfig(field_id="d1", name="d1", call_by=".fns:echo(a)"),
        },
    )
    assert compiler_module._config_uses_relative_references(derived_call) is True  # noqa: SLF001
