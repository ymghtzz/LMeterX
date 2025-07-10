"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Optimized and refactored Locust test file for LLM performance testing.
"""

import json
import os
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

import urllib3
from gevent import queue
from locust import HttpUser, between, events, task
from urllib3.exceptions import InsecureRequestWarning

from engine.core import (
    CertificateManager,
    ConfigManager,
    GlobalConfig,
    StreamMetrics,
    ValidationManager,
)
from engine.processing import ErrorHandler, EventManager, StreamProcessor
from utils.config import (
    DEFAULT_API_PATH,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_WAIT_TIME_MAX,
    DEFAULT_WAIT_TIME_MIN,
    HTTP_OK,
    METRIC_TTOC,
    METRIC_TTT,
)
from utils.logger import logger
from utils.tools import count_tokens, mask_sensitive_data

# Disable the specific InsecureRequestWarning from urllib3
urllib3.disable_warnings(InsecureRequestWarning)

# === GLOBAL STATE ===
GLOBAL_CONFIG = GlobalConfig()
GLOBAL_TASK_QUEUE: Dict[str, queue.Queue] = {
    "completion_tokens_queue": queue.Queue(),
    "all_tokens_queue": queue.Queue(),
}
_start_time: Optional[float] = None


# === REQUEST HANDLERS ===
class RequestHandler:
    """Handles different types of API requests."""

    def __init__(self, config: GlobalConfig, task_logger):
        """Initialize the RequestHandler with configuration and logger.

        Args:
            config: Global configuration object
            task_logger: Task-specific logger instance
        """
        self.config = config
        self.task_logger = task_logger

    def prepare_request_kwargs(
        self, prompt_data: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Handle API requests with user-provided payload."""
        try:
            if not self.config.request_payload:
                self.task_logger.error("No request payload provided for API endpoint")
                return None, None

            try:
                payload = json.loads(str(self.config.request_payload))
            except json.JSONDecodeError as e:
                self.task_logger.error(f"Invalid JSON in request payload: {e}")
                return None, None

            user_prompt = ""

            # Check if test_data is empty (no dataset mode)
            if not self.config.test_data or self.config.test_data.strip() == "":
                self.task_logger.info("Using original request payload without dataset")
                user_prompt = self._extract_prompt_from_payload(payload)
            else:
                # Dataset mode - update payload with prompt data
                user_prompt = prompt_data.get("prompt", DEFAULT_PROMPT)

                # Special handling for chat/completions API
                if self.config.api_path == DEFAULT_API_PATH:
                    self._handle_chat_completions_payload(
                        payload, prompt_data, user_prompt
                    )
                else:
                    # For other APIs, use field mapping to update prompt
                    self._handle_custom_api_payload(payload, user_prompt)

            # Set request name based on API path
            request_name = (
                "chat_completions"
                if self.config.api_path == DEFAULT_API_PATH
                else "api_request"
            )

            base_request_kwargs = {
                "json": payload,
                "headers": self.config.headers,
                "catch_response": True,
                "name": request_name,
                "verify": False,
                "timeout": DEFAULT_TIMEOUT,
            }

            if self.config.cookies:
                base_request_kwargs["cookies"] = self.config.cookies

            return base_request_kwargs, user_prompt

        except Exception as e:
            self.task_logger.error(
                f"Failed to prepare custom API request: {e}", exc_info=True
            )
            return None, None

    def _handle_chat_completions_payload(
        self, payload: Dict[str, Any], prompt_data: Dict[str, Any], user_prompt: str
    ) -> None:
        """Handle chat/completions API payload with image support."""
        try:
            # Build system message if configured
            messages: List[Dict[str, Any]] = []
            if self.config.system_prompt:
                messages.append(
                    {"role": "system", "content": self.config.system_prompt}
                )

            # Check for image data in prompt_data
            image_base64 = prompt_data.get("image_base64", "")
            image_url = prompt_data.get("image_url", "")

            if image_base64:
                # Use base64 encoded image
                content_list = [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ]
                messages.append({"role": "user", "content": content_list})
            elif image_url:
                # Use image URL
                content_list = [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ]
                messages.append({"role": "user", "content": content_list})
            else:
                # Text-only message
                messages.append({"role": "user", "content": user_prompt})

            # Update the messages field in payload
            payload["messages"] = messages

            # Auto-supplement stream field if missing or empty
            if (
                "stream" not in payload
                or payload.get("stream") is None
                or payload.get("stream") == ""
            ):
                payload["stream"] = self.config.stream_mode
                self.task_logger.debug(
                    f"Auto-set stream field to: {self.config.stream_mode}"
                )

            # Auto-supplement model field if missing or empty
            if (
                "model" not in payload
                or payload.get("model") is None
                or payload.get("model") == ""
            ):
                if self.config.model_name:
                    payload["model"] = self.config.model_name
                    self.task_logger.debug(
                        f"Auto-set model field to: {self.config.model_name}"
                    )

        except Exception as e:
            self.task_logger.warning(f"Failed to update chat/completions payload: {e}")
            # Fallback to simple field mapping
            self._handle_custom_api_payload(payload, user_prompt)

    def _handle_custom_api_payload(
        self, payload: Dict[str, Any], user_prompt: str
    ) -> None:
        """Handle custom API payload using field mapping."""
        try:
            # Parse field mapping to get prompt field path
            field_mapping = ConfigManager.parse_field_mapping(
                self.config.field_mapping or ""
            )

            # Update payload with current prompt data if field mapping is configured
            if field_mapping.prompt:
                try:
                    self._set_field_value(payload, field_mapping.prompt, user_prompt)
                except Exception as e:
                    self.task_logger.warning(f"Failed to update prompt in payload: {e}")
            else:
                self.task_logger.warning(
                    "No prompt field mapping configured, using original payload"
                )
        except Exception as e:
            self.task_logger.warning(f"Failed to handle custom API payload: {e}")

    def _extract_prompt_from_payload(self, payload: Dict[str, Any]) -> str:
        """Extract prompt content from custom payload using field mapping."""
        try:
            field_mapping = ConfigManager.parse_field_mapping(
                self.config.field_mapping or ""
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


# === STREAM HANDLERS ===
class StreamHandler:
    """Handles streaming and non-streaming request processing."""

    def __init__(self, config: GlobalConfig, task_logger):
        """Initialize the StreamHandler with configuration and logger.

        Args:
            config: Global configuration object
            task_logger: Task-specific logger instance
        """
        self.config = config
        self.task_logger = task_logger

    def handle_stream_request(
        self, client, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str]:
        """Handle streaming API request with comprehensive metrics collection."""
        metrics = StreamMetrics()
        request_kwargs = {**base_request_kwargs, "stream": True}
        field_mapping = ConfigManager.parse_field_mapping(
            self.config.field_mapping or ""
        )
        response = None
        has_failed = False
        actual_request_start_time = 0.0
        request_name = base_request_kwargs.get("name", "failure")

        try:
            actual_request_start_time = time.time()
            with client.post(self.config.api_path, **request_kwargs) as response:
                if self._handle_response_error(response, start_time, request_name):
                    has_failed = True
                    return "", ""

                try:
                    # Process as streaming response
                    for chunk in response.iter_lines():
                        error_msg = StreamProcessor.check_chunk_error(
                            chunk, field_mapping, self.task_logger
                        )
                        if error_msg:
                            response_time = (time.time() - start_time) * 1000
                            ErrorHandler.handle_general_exception(
                                error_msg,
                                self.task_logger,
                                response,
                                response_time,
                                request_name,
                            )
                            has_failed = True
                            return "", ""

                        metrics = StreamProcessor.process_chunk(
                            chunk,
                            field_mapping,
                            actual_request_start_time,
                            metrics,
                            self.task_logger,
                        )

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
                            METRIC_TTOC, completion_time, len(metrics.model_output)
                        )
                        EventManager.fire_metric_event(
                            METRIC_TTT,
                            total_time,
                            len(metrics.model_output) + len(metrics.reasoning_content),
                        )
                        response.success()

                except OSError as e:
                    self.task_logger.error(
                        f"Network error during stream processing: {e}"
                    )
                    response_time = (time.time() - start_time) * 1000
                    ErrorHandler.handle_general_exception(
                        str(e), self.task_logger, response, response_time, request_name
                    )
                    has_failed = True

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            ErrorHandler.handle_general_exception(
                str(e), self.task_logger, response, response_time, request_name
            )
            has_failed = True

        return metrics.reasoning_content, metrics.model_output

    def handle_non_stream_request(
        self, client, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str]:
        """Handle non-streaming API request."""
        request_kwargs = {**base_request_kwargs, "stream": False}
        model_output, reasoning_content = "", ""
        field_mapping = ConfigManager.parse_field_mapping(
            self.config.field_mapping or ""
        )
        request_name = base_request_kwargs.get("name", "failure")

        has_failed = False
        try:
            with client.post(self.config.api_path, **request_kwargs) as response:
                total_time = (time.time() - start_time) * 1000

                if self._handle_response_error(response, start_time, request_name):
                    has_failed = True
                    return "", ""

                try:
                    resp_json = response.json()

                    error_msg = ErrorHandler.check_json_error(resp_json)
                    if error_msg:
                        ErrorHandler.handle_general_exception(
                            error_msg,
                            self.task_logger,
                            response,
                            total_time,
                            request_name,
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
                    self.task_logger.error(f"Failed to parse response JSON: {e}")
                    ErrorHandler.handle_general_exception(
                        str(e), self.task_logger, response, total_time, request_name
                    )
                    has_failed = True

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            ErrorHandler.handle_general_exception(
                str(e), self.task_logger, response, response_time, request_name
            )
            has_failed = True

        return reasoning_content, model_output

    def _handle_response_error(
        self, response, start_time: float = 0, request_name: str = "failure"
    ) -> bool:
        """Handle HTTP status code errors."""
        if response.status_code != HTTP_OK:
            error_msg = f"Request failed with status {response.status_code}. Response: {response.text}"
            response_time = (time.time() - start_time) * 1000 if start_time > 0 else 0
            ErrorHandler.handle_general_exception(
                error_msg, self.task_logger, response, response_time, request_name
            )
            return True
        return False


# === LOCUST EVENT HOOKS ===
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
        default=DEFAULT_API_PATH,
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
    parser.add_argument(
        "--test_data",
        type=str,
        default="",
        help="Custom test data in JSONL format or file path",
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
        GLOBAL_CONFIG.test_data = options.test_data
        # Parse and validate configuration
        GLOBAL_CONFIG.headers = ConfigManager.parse_headers(
            options.headers, task_logger
        )
        GLOBAL_CONFIG.cookies = ConfigManager.parse_cookies(
            options.cookies, task_logger
        )
        GLOBAL_CONFIG.cert_config = CertificateManager.configure_certificates(
            GLOBAL_CONFIG.cert_file, GLOBAL_CONFIG.key_file, task_logger
        )

        # Validate configuration before proceeding
        if not ValidationManager.validate_config(GLOBAL_CONFIG, task_logger):
            raise ValueError("Invalid configuration provided")

        # Initialize prompt queue
        if not hasattr(environment, "prompt_queue"):
            try:
                from utils.tools import init_prompt_queue

                environment.prompt_queue = init_prompt_queue(
                    chat_type=options.chat_type,
                    test_data=options.test_data or "",
                    task_logger=task_logger,
                )
            except Exception as e:
                task_logger.error(f"Failed to initialize prompt queue: {e}")
                environment.prompt_queue = queue.Queue()

        environment.global_config = GLOBAL_CONFIG
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


# === MAIN USER CLASS ===
class LLMTestUser(HttpUser):
    """A user class that simulates a client making requests to an LLM service."""

    wait_time = between(DEFAULT_WAIT_TIME_MIN, DEFAULT_WAIT_TIME_MAX)

    def __init__(self, environment):
        """Initialize the LLMTestUser with environment and handlers.

        Args:
            environment: Locust environment object
        """
        super().__init__(environment)
        self.task_logger = logger.bind(task_id=GLOBAL_CONFIG.task_id)
        self.request_handler = RequestHandler(GLOBAL_CONFIG, self.task_logger)
        self.stream_handler = StreamHandler(GLOBAL_CONFIG, self.task_logger)

    def get_next_prompt(self) -> Dict[str, Any]:
        """Fetch the next prompt from the shared queue."""
        # Check if we're in no-dataset mode
        if not GLOBAL_CONFIG.test_data or GLOBAL_CONFIG.test_data.strip() == "":
            self.task_logger.warning("No dataset mode - returning empty prompt data")
            return {"id": "no_dataset", "prompt": ""}

        try:
            prompt_data = self.environment.prompt_queue.get_nowait()
            self.environment.prompt_queue.put_nowait(prompt_data)
            return prompt_data
        except queue.Empty:
            self.task_logger.warning("Prompt queue is empty. Using default prompt.")
            return {"id": "default", "prompt": DEFAULT_PROMPT}

    def _log_token_counts(
        self, user_prompt: str, reasoning_content: str, model_output: str
    ) -> None:
        """Calculate and log token counts for the completed request."""
        try:
            model_name = GLOBAL_CONFIG.model_name or ""
            system_tokens = count_tokens(GLOBAL_CONFIG.system_prompt or "", model_name)
            user_tokens = count_tokens(user_prompt, model_name)
            reasoning_tokens = count_tokens(reasoning_content, model_name)
            completion_tokens = count_tokens(model_output, model_name)

            total_output_tokens = reasoning_tokens + completion_tokens
            total_tokens = total_output_tokens + user_tokens + system_tokens

            GLOBAL_TASK_QUEUE["completion_tokens_queue"].put(int(total_output_tokens))
            GLOBAL_TASK_QUEUE["all_tokens_queue"].put(int(total_tokens))
        except Exception as e:
            self.task_logger.error(f"Failed to count tokens: {e}", exc_info=True)

    @task
    def chat_request(self):
        """Main Locust task that executes a single chat request."""

        prompt_data = self.get_next_prompt()

        base_request_kwargs, user_prompt = self.request_handler.prepare_request_kwargs(
            prompt_data
        )
        self.task_logger.info(f"base_request_kwargs: {base_request_kwargs}")

        if not base_request_kwargs:
            self.task_logger.error(
                "Failed to generate request arguments. Skipping task."
            )
            return

        if GLOBAL_CONFIG.cert_config:
            base_request_kwargs["cert"] = GLOBAL_CONFIG.cert_config

        start_time = time.time()
        reasoning_content, model_output = "", ""
        request_name = (
            base_request_kwargs.get("name", "failure")
            if base_request_kwargs
            else "failure"
        )

        try:
            if GLOBAL_CONFIG.stream_mode:
                reasoning_content, model_output = (
                    self.stream_handler.handle_stream_request(
                        self.client, base_request_kwargs, start_time
                    )
                )
            else:
                reasoning_content, model_output = (
                    self.stream_handler.handle_non_stream_request(
                        self.client, base_request_kwargs, start_time
                    )
                )
        except Exception as e:
            self.task_logger.error(
                f"Unhandled exception in chat_request: {e}", exc_info=True
            )
            # Record the failure event for unhandled exceptions
            response_time = (time.time() - start_time) * 1000
            ErrorHandler.handle_general_exception(
                f"Unhandled exception in chat_request: {e}",
                self.task_logger,
                response=None,
                response_time=response_time,
                request_name=request_name,
            )

        if reasoning_content or model_output:
            self._log_token_counts(user_prompt or "", reasoning_content, model_output)
