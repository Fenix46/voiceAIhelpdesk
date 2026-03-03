"""Legacy configuration module - now redirects to new config system."""

import warnings
from functools import lru_cache

# Import from new configuration system
from voicehelpdeskai.config.config import Settings as NewSettings, get_settings as get_new_settings
from voicehelpdeskai.config.manager import get_config_manager


class Settings:
    """Legacy Settings class that wraps the new configuration system."""
    
    def __init__(self):
        """Initialize legacy settings wrapper."""
        warnings.warn(
            "The core.config module is deprecated. Use voicehelpdeskai.config instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._new_settings = get_new_settings()
        self._config_manager = get_config_manager()
    
    def __getattr__(self, name):
        """Delegate attribute access to new settings."""
        return getattr(self._new_settings, name)
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self._new_settings.is_development
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self._new_settings.is_production
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self._new_settings.is_testing


@lru_cache()
def get_settings() -> Settings:
    """Get cached legacy settings instance."""
    warnings.warn(
        "get_settings from core.config is deprecated. Use voicehelpdeskai.config.get_settings instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return Settings()


# Global settings instance (legacy)
settings = get_settings()

# Also expose the new settings for migration
new_settings = get_new_settings()