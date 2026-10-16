"""Readiness must fail on a present-but-invalid provider key (401), not only on
placeholder-shaped values. See provider_key_health.py."""

import importlib

import provider_key_health as pkh


def _reload():
    importlib.reload(pkh)
    return pkh


def test_disabled_returns_empty(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_KEY_CHECK", "off")
    module = _reload()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-present")
    assert module.provider_key_health(force=True) == {}


def test_invalid_key_fails(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_KEY_CHECK", "live")
    module = _reload()
    monkeypatch.setenv("OPENAI_API_KEY", "fe_oa_9-placeholder")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-")
    monkeypatch.setattr(module, "_probe_status", lambda provider, key: 401)
    report = module.provider_key_health(force=True)
    assert report["openai"]["ok"] is False
    assert report["openai"]["invalid"] == 1
    assert report["anthropic"]["ok"] is False


def test_valid_and_transient_keys_pass(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_KEY_CHECK", "live")
    module = _reload()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-good")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-good")
    monkeypatch.setattr(module, "_probe_status", lambda provider, key: 200)
    report = module.provider_key_health(force=True)
    assert report["openai"]["ok"] is True
    assert report["anthropic"]["ok"] is True


def test_transient_probe_does_not_fail_readiness(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_KEY_CHECK", "live")
    module = _reload()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-good")
    monkeypatch.setattr(module, "_probe_status", lambda provider, key: 0)
    report = module.provider_key_health(force=True)
    assert report["openai"]["ok"] is True
    assert report["openai"]["unknown"] == 1


def test_optional_provider_is_skipped_without_a_key(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_KEY_CHECK", "live")
    module = _reload()
    for name in ("GEMINI_API_KEY", "COHERE_API_KEY", "OPENROUTER_API_KEY", "MOONSHOT_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-good")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-good")
    monkeypatch.setattr(module, "_probe_status", lambda provider, key: 200)
    report = module.provider_key_health(force=True)
    assert set(report) == {"openai", "anthropic"}


def test_optional_provider_is_validated_when_a_key_is_present(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_KEY_CHECK", "live")
    module = _reload()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-good")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-good")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-good")
    monkeypatch.setenv("MISTRAL_API_KEY", "mistral-bad")
    monkeypatch.setattr(
        module,
        "_probe_status",
        lambda provider, key: 401 if provider == "mistral" else 200,
    )
    report = module.provider_key_health(force=True)
    assert report["google"]["ok"] is True
    assert report["google"]["required"] is False
    assert report["mistral"]["ok"] is False
    assert report["mistral"]["invalid"] == 1


def test_every_enabled_registry_provider_has_a_probe_spec():
    module = _reload()
    from model_registry import ModelRegistry

    specs = module._provider_specs()
    registry = ModelRegistry()
    for provider_id, definition in registry.providers.items():
        if not definition.enabled:
            continue
        assert provider_id in specs
        assert specs[provider_id]["url"]


def test_required_provider_missing_key_fails(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_KEY_CHECK", "live")
    module = _reload()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-good")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY_2", raising=False)
    monkeypatch.setattr(module, "_probe_status", lambda provider, key: 200)
    report = module.provider_key_health(force=True)
    assert report["anthropic"]["ok"] is False
    assert report["anthropic"]["required"] is True
