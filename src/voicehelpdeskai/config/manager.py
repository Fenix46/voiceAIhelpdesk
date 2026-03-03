"""Configuration Manager - Singleton for centralized config management."""

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:  # Optional dependency for hot-reload in development
    Observer = None

    class FileSystemEventHandler:  # type: ignore[no-redef]
        pass

import yaml
from loguru import logger

from voicehelpdeskai.config.config import Settings, get_settings


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for config file changes."""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.last_modified = {}
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        file_path = event.src_path
        current_time = time.time()
        
        # Debounce: ignore rapid successive changes
        if file_path in self.last_modified:
            if current_time - self.last_modified[file_path] < 1.0:
                return
        
        self.last_modified[file_path] = current_time
        
        # Check if it's a config file we care about
        if file_path.endswith(('.yaml', '.yml', '.json', '.env')):
            logger.info(f"Config file changed: {file_path}")
            self.config_manager._reload_config_file(file_path)


class ConfigManager:
    """Singleton configuration manager with hot-reload support."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls) -> 'ConfigManager':
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the configuration manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self._lock = threading.RLock()
        
        # Load base settings
        self._settings = get_settings()
        
        # Configuration data
        self._model_config: Dict[str, Any] = {}
        self._system_prompts: Dict[str, str] = {}
        self._runtime_overrides: Dict[str, Any] = {}
        
        # File watching
        self._observer: Optional[Observer] = None
        self._watch_files: Dict[str, str] = {}
        
        # Load all configurations
        self._load_all_configs()
        
        # Setup hot-reload if in development
        if self._settings.is_development and self._settings.hot_reload:
            self._setup_hot_reload()
        
        logger.info("ConfigManager initialized successfully")
    
    def _load_all_configs(self):
        """Load all configuration files."""
        config_dir = Path(__file__).parent
        
        # Load model configuration
        model_config_path = config_dir / "model_config.yaml"
        if model_config_path.exists():
            self._model_config = self._load_yaml_file(model_config_path)
            self._watch_files[str(model_config_path)] = "model_config"
        
        # Load system prompts
        prompts_path = config_dir / "prompts" / "system_prompts.json"
        if prompts_path.exists():
            self._system_prompts = self._load_json_file(prompts_path)
            self._watch_files[str(prompts_path)] = "system_prompts"
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load YAML file {file_path}: {e}")
            return {}
    
    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Load JSON configuration file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load JSON file {file_path}: {e}")
            return {}
    
    def _setup_hot_reload(self):
        """Setup file watching for hot-reload."""
        if Observer is None:
            logger.warning("Hot-reload disabled: watchdog is not installed")
            return

        try:
            self._observer = Observer()
            handler = ConfigFileHandler(self)
            
            # Watch config directory
            config_dir = Path(__file__).parent
            self._observer.schedule(handler, str(config_dir), recursive=True)
            
            # Watch .env file if it exists
            env_file = Path(".env")
            if env_file.exists():
                self._observer.schedule(handler, str(env_file.parent), recursive=False)
                self._watch_files[str(env_file)] = "env"
            
            self._observer.start()
            logger.info("Hot-reload enabled for configuration files")
            
        except Exception as e:
            logger.warning(f"Failed to setup hot-reload: {e}")
    
    def _reload_config_file(self, file_path: str):
        """Reload a specific configuration file."""
        try:
            with self._lock:
                file_path_obj = Path(file_path)
                
                if file_path in self._watch_files:
                    config_type = self._watch_files[file_path]
                    
                    if config_type == "model_config":
                        self._model_config = self._load_yaml_file(file_path_obj)
                        logger.info("Model configuration reloaded")
                    
                    elif config_type == "system_prompts":
                        self._system_prompts = self._load_json_file(file_path_obj)
                        logger.info("System prompts reloaded")
                    
                    elif config_type == "env":
                        # Reload environment settings
                        self._settings = get_settings()
                        logger.info("Environment settings reloaded")
        
        except Exception as e:
            logger.error(f"Failed to reload config file {file_path}: {e}")
    
    def get_settings(self) -> Settings:
        """Get the main application settings."""
        return self._settings
    
    def get_model_config(self, model_type: str = None) -> Union[Dict[str, Any], Any]:
        """Get model configuration."""
        with self._lock:
            if model_type:
                return self._model_config.get(model_type, {})
            return self._model_config.copy()
    
    def get_whisper_config(self) -> Dict[str, Any]:
        """Get Whisper-specific configuration."""
        return self.get_model_config("whisper")
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM-specific configuration."""
        return self.get_model_config("llm")
    
    def get_tts_config(self) -> Dict[str, Any]:
        """Get TTS-specific configuration."""
        return self.get_model_config("tts")
    
    def get_system_prompt(self, prompt_name: str) -> Optional[str]:
        """Get a system prompt by name."""
        with self._lock:
            return self._system_prompts.get(prompt_name)
    
    def get_all_system_prompts(self) -> Dict[str, str]:
        """Get all system prompts."""
        with self._lock:
            return self._system_prompts.copy()
    
    def set_runtime_override(self, key: str, value: Any):
        """Set a runtime configuration override."""
        with self._lock:
            self._runtime_overrides[key] = value
            logger.info(f"Runtime override set: {key} = {value}")
    
    def get_runtime_override(self, key: str, default: Any = None) -> Any:
        """Get a runtime configuration override."""
        with self._lock:
            return self._runtime_overrides.get(key, default)
    
    def clear_runtime_override(self, key: str):
        """Clear a runtime configuration override."""
        with self._lock:
            if key in self._runtime_overrides:
                del self._runtime_overrides[key]
                logger.info(f"Runtime override cleared: {key}")
    
    def clear_all_runtime_overrides(self):
        """Clear all runtime configuration overrides."""
        with self._lock:
            self._runtime_overrides.clear()
            logger.info("All runtime overrides cleared")
    
    def get_config_value(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'whisper.model_name')."""
        try:
            # First check runtime overrides
            with self._lock:
                if key_path in self._runtime_overrides:
                    return self._runtime_overrides[key_path]
            
            # Parse key path
            parts = key_path.split('.')
            
            # Determine source based on first part
            if parts[0] in ['whisper', 'llm', 'tts', 'performance', 'endpoints', 'validation', 'fallback']:
                source = self._model_config
            elif parts[0] == 'prompts':
                if len(parts) == 2:
                    return self.get_system_prompt(parts[1])
                source = self._system_prompts
            else:
                # Try settings object
                source = self._settings.dict()
            
            # Navigate through nested keys
            value = source
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            
            return value
            
        except Exception as e:
            logger.error(f"Failed to get config value for {key_path}: {e}")
            return default
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate all configurations and return validation results."""
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Validate main settings
            settings = self.get_settings()
            
            # Validate model configurations
            whisper_config = self.get_whisper_config()
            llm_config = self.get_llm_config()
            tts_config = self.get_tts_config()
            
            # Check required configurations
            if not whisper_config:
                validation_results["warnings"].append("Whisper configuration is empty")
            
            if not llm_config:
                validation_results["errors"].append("LLM configuration is required")
                validation_results["valid"] = False
            
            # Validate API keys for external services
            if llm_config.get("model_type") == "openai":
                if not os.getenv("OPENAI_API_KEY") and not llm_config.get("openai", {}).get("api_key"):
                    validation_results["errors"].append("OpenAI API key is required")
                    validation_results["valid"] = False
            
            # Validate file paths
            paths_to_check = [
                settings.database.sqlite_path,
                settings.audio.audio_storage_path,
                settings.logging.file_path,
            ]
            
            for path in paths_to_check:
                if path and not Path(path).parent.exists():
                    try:
                        Path(path).parent.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        validation_results["warnings"].append(f"Cannot create directory for {path}: {e}")
            
            # Validate system prompts
            prompts = self.get_all_system_prompts()
            if not prompts:
                validation_results["warnings"].append("No system prompts loaded")
            
            logger.info(f"Configuration validation completed: {'PASSED' if validation_results['valid'] else 'FAILED'}")
            
        except Exception as e:
            validation_results["valid"] = False
            validation_results["errors"].append(f"Configuration validation failed: {e}")
            logger.error(f"Configuration validation error: {e}")
        
        return validation_results
    
    def export_config_summary(self) -> Dict[str, Any]:
        """Export a summary of current configuration."""
        with self._lock:
            return {
                "settings": {
                    "app_name": self._settings.app_name,
                    "environment": self._settings.environment,
                    "debug": self._settings.debug,
                    "features": self._settings.features,
                },
                "model_config": {
                    "whisper": {
                        "model_name": self._model_config.get("whisper", {}).get("model_name"),
                        "language": self._model_config.get("whisper", {}).get("language"),
                    },
                    "llm": {
                        "model_name": self._model_config.get("llm", {}).get("model_name"),
                        "model_type": self._model_config.get("llm", {}).get("model_type"),
                    },
                    "tts": {
                        "engine": self._model_config.get("tts", {}).get("engine"),
                        "voice_model": self._model_config.get("tts", {}).get("voice_model"),
                    }
                },
                "runtime_overrides": self._runtime_overrides.copy(),
                "system_prompts_count": len(self._system_prompts),
                "hot_reload_enabled": self._observer is not None,
            }
    
    def shutdown(self):
        """Shutdown the configuration manager."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("Configuration file watching stopped")
        
        logger.info("ConfigManager shutdown completed")
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            self.shutdown()
        except:
            pass


# Global instance
_config_manager = None
_config_manager_lock = threading.Lock()


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    
    if _config_manager is None:
        with _config_manager_lock:
            if _config_manager is None:
                _config_manager = ConfigManager()
    
    return _config_manager


# Convenience functions
def get_whisper_config() -> Dict[str, Any]:
    """Get Whisper configuration."""
    return get_config_manager().get_whisper_config()


def get_llm_config() -> Dict[str, Any]:
    """Get LLM configuration."""
    return get_config_manager().get_llm_config()


def get_tts_config() -> Dict[str, Any]:
    """Get TTS configuration."""
    return get_config_manager().get_tts_config()


def get_system_prompt(prompt_name: str) -> Optional[str]:
    """Get system prompt by name."""
    return get_config_manager().get_system_prompt(prompt_name)


def get_config_value(key_path: str, default: Any = None) -> Any:
    """Get configuration value using dot notation."""
    return get_config_manager().get_config_value(key_path, default)
