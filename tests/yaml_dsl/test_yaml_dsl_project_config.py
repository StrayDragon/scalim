from pathlib import Path

import pytest

from scalim.dsl.by_yaml._internal.config_parsing import imports as imports_mod
from scalim.dsl.by_yaml._internal.config_parsing import presets as presets_mod
from scalim.dsl.by_yaml._internal.config_parsing import project_config as project_config_mod
from scalim.dsl.by_yaml._internal.config_parsing.error_envelope import ScalimYamlValidationError


def test_parse_scalim_preset_uri_rejects_non_scalim_scheme() -> None:
    with pytest.raises(ValueError) as excinfo:
        _ = imports_mod._parse_scalim_preset_uri("file:///tmp/x.yaml")  # noqa: SLF001
    assert "Expected scalim:// preset URI" in str(excinfo.value)


def test_parse_scalim_preset_uri_rejects_empty_id() -> None:
    with pytest.raises(ValueError) as excinfo:
        _ = imports_mod._parse_scalim_preset_uri("scalim://")  # noqa: SLF001
    assert "preset id cannot be empty" in str(excinfo.value)


def test_apply_import_aliases_skips_empty_and_returns_none_for_no_match(tmp_path: Path) -> None:
    cfg = project_config_mod.YamlDslProjectConfig(
        scalim_yaml_path=tmp_path / "scalim.yaml",
        project_root=tmp_path,
        import_aliases={"": tmp_path, "COMMON": tmp_path},
        import_allowed_roots=(),
    )
    assert imports_mod._apply_import_aliases("not-match.yaml", project_config=cfg) is None  # noqa: SLF001


def test_apply_import_aliases_supports_non_at_prefix_syntax(tmp_path: Path) -> None:
    cfg = project_config_mod.YamlDslProjectConfig(
        scalim_yaml_path=tmp_path / "scalim.yaml",
        project_root=tmp_path,
        import_aliases={"COMMON": tmp_path},
        import_allowed_roots=(),
    )
    remainder, base_dir = imports_mod._apply_import_aliases("COMMON:/x.yaml", project_config=cfg)  # noqa: SLF001
    assert remainder == "x.yaml"
    assert base_dir == tmp_path


def test_parse_import_source_requires_base_dir_for_file_paths() -> None:
    with pytest.raises(ValueError) as excinfo:
        _ = imports_mod._parse_import_source(  # noqa: SLF001
            "a",
            "./x.yaml",
            base_dir=None,
            project_config=None,
            allowed_yaml_roots=(),
        )
    assert "require base_dir" in str(excinfo.value)


def test_load_yaml_mapping_from_source_rejects_file_source_missing_path() -> None:
    source = imports_mod.ImportSource(kind="file", key="/tmp/x.yaml", path=None)
    with pytest.raises(ValueError) as excinfo:
        _ = imports_mod._load_yaml_mapping_from_source(  # noqa: SLF001
            source,
            template_vars=None,
            template_sandbox="safe",
            rendered_yaml_max_len=imports_mod.DEFAULT_RENDERED_YAML_MAX_LEN,
        )
    assert "requires path" in str(excinfo.value)


def test_load_yaml_mapping_from_source_rejects_preset_source_missing_preset_id() -> None:
    source = imports_mod.ImportSource(kind="preset", key="scalim://x", preset_id=None)
    with pytest.raises(ValueError) as excinfo:
        _ = imports_mod._load_yaml_mapping_from_source(  # noqa: SLF001
            source,
            template_vars=None,
            template_sandbox="safe",
            rendered_yaml_max_len=imports_mod.DEFAULT_RENDERED_YAML_MAX_LEN,
        )
    assert "requires preset_id" in str(excinfo.value)


def test_load_yaml_mapping_from_source_rejects_non_mapping_preset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imports_mod, "load_scalim_preset_yaml_text", lambda _preset_id: "- 1\n")
    source = imports_mod.ImportSource(kind="preset", key="scalim://bad", preset_id="bad")
    with pytest.raises(ScalimYamlValidationError) as excinfo:
        _ = imports_mod._load_yaml_mapping_from_source(  # noqa: SLF001
            source,
            template_vars=None,
            template_sandbox="safe",
            rendered_yaml_max_len=imports_mod.DEFAULT_RENDERED_YAML_MAX_LEN,
        )
    assert any(env.code == "yaml_root_not_mapping" for env in excinfo.value.errors)


