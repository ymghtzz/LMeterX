"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Core data structures and configuration management for the stress testing engine.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Union

from utils.config import DEFAULT_API_PATH, DEFAULT_CONTENT_TYPE
from utils.tools import FilePathUtils


# === DATA CLASSES ===
@dataclass
class StreamMetrics:
    """Metrics for streaming responses."""

    first_token_received: bool = False
    first_thinking_received: bool = False
    reasoning_is_active: bool = False
    reasoning_ended: bool = False
    first_output_token_time: float = 0.0
    first_thinking_token_time: float = 0.0
    model_output: str = ""
    reasoning_content: str = ""


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
    stream_mode: bool = True
    chat_type: int = 0
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    cert_config: Optional[Union[str, Tuple[str, str]]] = None
    field_mapping: Optional[str] = None
    test_data: Optional[str] = None


@dataclass
class FieldMapping:
    """Field mapping configuration for custom APIs."""

    stream_prefix: str = "data:"
    data_format: str = "json"
    stop_flag: str = "[DONE]"
    end_prefix: str = ""
    end_condition: str = ""
    content: str = ""
    reasoning_content: str = ""
    prompt: str = ""


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
                end_condition=mapping_dict.get("end_condition", ""),
                content=mapping_dict.get("content", ""),
                reasoning_content=mapping_dict.get("reasoning_content", ""),
                prompt=mapping_dict.get("prompt", ""),
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
        """Configure client certificate and key."""
        return FilePathUtils.configure_certificates(cert_file, key_file, task_logger)


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
