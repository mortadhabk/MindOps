import pytest

import app.agent.settings  # noqa: F401  effet de bord : enregistre la section "agent"
import app.core.logging_settings  # noqa: F401  idem, "logging"
import app.gating.settings  # noqa: F401  idem, "gating"
import app.rag.settings  # noqa: F401  idem, "rag"
from app.core.exceptions import SettingsSectionNotFoundError
from app.settings.registry import get_section, list_sections


def test_list_sections_includes_all_registered_domains():
    keys = {s.key for s in list_sections()}
    assert {"gating", "rag", "agent", "logging"}.issubset(keys)


def test_get_section_returns_matching_section():
    section = get_section("gating")
    assert section.display_name == "Gating (politique de confiance)"


def test_get_section_raises_for_unknown_key():
    with pytest.raises(SettingsSectionNotFoundError):
        get_section("does-not-exist")
