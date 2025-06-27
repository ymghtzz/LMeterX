"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

import urllib3
from gevent import queue
from locust import HttpUser, between, events, task
from urllib3.exceptions import InsecureRequestWarning

from utils.logger import logger
from utils.tools import count_tokens

# Disable the specific InsecureRequestWarning from urllib3
urllib3.disable_warnings(InsecureRequestWarning)

# --- Constants ---
HTTP_OK = 200
DEFAULT_TIMEOUT = 90
DEFAULT_WAIT_TIME_MIN = 1
DEFAULT_WAIT_TIME_MAX = 3
DEFAULT_PROMPT = "Tell me about the history of Artificial Intelligence."

# Streaming constants
STREAM_END_MARKERS = ["[DONE]", "[END]", "DONE", "END"]
STREAM_ERROR_MARKERS = ["[ERROR]", "ERROR"]
MAX_CHUNK_SIZE = 1000  # Maximum chunk size to process
MAX_OUTPUT_LENGTH = 100000  # Maximum output length to prevent memory issues

# Timing metrics names
METRIC_TTFOT = "Time_to_first_output_token"
METRIC_TTFRT = "Time_to_first_reasoning_token"
METRIC_TTRC = "Time_to_reasoning_completion"
METRIC_TTOC = "Time_to_output_completion"
METRIC_TTT = "Total_turnaround_time"

# --- Data Classes ---


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
    api_path: str = "/v1/chat/completions"
    headers: Dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "application/json"}
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


# --- Global State ---
GLOBAL_CONFIG = GlobalConfig()
GLOBAL_TASK_QUEUE: Dict[str, queue.Queue] = {
    "completion_tokens_queue": queue.Queue(),
    "all_tokens_queue": queue.Queue(),
}
_start_time: Optional[float] = None

# --- Utility Classes ---


class ConfigManager:
    """Manages configuration parsing and validation."""

    @staticmethod
    def parse_headers(
        headers_input: Union[str, Dict[str, str]], task_logger
    ) -> Dict[str, str]:
        """Parse headers from string or dict input."""
        default_headers = {"Content-Type": "application/json"}

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


class CertificateManager:
    """Manages SSL certificate configuration."""

    @staticmethod
    def configure_certificates(
        cert_file: Optional[str], key_file: Optional[str], task_logger
    ) -> Optional[Union[str, Tuple[str, str]]]:
        """Configure client certificate and key."""

        def is_file_accessible(file_path: Optional[str]) -> bool:
            if not file_path or not isinstance(file_path, str) or not file_path.strip():
                return False
            try:
                return os.path.exists(file_path) and os.access(file_path, os.R_OK)
            except OSError:
                return False

        cert_valid = is_file_accessible(cert_file)
        key_valid = is_file_accessible(key_file)

        if cert_valid and key_valid and cert_file and key_file:
            return (cert_file, key_file)
        elif cert_valid and cert_file:
            return cert_file
        elif cert_file and cert_file.strip():
            task_logger.warning(f"Certificate file not accessible: {cert_file}")
        elif key_file and key_file.strip():
            task_logger.warning(f"Key file not accessible: {key_file}")

        return None


