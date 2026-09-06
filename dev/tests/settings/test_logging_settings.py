from app.core import logging_settings
from app.settings import store


def test_get_effective_log_level_uses_env_default_when_no_override():
    assert logging_settings.get_effective_log_level() in {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }


def test_get_effective_log_level_uses_override_when_present():
    store._overrides["logging"] = {"log_level": "debug"}

    assert logging_settings.get_effective_log_level() == "DEBUG"


def test_apply_reconfigures_the_root_logger(monkeypatch):
    calls = []
    monkeypatch.setattr(logging_settings, "configure_logging", lambda level: calls.append(level))

    logging_settings._apply({"log_level": "DEBUG"})

    assert calls == ["DEBUG"]