def test_load_yaml_mapping_from_source_rejects_unknown_kind() -> None:
    source = imports_mod.ImportSource(kind="nope", key="nope")
    with pytest.raises(ValueError) as excinfo:
        _ = imports_mod._load_yaml_mapping_from_source(  # noqa: SLF001
            source,
            template_vars=None,
            template_sandbox="safe",
            rendered_yaml_max_len=imports_mod.DEFAULT_RENDERED_YAML_MAX_LEN,
        )
    assert "Unknown ImportSource.kind" in str(excinfo.value)


def test_load_scalim_preset_yaml_text_rejects_empty_id() -> None:
    with pytest.raises(ValueError) as excinfo:
        _ = presets_mod.load_scalim_preset_yaml_text("")
    assert "preset id cannot be empty" in str(excinfo.value)


def test_load_scalim_preset_yaml_text_rejects_unknown_id() -> None:
    with pytest.raises(ValueError) as excinfo:
        _ = presets_mod.load_scalim_preset_yaml_text("yaml-dsl/presets/missing.yaml")
    assert "Unknown scalim:// preset id" in str(excinfo.value)


def test_project_config_empty_scalim_yaml_loads_empty_config(tmp_path: Path) -> None:
    scalim_yaml = tmp_path / "scalim.yaml"
    scalim_yaml.write_text("", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    cfg = project_config_mod.load_yaml_dsl_project_config(demand)
    assert cfg is not None
    assert cfg.import_aliases == {}
    assert cfg.import_allowed_roots == ()


def test_project_config_scalim_yaml_must_be_mapping(tmp_path: Path) -> None:
    (tmp_path / "scalim.yaml").write_text("[]\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    with pytest.raises(TypeError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand)
    assert "must be a mapping" in str(excinfo.value)


def test_project_config_yaml_dsl_must_be_mapping(tmp_path: Path) -> None:
    (tmp_path / "scalim.yaml").write_text("yaml_dsl: 1\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    with pytest.raises(TypeError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand)
    assert "yaml_dsl must be a mapping" in str(excinfo.value)


def test_project_config_import_aliases_must_be_mapping(tmp_path: Path) -> None:
    (tmp_path / "scalim.yaml").write_text("yaml_dsl:\n  import_aliases: []\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    with pytest.raises(TypeError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand)
    assert "import_aliases must be a mapping" in str(excinfo.value)


def test_project_config_import_aliases_keys_must_be_non_empty_strings(tmp_path: Path) -> None:
    (tmp_path / "scalim.yaml").write_text("yaml_dsl:\n  import_aliases:\n    1: ./\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    with pytest.raises(TypeError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand)
    assert "keys must be non-empty strings" in str(excinfo.value)


def test_project_config_import_aliases_dir_must_be_non_empty(tmp_path: Path) -> None:
    (tmp_path / "scalim.yaml").write_text('yaml_dsl:\n  import_aliases: {"@": ""}\n', encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    with pytest.raises(TypeError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand)
    assert "must be a non-empty directory path" in str(excinfo.value)


def test_project_config_import_aliases_dir_must_exist_and_be_dir(tmp_path: Path) -> None:
    (tmp_path / "scalim.yaml").write_text('yaml_dsl:\n  import_aliases: {"@": "./missing"}\n', encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand)
    assert "must be an existing directory" in str(excinfo.value)


def test_project_config_import_allowed_roots_must_be_list(tmp_path: Path) -> None:
    (tmp_path / "scalim.yaml").write_text("yaml_dsl:\n  import_allowed_roots: ./\n", encoding="utf-8")
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    with pytest.raises(TypeError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand)
    assert "import_allowed_roots must be a list" in str(excinfo.value)


def test_project_config_scalim_yaml_override_must_exist_and_be_file(tmp_path: Path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand, scalim_yaml_override=tmp_path / "missing.yaml")
    assert "override must exist and be a file" in str(excinfo.value)


def test_project_config_project_root_override_must_contain_scalim_yaml(tmp_path: Path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text("name: demo\nsources: {}\n", encoding="utf-8")
    other_root = tmp_path / "other"
    other_root.mkdir(parents=True)
    with pytest.raises(ValueError) as excinfo:
        _ = project_config_mod.load_yaml_dsl_project_config(demand, project_root_override=other_root)
    assert "does not contain scalim.yaml" in str(excinfo.value)
