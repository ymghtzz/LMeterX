"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Core data structures and configuration management for the stress testing engine.
"""

import json
import multiprocessing as mp
import ssl
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

from gevent import queue
from gevent.lock import Semaphore

from config.base import DEFAULT_API_PATH, DEFAULT_CONTENT_TYPE
from config.multiprocess import should_use_multiprocessing_manager
from utils.logger import logger


# === UTILITY CLASSES ===
class SimpleLock:
    """Simple lock implementation as fallback when multiprocessing fails."""

    def __enter__(self):
        pass

    def __exit__(self, *args):
        pass


# === DATA CLASSES ===
@dataclass
class StreamMetrics:
    """Metrics for streaming responses."""

    first_token_received: bool = False
    first_thinking_received: bool = False
    reasoning_is_active: bool = False
    reasoning_ended: bool = False
    first_output_token_time: Optional[float] = None
    first_thinking_token_time: Optional[float] = None
    content: str = ""
    reasoning_content: str = ""
    # Usage information from streaming response
    usage: Optional[Dict[str, Optional[int]]] = field(default=None)


@dataclass
class GlobalConfig:
    """Global configuration for all users."""

    task_id: str = ""
    api_path: str = DEFAULT_API_PATH
    headers: Dict[str, str] = field(
        default_factory=lambda: {"Content-Type": DEFAULT_CONTENT_TYPE}
    )
    cookies: Optional[Dict[str, str]] = None
    request_payload: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    stream_mode: bool = True
    chat_type: int = 0
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    cert_config: Optional[Union[str, Tuple[str, str]]] = None
    field_mapping: Optional[str] = None
    test_data: Optional[str] = None
    duration: int = 60


@dataclass
class FieldMapping:
    """Field mapping configuration for custom APIs."""

    stream_prefix: str = "data:"
    data_format: str = "json"
    stop_flag: str = "[DONE]"
    end_prefix: str = ""
    end_field: str = ""
    content: str = ""
    reasoning_content: str = ""
    prompt: str = ""
    usage: str = ""


# === GLOBAL STATE MANAGEMENT ===
class GlobalStateManager:
    """Manages global state for Locust testing."""

    _global_config: Optional[GlobalConfig] = None
    _global_task_queue: Optional[Dict[str, Any]] = None
    _start_time: Optional[float] = None
    _lock: Optional[Any] = None
    _logger_cache: Dict[str, Any] = {}
    _ssl_context: Optional[ssl.SSLContext] = None

    @classmethod
    def initialize_global_state(cls) -> None:
        """Initialize global state with error handling."""
        try:
            # Check if we should use multiprocessing manager
            use_multiprocessing = should_use_multiprocessing_manager()

            # single process mode
            if not use_multiprocessing:
                if cls._lock is None:
                    try:
                        cls._lock = Semaphore(1)
                    except Exception as e:
                        logger.warning(f"Failed to create gevent semaphore: {e}")
                        cls._lock = SimpleLock()

                # create in-process queues
                cls._global_task_queue = {
                    "completion_tokens_queue": queue.Queue(),
                    "all_tokens_queue": queue.Queue(),
                }

                cls._global_config = GlobalConfig()
                cls._start_time = None
                cls._logger_cache = {}
                cls._ssl_context = None
                return

            # multiprocessing mode - use per-process queues
            # Locust's Worker processes cannot access the Master process's shared queue
            if use_multiprocessing:
                logger.info("Multi-process mode detected - using per-process queues")
                # In multi-process mode, each process uses its own queue, sharing data via messages

            # Create lock - use gevent lock in multi-process mode
            if cls._lock is None:
                try:
                    cls._lock = Semaphore(1)
                except Exception as e:
                    logger.warning(f"Failed to create gevent semaphore: {e}")
                    # final fallback: use simple object as lock
                    cls._lock = SimpleLock()

            assert cls._lock is not None
            with cls._lock:
                cls._global_config = GlobalConfig()

                # Always use single process queue - share data via messages in multi-process mode
                cls._global_task_queue = {
                    "completion_tokens_queue": queue.Queue(),
                    "all_tokens_queue": queue.Queue(),
                }

                cls._start_time = None
                cls._logger_cache = {}
                cls._ssl_context = None

        except Exception as e:
            logger.error(f"Failed to initialize global state: {e}")
            # Set fallback values to prevent further errors
            if cls._global_config is None:
                cls._global_config = GlobalConfig()
            if cls._global_task_queue is None:
                cls._global_task_queue = {
                    "completion_tokens_queue": queue.Queue(),
                    "all_tokens_queue": queue.Queue(),
                }
            if cls._lock is None:
                # final fallback: use simple object as lock
                cls._lock = SimpleLock()

    @classmethod
    def get_global_config(cls) -> GlobalConfig:
        """Thread-safe access to global configuration."""
        if cls._global_config is None:
            cls.initialize_global_state()
        return cls._global_config  # type: ignore

    @classmethod
    def get_global_task_queue(cls) -> Dict[str, queue.Queue]:
        """Thread-safe access to global task queue."""
        if cls._global_task_queue is None:
            cls.initialize_global_state()
        return cls._global_task_queue  # type: ignore

    @classmethod
    def set_start_time(cls, start_time: float) -> None:
        """Set the test start time."""
        if cls._lock is None:
            cls.initialize_global_state()
        assert cls._lock is not None
        with cls._lock:  # type: ignore
            cls._start_time = start_time

    @classmethod
    def get_start_time(cls) -> Optional[float]:
        """Get the test start time."""
        return cls._start_time

    # --- Logger cache ---
    @classmethod
    def get_task_logger(cls, task_id: str):
        """Get a cached bound logger for the given task id (reduces bind overhead)."""
        if not task_id:
            return logger
        if cls._lock is None:
            cls.initialize_global_state()
        assert cls._lock is not None
        with cls._lock:  # type: ignore
            if task_id not in cls._logger_cache:
                cls._logger_cache[task_id] = logger.bind(task_id=task_id)
            return cls._logger_cache[task_id]

    # --- SSL Context cache ---
    @classmethod
    def build_ssl_context_if_needed(
        cls, cert_config: Optional[Union[str, Tuple[str, str]]]
    ) -> None:
        """Build and cache SSL context once per process."""
        if cls._ssl_context is not None:
            return
        if cls._lock is None:
            cls.initialize_global_state()
        assert cls._lock is not None
        with cls._lock:  # type: ignore
            if cls._ssl_context is not None:
                return
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                if cert_config:
                    if isinstance(cert_config, tuple):
                        cert_file, key_file = cert_config
                        ssl_context.load_cert_chain(cert_file, key_file)
                    elif isinstance(cert_config, str):
                        ssl_context.load_cert_chain(cert_config)
                cls._ssl_context = ssl_context
            except Exception as e:
                # Do not raise; leave as None to fallback gracefully
                logger.warning(f"Failed to build SSL context: {e}")
                cls._ssl_context = None

    @classmethod
    def get_ssl_context(cls) -> Optional[ssl.SSLContext]:
        """Get the SSL context for secure connections."""
        return cls._ssl_context


# === CONFIGURATION MANAGEMENT ===
class ConfigManager:
    """Manages configuration parsing and validation."""

    @staticmethod
    def parse_headers(
        headers_input: Union[str, Dict[str, str]], task_logger
    ) -> Dict[str, str]:
        """Parse headers from string or dict input."""
        default_headers = {"Content-Type": DEFAULT_CONTENT_TYPE}

        if isinstance(headers_input, dict):
            return headers_input

        if isinstance(headers_input, str) and headers_input.strip():
            try:
                parsed_headers = json.loads(headers_input)
                if not isinstance(parsed_headers, dict):
                    raise ValueError("Headers must be a JSON object")
                return parsed_headers
            except (json.JSONDecodeError, ValueError) as e:
                task_logger.error(
                    f"Failed to parse headers JSON '{headers_input}': {e}"
                )
                return default_headers

        return default_headers

    @staticmethod
    def parse_cookies(
        cookies_input: Union[str, Dict[str, str]], task_logger
    ) -> Optional[Dict[str, str]]:
        """Parse cookies from string or dict input."""
        if isinstance(cookies_input, dict):
            return cookies_input

        if isinstance(cookies_input, str) and cookies_input.strip():
            try:
                parsed_cookies = json.loads(cookies_input)
                if not isinstance(parsed_cookies, dict):
                    raise ValueError("Cookies must be a JSON object")
                return parsed_cookies
            except (json.JSONDecodeError, ValueError) as e:
                task_logger.error(
                    f"Failed to parse cookies JSON '{cookies_input}': {e}"
                )
                return None

        return None

    @staticmethod
    def parse_field_mapping(field_mapping_str: str) -> FieldMapping:
        """Parse field mapping configuration."""
        if not field_mapping_str:
            return FieldMapping()

        try:
            mapping_dict = json.loads(str(field_mapping_str))
            return FieldMapping(
                stream_prefix=mapping_dict.get("stream_prefix", "data:"),
                data_format=mapping_dict.get("data_format", "json"),
                stop_flag=mapping_dict.get("stop_flag", "[DONE]"),
                end_prefix=mapping_dict.get("end_prefix", ""),
                end_field=mapping_dict.get("end_field", ""),
                content=mapping_dict.get("content", ""),
                reasoning_content=mapping_dict.get("reasoning_content", ""),
                prompt=mapping_dict.get("prompt", ""),
                usage=mapping_dict.get("usage", ""),
            )
        except (json.JSONDecodeError, TypeError):
            return FieldMapping()


# === CERTIFICATE MANAGEMENT ===
class CertificateManager:
    """Manages SSL certificate configuration."""

    @staticmethod
    def configure_certificates(
        cert_file: Optional[str], key_file: Optional[str], task_logger
    ) -> Optional[Union[str, Tuple[str, str]]]:
        """Configure client certificate and key for SSL connections.

        Args:
            cert_file (Optional[str]): Path to certificate file
            key_file (Optional[str]): Path to key file
            task_logger: Logger instance for task-specific logging

        Returns:
            Optional[Union[str, Tuple[str, str]]]:
                - None if no certificates provided
                - str if only cert_file provided (for combined cert+key files)
                - Tuple[str, str] if both cert and key files provided

        Raises:
            ValueError: If certificate configuration is invalid
        """
        if not cert_file and not key_file:
            return None

        if cert_file and not key_file:
            # Single file contains both certificate and key
            return cert_file

        if cert_file and key_file:
            # Separate certificate and key files
            return (cert_file, key_file)

        if not cert_file and key_file:
            # Key file without certificate file is invalid, but don't fail
            return None

        return None


# === VALIDATION ===
class ValidationManager:
    """Handles configuration validation."""

    @staticmethod
    def validate_config(config: GlobalConfig, task_logger) -> bool:
        """Validate global configuration before starting tests."""
        if not config.task_id:
            task_logger.error("Task ID is required but not provided")
            return False

        if not config.model_name:
            task_logger.error("Model name is required")
            return False

        if not config.request_payload:
            task_logger.error("Request payload is required for all API endpoints")
            return False

        return True
