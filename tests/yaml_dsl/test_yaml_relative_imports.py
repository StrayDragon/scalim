import sys
from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import RunOptions, compile as compile_yaml
from scalim.dsl.yaml_dsl._internal.config_parsing.call_by import ScalimCallByParseError, parse_call_by
from scalim.dsl.yaml_dsl._internal.config_parsing.errors import ScalimConfigValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.yaml_dsl.runtime.errors import ScalimResolverError
from scalim.dsl.yaml_dsl.runtime import compiler as compiler_module
from scalim.dsl.yaml_dsl.runtime.references import SecurePythonReferenceResolver, derive_base_module_path
from scalim.dsl.yaml_dsl.schema_dsl.models import DemandConfig, DerivedFieldConfig, LoaderRetryConfig, MainSourceConfig, SourceConfig


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


def test_derive_base_module_path_prefers_non_empty_module_path_when_yaml_dir_is_in_sys_path(tmp_path: Path) -> None:
    yaml_path = tmp_path / "relpkg/sub/config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    yaml_dir = yaml_path.parent
    base = derive_base_module_path(
        str(yaml_path),
        sys_path=[str(yaml_dir), str(tmp_path)],
        cwd=str(tmp_path),
    )
    assert base == "relpkg.sub"


def test_derive_base_module_path_reads_sys_path_when_not_provided(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = tmp_path / "pkg/config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    monkeypatch.setattr(sys, "path", [str(tmp_path)])
    base = derive_base_module_path(str(yaml_path))
    assert base == "pkg"


def test_derive_base_module_path_errors_on_missing_yaml_path() -> None:
    with pytest.raises(ScalimResolverError, match="必须提供 `yaml_path`"):
        derive_base_module_path("")


def test_derive_base_module_path_errors_when_no_candidate_sys_path_prefix(tmp_path: Path) -> None:
    yaml_path = tmp_path / "relpkg/sub/config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    with pytest.raises(ScalimResolverError, match="不在任何 `sys\\.path` 条目下"):
        derive_base_module_path(str(yaml_path), sys_path=[], cwd=str(tmp_path))


def test_derive_base_module_path_errors_on_non_identifier_segment(tmp_path: Path) -> None:
    yaml_path = tmp_path / "bad-name/sub/config.yaml"
    _write_text(yaml_path, "name: demo\nmain_source: {source_id: a, loader: x.y:z}\n")

    with pytest.raises(ScalimResolverError, match="不是合法的 Python 标识符"):
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

    with pytest.raises(ScalimResolverError, match="不在 `allowed_modules` 允许列表中"):
        SecurePythonReferenceResolver(allowed_modules=frozenset(["relpkg.sub"]), base_module_path=base).resolve("..common:ping")


def test_secure_resolver_errors_when_base_module_is_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = _prepare_pkg(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _purge_modules("relpkg")

    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["relpkg"]))
    with pytest.raises(ScalimResolverError, match="需要先根据 `yaml_path` \\+ `sys\\.path` 推导 `base_module_path`"):
        resolver.resolve(".loaders:ping")


def test_secure_resolver_errors_for_relative_syntax_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = _prepare_pkg(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _purge_modules("relpkg")

    base = derive_base_module_path(str(yaml_path))
    resolver = SecurePythonReferenceResolver(allowed_modules=frozenset(["relpkg"]), base_module_path=base)

    with pytest.raises(ScalimResolverError, match="前导点后缺少模块路径"):
        resolver.resolve(".:ping")
    with pytest.raises(ScalimResolverError, match="类式引用 .* 非法"):
        resolver.resolve(".loaders:ping:extra")
    with pytest.raises(ScalimResolverError, match="相对点号引用 .* 非法"):
        SecurePythonReferenceResolver().resolve(".ping")
    with pytest.raises(ScalimResolverError, match="超出了根包范围"):
        resolver.resolve("....loaders:ping")
    with pytest.raises(ScalimResolverError, match="模块路径 .* 非法"):
        resolver.resolve(".bad-name:ping")


def test_compile_raises_clear_error_when_relative_reference_cannot_derive_base_module(tmp_path: Path) -> None:
    yaml_path = _prepare_pkg(tmp_path)
    _purge_modules("relpkg")

    with pytest.raises(ScalimResolverError, match="无法根据 `yaml_path="):
        compile_yaml(
            str(yaml_path),
            options=RunOptions(allowed_modules=frozenset(["relpkg"])),
        )


def test_compile_accepts_relative_and_absolute_loader_refs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    yaml_path = _prepare_pkg(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    _purge_modules("relpkg")

    _ = compile_yaml(str(yaml_path), options=RunOptions(allowed_modules=frozenset(["relpkg"])))

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
    _ = compile_yaml(str(abs_yaml_path), options=RunOptions(allowed_modules=frozenset(["relpkg"])))


def test_config_validator_and_call_by_parser_accept_relative_references() -> None:
    validator = ConfigValidator()
    config = {
        "name": "demo",
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

    with pytest.raises(ScalimConfigValidationError):
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
    with pytest.raises(ScalimConfigValidationError):
        validator.validate(bad_dotted)

    with pytest.raises(ScalimCallByParseError, match="`call_by` 引用 .* 非法"):
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

    with pytest.raises(ScalimConfigValidationError) as excinfo:
        validator.validate(config)
    assert any("retry: YAML key 'retry' was moved out of YAML mainline" in item for item in excinfo.value.errors)


def test_validator_retry_should_retry_rejects_null() -> None:
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
    with pytest.raises(ScalimConfigValidationError) as excinfo:
        validator.validate(config)
    assert any("retry: YAML key 'retry' was moved out of YAML mainline" in item for item in excinfo.value.errors)


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

    with pytest.raises(ScalimConfigValidationError) as excinfo:
        validator.validate(config)
    assert any("retry: YAML key 'retry' was moved out of YAML mainline" in item for item in excinfo.value.errors)


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
