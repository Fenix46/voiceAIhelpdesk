"""Configuration usage examples for VoiceHelpDeskAI."""

from voicehelpdeskai.config import get_settings, ConfigManager
from voicehelpdeskai.config.manager import (
    get_config_manager,
    get_whisper_config,
    get_llm_config,
    get_tts_config,
    get_system_prompt,
    get_config_value
)
from voicehelpdeskai.config.validator import validate_configuration


def basic_usage_examples():
    """Basic configuration usage examples."""
    
    print("=== Basic Configuration Usage ===\n")
    
    # Get main settings
    settings = get_settings()
    print(f"App name: {settings.app_name}")
    print(f"Environment: {settings.environment}")
    print(f"Debug mode: {settings.debug}")
    print()
    
    # Access nested configuration
    print(f"Database URL: {settings.database_url}")
    print(f"Redis URL: {settings.redis_url}")
    print(f"Audio sample rate: {settings.audio.sample_rate}")
    print()
    
    # Feature flags
    print(f"Voice chat enabled: {settings.get_feature('voice_chat')}")
    print(f"Analytics enabled: {settings.get_feature('analytics')}")
    print()


def model_config_examples():
    """Model configuration usage examples."""
    
    print("=== Model Configuration Examples ===\n")
    
    # Get specific model configurations
    whisper_config = get_whisper_config()
    llm_config = get_llm_config()
    tts_config = get_tts_config()
    
    print("Whisper Configuration:")
    print(f"  Model: {whisper_config.get('model_name', 'N/A')}")
    print(f"  Language: {whisper_config.get('language', 'N/A')}")
    print(f"  Beam size: {whisper_config.get('beam_size', 'N/A')}")
    print()
    
    print("LLM Configuration:")
    print(f"  Model: {llm_config.get('model_name', 'N/A')}")
    print(f"  Type: {llm_config.get('model_type', 'N/A')}")
    print(f"  Temperature: {llm_config.get('temperature', 'N/A')}")
    print(f"  Max tokens: {llm_config.get('max_tokens', 'N/A')}")
    print()
    
    print("TTS Configuration:")
    print(f"  Engine: {tts_config.get('engine', 'N/A')}")
    print(f"  Voice: {tts_config.get('voice_model', 'N/A')}")
    print(f"  Speed: {tts_config.get('speed', 'N/A')}")
    print()


def system_prompts_examples():
    """System prompts usage examples."""
    
    print("=== System Prompts Examples ===\n")
    
    # Get specific prompts
    greeting_prompt = get_system_prompt("helpdesk_greeting")
    assistant_prompt = get_system_prompt("helpdesk_assistant")
    
    if greeting_prompt:
        if isinstance(greeting_prompt, dict):
            prompt_text = greeting_prompt.get("prompt", "")[:100]
        else:
            prompt_text = greeting_prompt[:100]
        print(f"Greeting prompt (first 100 chars): {prompt_text}...")
    
    if assistant_prompt:
        if isinstance(assistant_prompt, dict):
            prompt_text = assistant_prompt.get("prompt", "")[:100]
        else:
            prompt_text = assistant_prompt[:100]
        print(f"Assistant prompt (first 100 chars): {prompt_text}...")
    
    print()
    
    # List all available prompts
    config_manager = get_config_manager()
    all_prompts = config_manager.get_all_system_prompts()
    print(f"Available prompts ({len(all_prompts)}):")
    for name in sorted(all_prompts.keys()):
        print(f"  - {name}")
    print()


