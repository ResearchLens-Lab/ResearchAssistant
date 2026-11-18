import os
import pytest
from backend.app.core.config import get_settings


def test_external_lookups_enabled_config_flag():
    """Verify EXTERNAL_LOOKUPS_ENABLED environment variable controls get_settings().external_lookups_enabled."""
    old_env = os.environ.get("EXTERNAL_LOOKUPS_ENABLED")
    try:
        # 1. When EXTERNAL_LOOKUPS_ENABLED="true"
        os.environ["EXTERNAL_LOOKUPS_ENABLED"] = "true"
        get_settings.cache_clear()
        settings_true = get_settings()
        assert settings_true.external_lookups_enabled is True

        # 2. When EXTERNAL_LOOKUPS_ENABLED is unset
        os.environ.pop("EXTERNAL_LOOKUPS_ENABLED", None)
        get_settings.cache_clear()
        settings_unset = get_settings()
        assert settings_unset.external_lookups_enabled is False

        # 3. When EXTERNAL_LOOKUPS_ENABLED="false"
        os.environ["EXTERNAL_LOOKUPS_ENABLED"] = "false"
        get_settings.cache_clear()
        settings_false = get_settings()
        assert settings_false.external_lookups_enabled is False
    finally:
        if old_env is not None:
            os.environ["EXTERNAL_LOOKUPS_ENABLED"] = old_env
        else:
            os.environ.pop("EXTERNAL_LOOKUPS_ENABLED", None)
        get_settings.cache_clear()