class ErrorHandler:
    """Centralized error handling for various scenarios."""

    @staticmethod
    def check_json_error(json_data: Dict[str, Any]) -> Optional[str]:
        """Check if JSON data contains error conditions."""
        if not isinstance(json_data, dict):
            return None

        try:
            # Check for various error indicators
            code = json_data.get("code", 0)
            error = json_data.get("error", "")
            output_object = json_data.get("object", "")

            # API-specific error checks
            error_details = json_data.get("error", {})
            if isinstance(error_details, dict):
                error_type = error_details.get("type", "")
                error_message = error_details.get("message", "")
                if error_type or error_message:
                    return f"API error - type: {error_type}, message: {error_message}"

            if code < 0:
                return f"Response contains error code: {code}"

            if error and str(error).strip():
                return f"Response contains error: {error}"

            if output_object == "error":
                return f"Response object type is error"

            # Check for HTTP error status in response
            if "status" in json_data and json_data["status"] != 200:
                return f"HTTP error status: {json_data['status']}"

            return None
        except Exception as e:
            # Log parsing errors but don't treat them as API errors
            return None

    @staticmethod
    def handle_general_exception(
        error_msg: str, task_logger, response=None, response_time: float = 0
    ) -> None:
        """Centralized handler for logging exceptions during requests."""
        task_logger.error(error_msg)
        if response:
            response.failure(error_msg)
        EventManager.fire_failure_event(
            response_time=response_time, exception=Exception(error_msg)
        )

    @staticmethod
    def validate_config(config: GlobalConfig, task_logger) -> bool:
        """Validate global configuration before starting tests."""
        if not config.task_id:
            task_logger.error("Task ID is required but not provided")
            return False

        if not config.model_name and config.api_path == "/v1/chat/completions":
            task_logger.error("Model name is required for chat completions API")
            return False

        if not config.request_payload and config.api_path != "/v1/chat/completions":
            task_logger.error("Request payload is required for custom API endpoints")
            return False

        return True


class EventManager:
    """Manages Locust events and metrics."""

    @staticmethod
    def fire_failure_event(
        name: str = "http_request",
        response_time: float = 0,
        response_length: int = 0,
        exception: Optional[Exception] = None,
    ) -> None:
        """Fire failure events with proper Locust event format."""
        events.request.fire(
            request_type="POST",
            name=name,
            response_time=response_time,
            response_length=response_length,
            exception=exception or Exception("Request failed"),
        )

    @staticmethod
    def fire_metric_event(
        name: str, response_time: float, response_length: int
    ) -> None:
        """Fire metric events."""
        events.request.fire(
            request_type="metric",
            name=name,
            response_time=response_time,
            response_length=response_length,
        )


