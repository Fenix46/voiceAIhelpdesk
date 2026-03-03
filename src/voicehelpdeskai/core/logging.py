"""Logging configuration using Loguru."""

import sys
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from voicehelpdeskai.core.config import settings


def configure_logging() -> None:
    """Configure structured logging with Loguru."""
    # Remove default handler
    logger.remove()
    
    # Create logs directory if it doesn't exist
    log_path = Path(settings.log_file).parent
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Configure console logging
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    if settings.log_format == "json":
        # JSON format for production
        def json_formatter(record: Dict[str, Any]) -> str:
            import json
            return json.dumps({
                "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S"),
                "level": record["level"].name,
                "module": record["name"],
                "function": record["function"],
                "line": record["line"],
                "message": record["message"],
                "extra": record.get("extra", {}),
            })
        
        logger.add(
            sys.stdout,
            format=json_formatter,
            level=settings.log_level,
            serialize=True,
        )
        
        logger.add(
            settings.log_file,
            format=json_formatter,
            level=settings.log_level,
            rotation=settings.log_max_size,
            retention=settings.log_backup_count,
            serialize=True,
        )
    else:
        # Human-readable format for development
        logger.add(
            sys.stdout,
            format=console_format,
            level=settings.log_level,
            colorize=True,
        )
        
        logger.add(
            settings.log_file,
            format=console_format,
            level=settings.log_level,
            rotation=settings.log_max_size,
            retention=settings.log_backup_count,
            colorize=False,
        )
    
    # Configure third-party loggers
    configure_third_party_loggers()
    
    logger.info(
        "Logging configured",
        level=settings.log_level,
        format=settings.log_format,
        file=settings.log_file,
    )


def configure_third_party_loggers() -> None:
    """Configure third-party library loggers."""
    import logging
    
    # Intercept standard library logging
    class InterceptHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            # Get corresponding Loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno
            
            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            
            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )
    
    # Set up interception for standard library logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    
    # Configure specific loggers
    loggers_to_configure = [
        "uvicorn",
        "uvicorn.access",
        "fastapi",
        "sqlalchemy.engine",
        "celery",
        "redis",
        "httpx",
    ]
    
    for logger_name in loggers_to_configure:
        logging.getLogger(logger_name).handlers = [InterceptHandler()]
        if logger_name == "uvicorn.access":
            # Reduce verbosity of access logs
            logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str) -> Any:
    """Get a logger instance for the given name."""
    return logger.bind(name=name)