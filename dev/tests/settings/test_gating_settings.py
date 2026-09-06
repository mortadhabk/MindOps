from app.gating.settings import get_effective_gating_settings
from app.settings import store


def test_get_effective_gating_settings_uses_env_defaults_when_no_override():
    settings = get_effective_gating_settings()

    assert isinstance(settings.gating_policy, dict)
    assert 0 <= settings.gating_min_confidence <= 1


def test_get_effective_gating_settings_uses_override_when_present():
    store._overrides["gating"] = {
        "gating_policy": {"send_email": "auto_execute"},
        "gating_min_confidence": 0.5,
    }

    settings = get_effective_gating_settings()

    assert settings.gating_policy == {"send_email": "auto_execute"}
    assert settings.gating_min_confidence == 0.5


def test_policy_evaluate_reflects_the_override_immediately():
    from app.gating.policy import Decision, evaluate

    store._overrides["gating"] = {
        "gating_policy": {"send_email": "auto_execute"},
        "gating_min_confidence": 0.5,
    }

    assert evaluate("send_email", confidence=0.9) is Decision.AUTO_EXECUTE