def runtime_overrides_examples():
    """Runtime configuration overrides examples."""
    
    print("=== Runtime Overrides Examples ===\n")
    
    config_manager = get_config_manager()
    
    # Set runtime overrides
    config_manager.set_runtime_override("whisper.model_name", "large")
    config_manager.set_runtime_override("llm.temperature", 0.3)
    
    # Get values with overrides applied
    whisper_model = get_config_value("whisper.model_name")
    llm_temp = get_config_value("llm.temperature")
    
    print(f"Whisper model (with override): {whisper_model}")
    print(f"LLM temperature (with override): {llm_temp}")
    print()
    
    # Get original values (without overrides)
    whisper_config = get_whisper_config()
    original_model = whisper_config.get("model_name")
    print(f"Original whisper model: {original_model}")
    print()
    
    # Clear overrides
    config_manager.clear_runtime_override("whisper.model_name")
    config_manager.clear_runtime_override("llm.temperature")
    
    print("Runtime overrides cleared")
    print()


def config_manager_examples():
    """ConfigManager advanced usage examples."""
    
    print("=== ConfigManager Advanced Usage ===\n")
    
    config_manager = get_config_manager()
    
    # Export configuration summary
    summary = config_manager.export_config_summary()
    print("Configuration Summary:")
    print(f"  App: {summary['settings']['app_name']}")
    print(f"  Environment: {summary['settings']['environment']}")
    print(f"  Features: {len(summary['settings']['features'])} configured")
    print(f"  System prompts: {summary['system_prompts_count']} loaded")
    print(f"  Hot reload: {'enabled' if summary['hot_reload_enabled'] else 'disabled'}")
    print()
    
    # Validate configuration
    validation_results = config_manager.validate_configuration()
    status = "✅ Valid" if validation_results["valid"] else "❌ Invalid"
    print(f"Configuration validation: {status}")
    if validation_results["errors"]:
        print(f"  Errors: {len(validation_results['errors'])}")
    if validation_results["warnings"]:
        print(f"  Warnings: {len(validation_results['warnings'])}")
    print()


def dot_notation_examples():
    """Dot notation configuration access examples."""
    
    print("=== Dot Notation Access Examples ===\n")
    
    # Access nested configuration using dot notation
    examples = [
        ("whisper.model_name", "Whisper model"),
        ("llm.temperature", "LLM temperature"),
        ("tts.engine", "TTS engine"),
        ("performance.batch_size", "Batch size"),
        ("validation.max_audio_duration", "Max audio duration"),
    ]
    
    for key_path, description in examples:
        value = get_config_value(key_path, "Not configured")
        print(f"{description}: {value}")
    
    print()
    
    # Access with defaults
    custom_value = get_config_value("custom.non_existent.key", "default_value")
    print(f"Non-existent key with default: {custom_value}")
    print()


def validation_examples():
    """Configuration validation examples."""
    
    print("=== Configuration Validation Examples ===\n")
    
    # Run full validation
    results = validate_configuration()
    
    print(f"Validation status: {'✅ PASSED' if results['valid'] else '❌ FAILED'}")
    print(f"Total errors: {len(results['errors'])}")
    print(f"Total warnings: {len(results['warnings'])}")
    print()
    
    if results['errors']:
        print("Errors found:")
        for error in results['errors'][:3]:  # Show first 3 errors
            print(f"  - {error}")
        if len(results['errors']) > 3:
            print(f"  ... and {len(results['errors']) - 3} more")
        print()
    
    if results['warnings']:
        print("Warnings found:")
        for warning in results['warnings'][:3]:  # Show first 3 warnings
            print(f"  - {warning}")
        if len(results['warnings']) > 3:
            print(f"  ... and {len(results['warnings']) - 3} more")
        print()
    
    # Show section-specific results
    print("Section results:")
    for section, section_result in results['sections'].items():
        status = "✅" if section_result.get('valid', True) else "❌"
        print(f"  {status} {section.replace('_', ' ').title()}")
    print()


def main():
    """Run all configuration examples."""
    print("VoiceHelpDeskAI Configuration System Examples")
    print("=" * 50)
    print()
    
    try:
        basic_usage_examples()
        model_config_examples()
        system_prompts_examples()
        runtime_overrides_examples()
        config_manager_examples()
        dot_notation_examples()
        validation_examples()
        
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()