class StreamProcessor:
    """Handles streaming response processing."""

    @staticmethod
    def get_field_value(data: Dict[str, Any], path: str) -> str:
        """Get value from nested dictionary using dot-separated path."""
        if not path or not isinstance(data, dict):
            return ""

        try:
            keys = path.split(".")
            current = data

            for key in keys:
                if key.isdigit():
                    if isinstance(current, list):
                        current = current[int(key)]
                    else:
                        return ""
                elif isinstance(current, list) and current:
                    if isinstance(current[0], dict):
                        current = current[0].get(key, {})
                    else:
                        return ""
                elif isinstance(current, dict):
                    current = current.get(key, {})
                else:
                    return ""

            return str(current) if current else ""
        except (KeyError, IndexError, TypeError, ValueError):
            return ""

    @staticmethod
    def check_stream_end_condition(
        chunk_str: str, chunk_data: Dict[str, Any], field_mapping: FieldMapping
    ) -> bool:
        """Check if the stream has ended based on various conditions."""
        try:
            # Check direct stop flag match
            if field_mapping.stop_flag:
                if field_mapping.end_prefix:
                    end_stream = chunk_str.replace(field_mapping.end_prefix, "").strip()
                else:
                    end_stream = chunk_str.strip()

                if end_stream == field_mapping.stop_flag:
                    return True

            # Check JSON end field condition
            if field_mapping.end_condition and chunk_data:
                end_value = StreamProcessor.get_field_value(
                    chunk_data, field_mapping.end_condition
                )
                if end_value in [
                    "stop",
                    "complete",
                    "done",
                    "finished",
                    "length",
                    "content_filter",
                ]:
                    return True
                if isinstance(end_value, bool) and end_value:
                    return True

            return False
        except Exception:
            return False

    @staticmethod
    def process_chunk(
        chunk: bytes,
        field_mapping: FieldMapping,
        start_time: float,
        metrics: StreamMetrics,
        task_logger,
    ) -> StreamMetrics:
        """Process a single stream chunk and update metrics."""
        if not chunk:
            return metrics

        try:
            chunk_str = chunk.decode("utf-8", errors="replace").strip()
        except UnicodeDecodeError as e:
            task_logger.warning(f"Failed to decode chunk: {e}")
            return metrics

        # Check direct stop flag match
        if field_mapping.stop_flag and (
            chunk_str == f"{field_mapping.end_prefix} {field_mapping.stop_flag}"
            or chunk_str == field_mapping.stop_flag
        ):
            return metrics

        # Remove stream prefix if present
        if field_mapping.stream_prefix and chunk_str.startswith(
            field_mapping.stream_prefix
        ):
            chunk_str = chunk_str[len(field_mapping.stream_prefix) :].strip()

        if not chunk_str:
            return metrics

        content_chunk = ""
        reasoning_chunk = ""
        chunk_data = {}

        try:
            if field_mapping.data_format == "json":
                chunk_data = json.loads(chunk_str)

                if StreamProcessor.check_stream_end_condition(
                    chunk_str, chunk_data, field_mapping
                ):
                    return metrics

                content_chunk = (
                    StreamProcessor.get_field_value(chunk_data, field_mapping.content)
                    if field_mapping.content
                    else ""
                )
                reasoning_chunk = (
                    StreamProcessor.get_field_value(
                        chunk_data, field_mapping.reasoning_content
                    )
                    if field_mapping.reasoning_content
                    else ""
                )
            else:
                if StreamProcessor.check_stream_end_condition(
                    chunk_str, {}, field_mapping
                ):
                    return metrics
                content_chunk = chunk_str

        except (json.JSONDecodeError, IndexError, KeyError) as e:
            if field_mapping.data_format == "json":
                # For malformed JSON chunks, treat as text content if not too large
                if len(chunk_str) < 1000:  # Reasonable size threshold
                    content_chunk = chunk_str
            else:
                content_chunk = chunk_str

        # Process content tokens with safety checks
        if content_chunk and len(content_chunk.strip()) > 0:
            # Prevent memory issues by limiting output length
            if len(metrics.model_output) + len(content_chunk) > MAX_OUTPUT_LENGTH:
                task_logger.warning(
                    f"Output length exceeded {MAX_OUTPUT_LENGTH} characters, truncating"
                )
                content_chunk = content_chunk[
                    : MAX_OUTPUT_LENGTH - len(metrics.model_output)
                ]

            metrics.model_output += content_chunk
            if not metrics.first_token_received:
                metrics.first_token_received = True
                metrics.first_output_token_time = time.time()
                ttfot = (metrics.first_output_token_time - start_time) * 1000
                EventManager.fire_metric_event(METRIC_TTFOT, ttfot, len(content_chunk))

        # Process reasoning tokens with safety checks
        if reasoning_chunk and len(reasoning_chunk.strip()) > 0:
            # Prevent memory issues by limiting reasoning content length
            if (
                len(metrics.reasoning_content) + len(reasoning_chunk)
                > MAX_OUTPUT_LENGTH
            ):
                task_logger.warning(
                    f"Reasoning content length exceeded {MAX_OUTPUT_LENGTH} characters, truncating"
                )
                reasoning_chunk = reasoning_chunk[
                    : MAX_OUTPUT_LENGTH - len(metrics.reasoning_content)
                ]

            metrics.reasoning_content += reasoning_chunk
            if not metrics.reasoning_is_active:
                metrics.reasoning_is_active = True
            if not metrics.first_thinking_received:
                metrics.first_thinking_received = True
                metrics.first_thinking_token_time = time.time()
                ttfrt = (metrics.first_thinking_token_time - start_time) * 1000
                EventManager.fire_metric_event(
                    METRIC_TTFRT, ttfrt, len(reasoning_chunk)
                )
        elif (
            metrics.reasoning_is_active
            and not reasoning_chunk
            and not metrics.reasoning_ended
            and content_chunk
        ):
            if metrics.first_thinking_received:
                metrics.reasoning_ended = True
                ttrc = (time.time() - metrics.first_thinking_token_time) * 1000
                EventManager.fire_metric_event(
                    METRIC_TTRC, ttrc, len(metrics.reasoning_content)
                )

        return metrics

    @staticmethod
    def check_chunk_error(
        chunk: bytes, field_mapping: FieldMapping, task_logger
    ) -> Optional[str]:
        """Check streaming chunk for errors."""
        try:
            if not chunk or not isinstance(chunk, bytes):
                return None

            chunk_str = chunk.decode("utf-8", errors="replace").strip()

            # Skip processing if it's a stop flag
            if field_mapping.stop_flag and (
                chunk_str == field_mapping.stop_flag
                or chunk_str.endswith(field_mapping.stop_flag)
            ):
                return None

            # Remove prefix if present
            if field_mapping.stream_prefix and chunk_str.startswith(
                field_mapping.stream_prefix
            ):
                chunk_content = chunk_str[len(field_mapping.stream_prefix) :].strip()
            else:
                chunk_content = chunk_str

            if not chunk_content:
                return None

            # Only check JSON errors if data format is JSON
            if field_mapping.data_format == "json":
                try:
                    chunk_json = json.loads(chunk_content)
                    return ErrorHandler.check_json_error(chunk_json)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return None

            return None

        except Exception as e:
            task_logger.warning(f"Unexpected error checking chunk for errors: {e}")
            return None


