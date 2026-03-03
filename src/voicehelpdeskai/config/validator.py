"""Configuration validation utilities."""

import os
from pathlib import Path
from typing import Dict, Any, List

from loguru import logger

from voicehelpdeskai.config.manager import get_config_manager


class ConfigValidator:
    """Configuration validation and health check utilities."""
    
    def __init__(self):
        """Initialize the configuration validator."""
        self.config_manager = get_config_manager()
    
    def validate_all(self) -> Dict[str, Any]:
        """Perform comprehensive configuration validation."""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": [],
            "sections": {}
        }
        
        # Validate each section
        results["sections"]["settings"] = self._validate_settings()
        results["sections"]["database"] = self._validate_database_config()
        results["sections"]["ai_models"] = self._validate_ai_models_config()
        results["sections"]["audio"] = self._validate_audio_config()
        results["sections"]["redis"] = self._validate_redis_config()
        results["sections"]["api"] = self._validate_api_config()
        results["sections"]["logging"] = self._validate_logging_config()
        results["sections"]["file_paths"] = self._validate_file_paths()
        results["sections"]["system_prompts"] = self._validate_system_prompts()
        
        # Collect overall results
        for section_name, section_result in results["sections"].items():
            if not section_result.get("valid", True):
                results["valid"] = False
            results["errors"].extend(section_result.get("errors", []))
            results["warnings"].extend(section_result.get("warnings", []))
            results["info"].extend(section_result.get("info", []))
        
        return results
    
    def _validate_settings(self) -> Dict[str, Any]:
        """Validate main application settings."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            settings = self.config_manager.get_settings()
            
            # Check required fields
            if not hasattr(settings, 'app_name') or not settings.app_name:
                result["errors"].append("app_name is required")
                result["valid"] = False
            
            # Check environment
            valid_environments = ["development", "testing", "staging", "production"]
            if settings.environment not in valid_environments:
                result["warnings"].append(f"Unusual environment: {settings.environment}")
            
            # Check debug mode in production
            if settings.environment == "production" and settings.debug:
                result["warnings"].append("Debug mode is enabled in production")
            
            result["info"].append(f"Environment: {settings.environment}")
            result["info"].append(f"Debug mode: {settings.debug}")
            
        except Exception as e:
            result["errors"].append(f"Settings validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def _validate_database_config(self) -> Dict[str, Any]:
        """Validate database configuration."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            settings = self.config_manager.get_settings()
            
            # Check database URL/path
            db_config = settings.database
            if "sqlite" in settings.database_url:
                # Validate SQLite path
                db_path = Path(db_config.sqlite_path)
                if not db_path.parent.exists():
                    try:
                        db_path.parent.mkdir(parents=True, exist_ok=True)
                        result["info"].append(f"Created database directory: {db_path.parent}")
                    except Exception as e:
                        result["errors"].append(f"Cannot create database directory: {e}")
                        result["valid"] = False
            
            # Check connection pool settings
            if db_config.pool_size < 1:
                result["errors"].append("Database pool_size must be at least 1")
                result["valid"] = False
            
            if db_config.pool_size > 20:
                result["warnings"].append(f"Large pool size: {db_config.pool_size}")
            
            result["info"].append(f"Database type: {'SQLite' if 'sqlite' in settings.database_url else 'Other'}")
            result["info"].append(f"Pool size: {db_config.pool_size}")
            
        except Exception as e:
            result["errors"].append(f"Database config validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def _validate_ai_models_config(self) -> Dict[str, Any]:
        """Validate AI models configuration."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            whisper_config = self.config_manager.get_whisper_config()
            llm_config = self.config_manager.get_llm_config()
            tts_config = self.config_manager.get_tts_config()
            
            # Validate Whisper config
            if whisper_config:
                valid_whisper_models = ["tiny", "base", "small", "medium", "large", "large-v2"]
                model_name = whisper_config.get("model_name", "")
                if model_name and model_name not in valid_whisper_models:
                    result["warnings"].append(f"Unusual Whisper model: {model_name}")
                result["info"].append(f"Whisper model: {model_name}")
            
            # Validate LLM config
            if llm_config:
                model_type = llm_config.get("model_type", "")
                if model_type == "openai":
                    # Check for API key
                    api_key = (os.getenv("OPENAI_API_KEY") or 
                              llm_config.get("openai", {}).get("api_key"))
                    if not api_key:
                        result["errors"].append("OpenAI API key is required for OpenAI model type")
                        result["valid"] = False
                
                # Check temperature
                temp = llm_config.get("temperature", 0.7)
                if temp < 0 or temp > 2:
                    result["warnings"].append(f"Unusual temperature value: {temp}")
                
                result["info"].append(f"LLM type: {model_type}")
                result["info"].append(f"LLM model: {llm_config.get('model_name', 'N/A')}")
            
            # Validate TTS config
            if tts_config:
                engine = tts_config.get("engine", "")
                result["info"].append(f"TTS engine: {engine}")
            
        except Exception as e:
            result["errors"].append(f"AI models config validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def _validate_audio_config(self) -> Dict[str, Any]:
        """Validate audio configuration."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            settings = self.config_manager.get_settings()
            audio_config = settings.audio
            
            # Check sample rate
            valid_sample_rates = [8000, 16000, 22050, 44100, 48000]
            if audio_config.sample_rate not in valid_sample_rates:
                result["warnings"].append(f"Unusual sample rate: {audio_config.sample_rate}")
            
            # Check chunk size
            if audio_config.chunk_size < 256 or audio_config.chunk_size > 8192:
                result["warnings"].append(f"Unusual chunk size: {audio_config.chunk_size}")
            
            # Check audio storage path
            storage_path = Path(audio_config.audio_storage_path)
            if not storage_path.exists():
                try:
                    storage_path.mkdir(parents=True, exist_ok=True)
                    result["info"].append(f"Created audio storage directory: {storage_path}")
                except Exception as e:
                    result["errors"].append(f"Cannot create audio storage directory: {e}")
                    result["valid"] = False
            
            result["info"].append(f"Sample rate: {audio_config.sample_rate} Hz")
            result["info"].append(f"Supported formats: {', '.join(audio_config.supported_formats)}")
            
        except Exception as e:
            result["errors"].append(f"Audio config validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def _validate_redis_config(self) -> Dict[str, Any]:
        """Validate Redis configuration."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            settings = self.config_manager.get_settings()
            redis_config = settings.redis
            
            # Check port range
            if not (1 <= redis_config.port <= 65535):
                result["errors"].append(f"Invalid Redis port: {redis_config.port}")
                result["valid"] = False
            
            # Check TTL values
            if redis_config.default_ttl < 1:
                result["warnings"].append(f"Very low default TTL: {redis_config.default_ttl}")
            
            result["info"].append(f"Redis host: {redis_config.host}:{redis_config.port}")
            result["info"].append(f"Default TTL: {redis_config.default_ttl}s")
            
        except Exception as e:
            result["errors"].append(f"Redis config validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def _validate_api_config(self) -> Dict[str, Any]:
        """Validate API configuration."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            settings = self.config_manager.get_settings()
            api_config = settings.api
            
            # Check CORS origins
            if not api_config.cors_origins:
                result["warnings"].append("No CORS origins configured")
            
            # Check JWT settings
            if not api_config.jwt_secret_key:
                result["errors"].append("JWT secret key is required")
                result["valid"] = False
            
            if len(api_config.jwt_secret_key) < 32:
                result["warnings"].append("JWT secret key is shorter than recommended (32+ characters)")
            
            # Check rate limiting
            if api_config.enable_rate_limiting:
                if api_config.rate_limit_requests < 1:
                    result["errors"].append("Rate limit requests must be positive")
                    result["valid"] = False
            
            result["info"].append(f"Rate limiting: {'enabled' if api_config.enable_rate_limiting else 'disabled'}")
            result["info"].append(f"CORS origins: {len(api_config.cors_origins)} configured")
            
        except Exception as e:
            result["errors"].append(f"API config validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def _validate_logging_config(self) -> Dict[str, Any]:
        """Validate logging configuration."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            settings = self.config_manager.get_settings()
            logging_config = settings.logging
            
            # Check log level
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if logging_config.level.upper() not in valid_levels:
                result["errors"].append(f"Invalid log level: {logging_config.level}")
                result["valid"] = False
            
            # Check log file path
            log_path = Path(logging_config.file_path)
            if not log_path.parent.exists():
                try:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    result["info"].append(f"Created log directory: {log_path.parent}")
                except Exception as e:
                    result["errors"].append(f"Cannot create log directory: {e}")
                    result["valid"] = False
            
            result["info"].append(f"Log level: {logging_config.level}")
            result["info"].append(f"Log format: {logging_config.format}")
            
        except Exception as e:
            result["errors"].append(f"Logging config validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def _validate_file_paths(self) -> Dict[str, Any]:
        """Validate file paths and directories."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            settings = self.config_manager.get_settings()
            
            # Paths to check
            paths_to_check = [
                ("Audio storage", settings.audio.audio_storage_path),
                ("Temp audio", settings.audio.temp_audio_path),
                ("Model cache", settings.ai_models.model_cache_dir),
                ("Log file", settings.logging.file_path),
            ]
            
            for name, path_str in paths_to_check:
                if path_str:
                    path = Path(path_str)
                    # For files, check parent directory
                    check_path = path.parent if path.suffix else path
                    
                    if not check_path.exists():
                        try:
                            check_path.mkdir(parents=True, exist_ok=True)
                            result["info"].append(f"Created {name.lower()} directory: {check_path}")
                        except Exception as e:
                            result["warnings"].append(f"Cannot create {name.lower()} directory: {e}")
                    else:
                        result["info"].append(f"{name} path exists: {check_path}")
        
        except Exception as e:
            result["errors"].append(f"File paths validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def _validate_system_prompts(self) -> Dict[str, Any]:
        """Validate system prompts configuration."""
        result = {"valid": True, "errors": [], "warnings": [], "info": []}
        
        try:
            prompts = self.config_manager.get_all_system_prompts()
            
            if not prompts:
                result["warnings"].append("No system prompts loaded")
                return result
            
            # Check for required prompts
            required_prompts = [
                "helpdesk_assistant",
                "helpdesk_greeting",
                "problem_classification",
                "error_handling"
            ]
            
            missing_prompts = []
            for required in required_prompts:
                if required not in prompts:
                    missing_prompts.append(required)
            
            if missing_prompts:
                result["warnings"].append(f"Missing recommended prompts: {', '.join(missing_prompts)}")
            
            # Check prompt content
            empty_prompts = []
            for name, prompt in prompts.items():
                if isinstance(prompt, dict):
                    prompt_text = prompt.get("prompt", "")
                else:
                    prompt_text = prompt
                
                if not prompt_text or len(prompt_text.strip()) < 10:
                    empty_prompts.append(name)
            
            if empty_prompts:
                result["warnings"].append(f"Very short or empty prompts: {', '.join(empty_prompts)}")
            
            result["info"].append(f"Total prompts loaded: {len(prompts)}")
            result["info"].append(f"Required prompts present: {len(required_prompts) - len(missing_prompts)}/{len(required_prompts)}")
        
        except Exception as e:
            result["errors"].append(f"System prompts validation failed: {e}")
            result["valid"] = False
        
        return result
    
    def print_validation_results(self, results: Dict[str, Any]) -> None:
        """Print validation results in a formatted way."""
        print("=" * 60)
        print("CONFIGURATION VALIDATION RESULTS")
        print("=" * 60)
        
        overall_status = "✅ PASSED" if results["valid"] else "❌ FAILED"
        print(f"Overall Status: {overall_status}")
        print()
        
        # Print section results
        for section_name, section_result in results["sections"].items():
            section_status = "✅" if section_result.get("valid", True) else "❌"
            print(f"{section_status} {section_name.replace('_', ' ').title()}")
            
            # Print errors
            for error in section_result.get("errors", []):
                print(f"   ❌ ERROR: {error}")
            
            # Print warnings
            for warning in section_result.get("warnings", []):
                print(f"   ⚠️  WARNING: {warning}")
            
            # Print info (only if no errors/warnings)
            if not section_result.get("errors") and not section_result.get("warnings"):
                for info in section_result.get("info", [])[:2]:  # Limit to 2 info items
                    print(f"   ℹ️  {info}")
        
        print()
        
        # Summary
        total_errors = len(results["errors"])
        total_warnings = len(results["warnings"])
        
        if total_errors > 0:
            print(f"❌ {total_errors} error(s) found - configuration issues need to be resolved")
        
        if total_warnings > 0:
            print(f"⚠️  {total_warnings} warning(s) found - consider reviewing these items")
        
        if total_errors == 0 and total_warnings == 0:
            print("✅ Configuration validation completed successfully!")
        
        print("=" * 60)


def validate_configuration() -> Dict[str, Any]:
    """Convenience function to validate configuration."""
    validator = ConfigValidator()
    return validator.validate_all()


def print_config_validation() -> None:
    """Convenience function to validate and print results."""
    validator = ConfigValidator()
    results = validator.validate_all()
    validator.print_validation_results(results)


if __name__ == "__main__":
    print_config_validation()