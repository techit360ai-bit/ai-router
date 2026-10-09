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
