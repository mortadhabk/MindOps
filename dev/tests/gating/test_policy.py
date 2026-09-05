from types import SimpleNamespace

from app.gating.policy import Decision, evaluate


def _settings(policy: dict[str, str], min_confidence: float = 0.8) -> SimpleNamespace:
    return SimpleNamespace(gating_policy=policy, gating_min_confidence=min_confidence)


def test_evaluate_returns_suggest_only(monkeypatch):
    monkeypatch.setattr(
        "app.gating.policy.get_settings", lambda: _settings({"send_email": "suggest_only"})
    )
    assert evaluate("send_email", confidence=1.0) is Decision.SUGGEST_ONLY


def test_evaluate_returns_require_validation(monkeypatch):
    monkeypatch.setattr(
        "app.gating.policy.get_settings", lambda: _settings({"send_email": "require_validation"})
    )
    assert evaluate("send_email", confidence=1.0) is Decision.REQUIRE_VALIDATION


def test_evaluate_returns_auto_execute_above_confidence_threshold(monkeypatch):
    monkeypatch.setattr(
        "app.gating.policy.get_settings",
        lambda: _settings({"send_email": "auto_execute"}, min_confidence=0.8),
    )
    assert evaluate("send_email", confidence=0.95) is Decision.AUTO_EXECUTE


def test_evaluate_falls_back_to_require_validation_below_confidence_threshold(monkeypatch):
    monkeypatch.setattr(
        "app.gating.policy.get_settings",
        lambda: _settings({"send_email": "auto_execute"}, min_confidence=0.8),
    )
    assert evaluate("send_email", confidence=0.4) is Decision.REQUIRE_VALIDATION


def test_evaluate_defaults_unconfigured_action_type_to_require_validation(monkeypatch):
    monkeypatch.setattr("app.gating.policy.get_settings", lambda: _settings({}))
    assert evaluate("create_ticket", confidence=1.0) is Decision.REQUIRE_VALIDATION
