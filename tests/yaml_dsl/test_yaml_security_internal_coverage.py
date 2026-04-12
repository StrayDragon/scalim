import pytest


def test_warn_full_audit_enabled_once_returns_when_event_set_inside_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.dsl.yaml_dsl._internal.config_parsing import security as security_mod

    calls = {"n": 0}

    def _fake_is_set() -> bool:
        calls["n"] += 1
        return int(calls["n"]) >= 2

    monkeypatch.setattr(security_mod._full_audit_warning_emitted, "is_set", _fake_is_set)
    security_mod._warn_full_audit_enabled_once()