# --- Locust Event Hooks ---


@events.init_command_line_parser.add_listener
def init_parser(parser):
    """Add custom command-line arguments to the Locust parser."""
    parser.add_argument(
        "--task-id",
        type=str,
        default="",
        help="The unique identifier for the test task.",
    )
    parser.add_argument(
        "--api_path",
        type=str,
        default="/v1/chat/completions",
        help="API path for the request.",
    )
    parser.add_argument(
        "--headers", type=str, default="", help="Request headers in JSON format."
    )
    parser.add_argument(
        "--cookies", type=str, default="", help="Request cookies in JSON format."
    )
    parser.add_argument(
        "--request_payload", type=str, default="", help="Request payload."
    )
    parser.add_argument(
        "--model_name", type=str, default="", help="Name of the model to test."
    )
    parser.add_argument(
        "--system_prompt", type=str, default="", help="System prompt to use."
    )
    parser.add_argument(
        "--stream_mode",
        type=str,
        default="True",
        help="Whether to use streaming responses.",
    )
    parser.add_argument(
        "--chat_type",
        type=int,
        default=0,
        help="Type of chat (e.g., text:0, multimodal:1).",
    )
    parser.add_argument(
        "--cert_file", type=str, default="", help="Path to the client certificate file."
    )
    parser.add_argument(
        "--key_file", type=str, default="", help="Path to the client private key file."
    )
    parser.add_argument(
        "--field_mapping",
        type=str,
        default="",
        help="Field mapping configuration for custom APIs",
    )
    parser.add_argument(
        "--user_prompt", type=str, default="", help="User prompt for the model"
    )


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize Locust configuration and setup environment."""
    global _start_time, GLOBAL_CONFIG

    if not environment.parsed_options:
        logger.warning(
            "No parsed options found in environment. Skipping configuration."
        )
        return

    options = environment.parsed_options
    task_id = options.task_id or os.environ.get("TASK_ID", "unknown")
    task_logger = logger.bind(task_id=task_id)

    try:
        # Update global config
        GLOBAL_CONFIG.task_id = task_id
        GLOBAL_CONFIG.api_path = options.api_path
        GLOBAL_CONFIG.request_payload = options.request_payload
        GLOBAL_CONFIG.model_name = options.model_name
        GLOBAL_CONFIG.system_prompt = options.system_prompt
        GLOBAL_CONFIG.user_prompt = options.user_prompt
        GLOBAL_CONFIG.stream_mode = str(options.stream_mode).lower() in ("true", "1")
        GLOBAL_CONFIG.chat_type = int(options.chat_type)
        GLOBAL_CONFIG.cert_file = options.cert_file
        GLOBAL_CONFIG.key_file = options.key_file
        GLOBAL_CONFIG.field_mapping = options.field_mapping

        # Parse and validate headers
        GLOBAL_CONFIG.headers = ConfigManager.parse_headers(
            options.headers, task_logger
        )

        # Parse and validate cookies
        GLOBAL_CONFIG.cookies = ConfigManager.parse_cookies(
            options.cookies, task_logger
        )

        # Configure client certificates
        GLOBAL_CONFIG.cert_config = CertificateManager.configure_certificates(
            GLOBAL_CONFIG.cert_file, GLOBAL_CONFIG.key_file, task_logger
        )

        # Validate configuration before proceeding
        if not ErrorHandler.validate_config(GLOBAL_CONFIG, task_logger):
            raise ValueError("Invalid configuration provided")

        # Initialize prompt queue
        if not hasattr(environment, "prompt_queue"):
            try:
                from utils.tools import init_prompt_queue

                environment.prompt_queue = init_prompt_queue(
                    chat_type=options.chat_type, task_logger=task_logger
                )
            except Exception as e:
                task_logger.error(f"Failed to initialize prompt queue: {e}")
                environment.prompt_queue = queue.Queue()

        environment.global_config = GLOBAL_CONFIG

        from utils.tools import mask_sensitive_data

        masked_config = mask_sensitive_data(GLOBAL_CONFIG.__dict__)
        task_logger.info(f"Locust initialization complete. Config: {masked_config}")
        _start_time = time.time()

    except Exception as e:
        task_logger.error(f"Error during Locust initialization: {e}", exc_info=True)
        raise


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Calculate final metrics and save results."""
    task_id = GLOBAL_CONFIG.task_id
    task_logger = logger.bind(task_id=task_id)
    end_time = time.time()

    execution_time = (end_time - _start_time) if _start_time else 0
    if execution_time > 0:
        task_logger.info(f"Test duration: {execution_time:.2f} seconds.")
    else:
        task_logger.warning(
            "Start time was not recorded; cannot calculate execution time."
        )

    task_logger.info("Test stopped. Calculating token throughput metrics...")

    try:
        from utils.tools import calculate_custom_metrics, get_locust_stats

        custom_metrics = calculate_custom_metrics(
            task_id, GLOBAL_TASK_QUEUE, execution_time
        )
        locust_stats = get_locust_stats(task_id, environment.stats)

        locust_result = {
            "custom_metrics": custom_metrics,
            "locust_stats": locust_stats,
        }

        # Save results to temporary file
        result_file = os.path.join(
            tempfile.gettempdir(), "locust_result", task_id, "result.json"
        )
        result_dir = os.path.dirname(result_file)
        os.makedirs(result_dir, exist_ok=True)

        with open(result_file, "w") as f:
            json.dump(locust_result, f, indent=4)

    except Exception as e:
        task_logger.error(f"Failed to save locust results: {e}", exc_info=True)


