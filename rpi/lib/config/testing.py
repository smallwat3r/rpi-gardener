"""Test utilities for configuration.

This module provides helpers for overriding settings in tests. It should NOT
be imported in production code.
"""

import rpi.lib.config.settings as _settings_module
from rpi.lib.config.settings import Settings, _load_settings


def set_settings(settings: Settings | None) -> None:
    """Set or clear the global settings override for testing.

    Pass a Settings instance to override the global settings, or None to
    clear the override and revert to environment-based settings.

    Args:
        settings: Settings instance to use, or None to clear override.
    """
    _settings_module._settings_override = settings
    _load_settings.cache_clear()