# --- Main User Class ---


class LLMTestUser(HttpUser):
    """A user class that simulates a client making requests to an LLM service."""

    wait_time = between(DEFAULT_WAIT_TIME_MIN, DEFAULT_WAIT_TIME_MAX)

    @property
    def task_id(self) -> str:
        """Returns the task_id from the global configuration."""
        return GLOBAL_CONFIG.task_id

    def get_next_prompt(self) -> Tuple[str, Any]:
        """Fetch the next prompt from the shared queue."""
        task_logger = logger.bind(task_id=self.task_id)
        try:
            prompt_id, prompt_data = self.environment.prompt_queue.get_nowait()
            self.environment.prompt_queue.put_nowait((prompt_id, prompt_data))
            return prompt_id, prompt_data
        except queue.Empty:
            task_logger.warning("Prompt queue is empty. Using default prompt.")
            return "default", DEFAULT_PROMPT

    def prepare_request_kwargs(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Prepare request payload and arguments based on prompt and global config."""
        task_logger = logger.bind(task_id=self.task_id)

        if GLOBAL_CONFIG.api_path != "/v1/chat/completions":
            return self._prepare_custom_api_request(task_logger)

        return self._prepare_chat_completions_request(task_logger)

    def _prepare_custom_api_request(
        self, task_logger
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Handle custom API requests with user-provided payload."""
        try:
            if not GLOBAL_CONFIG.request_payload:
                task_logger.error("No request payload provided for custom API endpoint")
                return None, None

            # Get the next prompt data (same as chat_completions)
            prompt_id, prompt_data = self.get_next_prompt()
            if not prompt_data:
                prompt_data = GLOBAL_CONFIG.user_prompt or DEFAULT_PROMPT

            try:
                payload = json.loads(str(GLOBAL_CONFIG.request_payload))
            except json.JSONDecodeError as e:
                task_logger.error(f"Invalid JSON in request payload: {e}")
                return None, None

            # Parse field mapping to get prompt field path
            field_mapping = ConfigManager.parse_field_mapping(
                GLOBAL_CONFIG.field_mapping or ""
            )

            # Update payload with current prompt data if field mapping is configured
            if field_mapping.prompt:
                try:
                    # Handle different prompt data types (same as chat_completions)
                    if isinstance(prompt_data, str):
                        user_prompt = prompt_data
                    else:
                        # For multimodal data, extract the text prompt
                        user_prompt = prompt_data.get("prompt", "")

                    # Set the prompt content in the payload using field mapping
                    self._set_field_value(payload, field_mapping.prompt, user_prompt)
                    task_logger.debug(
                        f"Updated payload field '{field_mapping.prompt}' with prompt data"
                    )

                except Exception as e:
                    task_logger.warning(f"Failed to update prompt in payload: {e}")
                    user_prompt = self._extract_prompt_from_payload(payload)
            else:
                task_logger.warning(
                    "No prompt field mapping configured, using original payload"
                )
                user_prompt = self._extract_prompt_from_payload(payload)

            base_request_kwargs = {
                "json": payload,
                "headers": GLOBAL_CONFIG.headers,
                "catch_response": True,
                "name": "custom_api",
                "verify": False,
                "timeout": DEFAULT_TIMEOUT,
            }

            # Add cookies if configured
            if GLOBAL_CONFIG.cookies:
                base_request_kwargs["cookies"] = GLOBAL_CONFIG.cookies

            return base_request_kwargs, user_prompt

        except Exception as e:
            task_logger.error(
                f"Failed to prepare custom API request: {e}", exc_info=True
            )
            return None, None

    def _prepare_chat_completions_request(
        self, task_logger
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Handle traditional chat completions API requests."""
        prompt_id, prompt_data = self.get_next_prompt()
        if not prompt_data:
            prompt_data = GLOBAL_CONFIG.user_prompt or DEFAULT_PROMPT

        try:
            system_message = (
                [{"role": "system", "content": GLOBAL_CONFIG.system_prompt}]
                if GLOBAL_CONFIG.system_prompt
                else []
            )

            if isinstance(prompt_data, str):
                user_prompt = prompt_data
                messages = system_message + [{"role": "user", "content": user_prompt}]
            else:
                user_prompt = prompt_data.get("prompt", "")
                image_base64 = prompt_data.get("image_base64", "")
                content_list = [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ]
                messages = system_message + [{"role": "user", "content": content_list}]  # type: ignore

            payload = {
                "model": GLOBAL_CONFIG.model_name,
                "stream": GLOBAL_CONFIG.stream_mode,
                "messages": messages,
            }

            base_request_kwargs = {
                "json": payload,
                "headers": GLOBAL_CONFIG.headers,
                "catch_response": True,
                "name": "chat_completions",
                "verify": False,
                "timeout": DEFAULT_TIMEOUT,
            }

            # Add cookies if configured
            if GLOBAL_CONFIG.cookies:
                base_request_kwargs["cookies"] = GLOBAL_CONFIG.cookies

            return base_request_kwargs, user_prompt

        except Exception as e:
            task_logger.error(
                f"Failed to prepare chat completions request: {e}", exc_info=True
            )
            return None, None

    def _extract_prompt_from_payload(self, payload: Dict[str, Any]) -> str:
        """Extract prompt content from custom payload using field mapping."""
        try:
            field_mapping = ConfigManager.parse_field_mapping(
                GLOBAL_CONFIG.field_mapping or ""
            )
            if field_mapping.prompt:
                return StreamProcessor.get_field_value(payload, field_mapping.prompt)
            return ""
        except Exception:
            return ""

    def _set_field_value(self, data: Dict[str, Any], path: str, value: str) -> None:
        """Set value in nested dictionary using dot-separated path."""
        if not path or not isinstance(data, dict):
            return

        try:
            keys = path.split(".")
            current = data

            # Navigate to the parent of the target field
            for key in keys[:-1]:
                if key.isdigit():
                    if isinstance(current, list):
                        current = current[int(key)]
                    else:
                        return
                elif isinstance(current, list) and current:
                    if isinstance(current[0], dict):
                        current = current[0].setdefault(key, {})
                    else:
                        return
                elif isinstance(current, dict):
                    current = current.setdefault(key, {})
                else:
                    return

            # Set the final field value
            final_key = keys[-1]
            if final_key.isdigit():
                if isinstance(current, list) and len(current) > int(final_key):
                    current[int(final_key)] = value
            elif isinstance(current, dict):
                current[final_key] = value
            elif isinstance(current, list) and current and isinstance(current[0], dict):
                current[0][final_key] = value

        except (KeyError, IndexError, TypeError, ValueError):
            # If we can't set the nested field, log a warning but don't fail
            pass

    def _handle_response_error(
        self, response, task_logger, start_time: float = 0
    ) -> bool:
        """Handle HTTP status code errors."""
        if response.status_code != HTTP_OK:
            error_msg = f"Request failed with status {response.status_code}. Response: {response.text}"
            response_time = (time.time() - start_time) * 1000 if start_time > 0 else 0
            ErrorHandler.handle_general_exception(
                error_msg, task_logger, response, response_time
            )
            return True
        return False

    def _handle_stream_request(
        self, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str]:
        """Handle streaming API request with comprehensive metrics collection."""
        task_logger = logger.bind(task_id=self.task_id)
        metrics = StreamMetrics()
        request_kwargs = {**base_request_kwargs, "stream": True}
        field_mapping = ConfigManager.parse_field_mapping(
            GLOBAL_CONFIG.field_mapping or ""
        )
        response = None
        has_failed = False
        actual_request_start_time = 0.0
        try:
            actual_request_start_time = time.time()
            with self.client.post(GLOBAL_CONFIG.api_path, **request_kwargs) as response:
                if self._handle_response_error(response, task_logger, start_time):
                    has_failed = True
                    return "", ""

                try:
                    # Process as streaming response
                    for chunk in response.iter_lines():
                        error_msg = StreamProcessor.check_chunk_error(
                            chunk, field_mapping, task_logger
                        )
                        if error_msg:
                            response_time = (time.time() - start_time) * 1000
                            ErrorHandler.handle_general_exception(
                                error_msg, task_logger, response, response_time
                            )
                            has_failed = True
                            return "", ""

                        metrics = StreamProcessor.process_chunk(
                            chunk,
                            field_mapping,
                            actual_request_start_time,
                            metrics,
                            task_logger,
                        )

                        # if chunk == b"data: [DONE]":
                        #     break

                    # Only mark as success if no failures occurred
                    if not has_failed:
                        # Fire completion events for streaming
                        total_time = (time.time() - start_time) * 1000
                        completion_time = (
                            (time.time() - metrics.first_output_token_time) * 1000
                            if metrics.first_token_received
                            else 0
                        )

                        EventManager.fire_metric_event(
                            METRIC_TTOC,
                            completion_time,
                            len(metrics.model_output),
                        )
                        EventManager.fire_metric_event(
                            METRIC_TTT,
                            total_time,
                            len(metrics.model_output) + len(metrics.reasoning_content),
                        )
                        response.success()

                except OSError as e:
                    task_logger.error(f"Network error during stream processing: {e}")
                    response_time = (time.time() - start_time) * 1000
                    ErrorHandler.handle_general_exception(
                        str(e), task_logger, response, response_time
                    )
                    has_failed = True

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            ErrorHandler.handle_general_exception(
                str(e), task_logger, response, response_time
            )
            has_failed = True

        return metrics.reasoning_content, metrics.model_output

    def _handle_non_stream_request(
        self, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str]:
        """Handle non-streaming API request."""
        task_logger = logger.bind(task_id=self.task_id)
        request_kwargs = {**base_request_kwargs, "stream": False}
        model_output, reasoning_content = "", ""
        field_mapping = ConfigManager.parse_field_mapping(
            GLOBAL_CONFIG.field_mapping or ""
        )

        has_failed = False
        try:
            with self.client.post(GLOBAL_CONFIG.api_path, **request_kwargs) as response:
                total_time = (time.time() - start_time) * 1000

                if self._handle_response_error(response, task_logger, start_time):
                    has_failed = True
                    return "", ""

                try:
                    resp_json = response.json()

                    error_msg = ErrorHandler.check_json_error(resp_json)
                    if error_msg:
                        ErrorHandler.handle_general_exception(
                            error_msg, task_logger, response, total_time
                        )
                        has_failed = True
                        return "", ""

                    model_output = (
                        StreamProcessor.get_field_value(
                            resp_json, field_mapping.content
                        )
                        if field_mapping.content
                        else ""
                    )
                    reasoning_content = (
                        StreamProcessor.get_field_value(
                            resp_json, field_mapping.reasoning_content
                        )
                        if field_mapping.reasoning_content
                        else ""
                    )

                    # Only mark as success if no failures occurred
                    if not has_failed:
                        EventManager.fire_metric_event(
                            METRIC_TTT,
                            total_time,
                            len(model_output) + len(reasoning_content),
                        )
                        response.success()

                except (json.JSONDecodeError, KeyError) as e:
                    task_logger.error(f"Failed to parse response JSON: {e}")
                    ErrorHandler.handle_general_exception(
                        str(e), task_logger, response, total_time
                    )
                    has_failed = True

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            ErrorHandler.handle_general_exception(
                str(e), task_logger, response, response_time
            )
            has_failed = True

        return reasoning_content, model_output

    def _log_token_counts(
        self, user_prompt: str, reasoning_content: str, model_output: str
    ) -> None:
        """Calculate and log token counts for the completed request."""
        task_logger = logger.bind(task_id=self.task_id)
        try:
            model_name = GLOBAL_CONFIG.model_name
            system_tokens = count_tokens(GLOBAL_CONFIG.system_prompt or "", model_name)
            user_tokens = count_tokens(user_prompt, model_name)
            reasoning_tokens = count_tokens(reasoning_content, model_name)
            completion_tokens = count_tokens(model_output, model_name)

            total_output_tokens = reasoning_tokens + completion_tokens
            total_tokens = total_output_tokens + user_tokens + system_tokens

            GLOBAL_TASK_QUEUE["completion_tokens_queue"].put(int(total_output_tokens))
            GLOBAL_TASK_QUEUE["all_tokens_queue"].put(int(total_tokens))
        except Exception as e:
            task_logger.error(f"Failed to count tokens: {e}", exc_info=True)

    @task
    def chat_request(self):
        """Main Locust task that executes a single chat request."""
        task_logger = logger.bind(task_id=self.task_id)
        base_request_kwargs, user_prompt = self.prepare_request_kwargs()

        if not base_request_kwargs:
            task_logger.error("Failed to generate request arguments. Skipping task.")
            return

        if GLOBAL_CONFIG.cert_config:
            base_request_kwargs["cert"] = GLOBAL_CONFIG.cert_config

        start_time = time.time()
        reasoning_content, model_output = "", ""

        try:
            if GLOBAL_CONFIG.stream_mode:
                reasoning_content, model_output = self._handle_stream_request(
                    base_request_kwargs, start_time
                )
            else:
                reasoning_content, model_output = self._handle_non_stream_request(
                    base_request_kwargs, start_time
                )
        except Exception as e:
            task_logger.error(
                f"Unhandled exception in chat_request: {e}", exc_info=True
            )

        if reasoning_content or model_output:
            self._log_token_counts(user_prompt or "", reasoning_content, model_output)
