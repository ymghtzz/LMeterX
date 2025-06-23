"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import json
import os
import tempfile
import time
from typing import Any, Dict, Optional, Tuple

import urllib3
from gevent import queue
from locust import HttpUser, between, events, task
from urllib3.exceptions import InsecureRequestWarning

from utils.logger import st_logger as logger
from utils.tools import count_tokens

# Disable the specific InsecureRequestWarning from urllib3.
urllib3.disable_warnings(InsecureRequestWarning)

# --- Constants ---
HTTP_OK = 200
DEFAULT_TIMEOUT = 90
DEFAULT_WAIT_TIME_MIN = 1
DEFAULT_WAIT_TIME_MAX = 3
ERROR_CODE_THRESHOLD = 0
DEFAULT_PROMPT = "Tell me about the history of Artificial Intelligence."

# --- Global Configuration & State ---

# This dictionary holds the global configuration for all users, initialized with defaults.
# It's populated from command-line arguments during the 'init' event.
GLOBAL_USER_CONFIG = {
    "api_path": "/v1/chat/completions",
    "headers": {"Content-Type": "application/json"},
    "request_payload": None,
    "model_name": None,
    "system_prompt": None,
    "stream_mode": True,
    "chat_type": 0,
    "cert_file": None,
    "key_file": None,
    "cert_config": None,
}

# This dictionary holds queues for aggregating performance metrics across all users.
GLOBAL_TASK_QUEUE: Dict[str, queue.Queue] = {
    "completion_tokens_queue": queue.Queue(),
    "all_tokens_queue": queue.Queue(),
}

_start_time = None

# --- Locust Event Hooks ---


@events.init_command_line_parser.add_listener
def init_parser(parser):
    """
    Adds custom command-line arguments to the Locust parser.
    These arguments allow for dynamic configuration of the test without changing the code.
    """
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
        "--task-id",
        type=str,
        default="",
        help="The unique identifier for the test task.",
    )


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """
    Listener for the 'init' event, which runs once when Locust starts.
    It populates the GLOBAL_USER_CONFIG with parsed command-line options.
    """
    global _start_time, GLOBAL_USER_CONFIG
    if not environment.parsed_options:
        logger.warning(
            "No parsed options found in environment. Skipping configuration."
        )
        return

    options = environment.parsed_options
    task_id = options.task_id or os.environ.get("TASK_ID", "unknown")
    task_logger = logger.bind(task_id=task_id)

    try:
        # Update global config from command line options
        GLOBAL_USER_CONFIG.update(
            {
                "task_id": task_id,
                "api_path": options.api_path,
                "headers": options.headers,
                "request_payload": options.request_payload,
                "model_name": options.model_name,
                "system_prompt": options.system_prompt,
                "stream_mode": str(options.stream_mode).lower() in ("true", "1"),
                "chat_type": int(options.chat_type),
                "cert_file": options.cert_file,
                "key_file": options.key_file,
            }
        )

        # Parse and validate headers
        _process_headers(task_logger)

        # Configure client certificates
        _configure_certificates(task_logger)

        # Initialize the prompt queue for feeding data to users
        if not hasattr(environment, "prompt_queue"):
            try:
                from utils.tools import init_prompt_queue

                environment.prompt_queue = init_prompt_queue(
                    chat_type=options.chat_type, task_logger=task_logger
                )
            except Exception as e:
                task_logger.error(f"Failed to initialize prompt queue: {e}")
                # Create an empty queue as fallback
                environment.prompt_queue = queue.Queue()

        environment.global_config = GLOBAL_USER_CONFIG
        from utils.tools import mask_sensitive_data

        masked_config = mask_sensitive_data(GLOBAL_USER_CONFIG)
        task_logger.info(f"Locust initialization complete. Config: {masked_config}")
        _start_time = time.time()  # Record the test start time

    except Exception as e:
        task_logger.error(f"Error during Locust initialization: {e}", exc_info=True)
        raise


def _process_headers(task_logger) -> None:
    """Helper function to parse headers from a JSON string."""
    cli_headers = GLOBAL_USER_CONFIG["headers"]
    default_headers = {"Content-Type": "application/json"}

    if isinstance(cli_headers, str) and cli_headers.strip():
        try:
            parsed_headers = json.loads(cli_headers)
            if not isinstance(parsed_headers, dict):
                raise ValueError("Headers must be a JSON object")
            GLOBAL_USER_CONFIG["headers"] = parsed_headers
        except (json.JSONDecodeError, ValueError) as e:
            task_logger.error(
                f"Failed to parse headers JSON string '{cli_headers}': {e}. Using default headers."
            )
            GLOBAL_USER_CONFIG["headers"] = default_headers
    elif not isinstance(cli_headers, dict):
        task_logger.warning(
            f"Headers parameter is not a string or dict (type: {type(cli_headers)}). Using default headers."
        )
        GLOBAL_USER_CONFIG["headers"] = default_headers


def _configure_certificates(task_logger) -> None:
    """Helper function to configure client certificate and key."""
    cert_file = (
        str(GLOBAL_USER_CONFIG.get("cert_file", ""))
        if GLOBAL_USER_CONFIG.get("cert_file")
        else None
    )
    key_file = (
        str(GLOBAL_USER_CONFIG.get("key_file", ""))
        if GLOBAL_USER_CONFIG.get("key_file")
        else None
    )

    def _is_file_accessible(file_path: Optional[str]) -> bool:
        """Check if file exists and is readable."""
        if not file_path or not isinstance(file_path, str) or not file_path.strip():
            return False
        try:
            return os.path.exists(file_path) and os.access(file_path, os.R_OK)
        except (OSError, IOError):
            return False

    cert_valid = _is_file_accessible(cert_file)
    key_valid = _is_file_accessible(key_file)

    if (
        cert_valid
        and key_valid
        and isinstance(cert_file, str)
        and isinstance(key_file, str)
    ):
        GLOBAL_USER_CONFIG["cert_config"] = (cert_file, key_file)
        task_logger.info(
            f"Configured certificate and key files: {cert_file}, {key_file}"
        )
    elif cert_valid and isinstance(cert_file, str):
        GLOBAL_USER_CONFIG["cert_config"] = cert_file
        task_logger.info(f"Configured certificate file: {cert_file}")
    elif isinstance(cert_file, str) and cert_file.strip():
        task_logger.warning(f"Certificate file not accessible: {cert_file}")
    elif isinstance(key_file, str) and key_file.strip():
        task_logger.warning(f"Key file not accessible: {key_file}")
    else:
        task_logger.info("No certificate files configured")
        GLOBAL_USER_CONFIG["cert_config"] = None


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Listener for the 'test_stop' event.
    Calculates final metrics and saves them to a JSON file.
    """
    task_id = GLOBAL_USER_CONFIG.get("task_id", "unknown")
    task_logger = logger.bind(task_id=task_id)
    end_time = time.time()

    if _start_time:
        execution_time = end_time - _start_time
        task_logger.info(f"Test duration: {execution_time:.2f} seconds.")
    else:
        task_logger.warning(
            "Start time was not recorded; cannot calculate execution time."
        )
        execution_time = 0

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

        # Save results to a temporary file.
        result_file = os.path.join(
            tempfile.gettempdir(), "locust_result", task_id, "result.json"
        )
        result_dir = os.path.dirname(result_file)
        os.makedirs(result_dir, exist_ok=True)

        with open(result_file, "w") as f:
            json.dump(locust_result, f, indent=4)
        task_logger.info(f"Successfully saved locust results to {result_file}")

    except Exception as e:
        task_logger.error(f"Failed to save locust results: {e}", exc_info=True)


def _fire_failure_event(
    name: str = "failure",
    response_time: float = 0,
    response_length: int = 0,
):
    """Helper function to fire failure events."""
    events.request.fire(
        request_type="failure",
        name=name,
        response_time=response_time,
        response_length=response_length,
    )


def _fire_metric_event(name: str, response_time: float, response_length: int):
    """Helper function to fire metric events."""
    events.request.fire(
        request_type="metric",
        name=name,
        response_time=response_time,
        response_length=response_length,
    )


def _check_response_error(response_data: Dict[str, Any], task_logger) -> Optional[str]:
    """Check if response contains error conditions."""
    if (response_data.get("code", 0) > 0) or (
        response_data.get("error") and response_data.get("error") != ""
    ):
        return f"Response contains error: {response_data}"
    return None


def _check_json_error(json_data: Dict[str, Any]) -> Optional[str]:
    """Check if JSON data contains error conditions based on code or error fields."""
    try:
        if not isinstance(json_data, dict):
            return None

        code = json_data.get("code", 0)
        error = json_data.get("error")

        if code < 0:
            return f"Response maybe contains error: response={json_data}"

        if error is not None and str(error).strip() != "":
            return f"Response maybe contains error: response={json_data}"

        return None

    except Exception as e:
        return None


class LLMTestUser(HttpUser):
    """
    A user class that simulates a client making requests to an LLM service.
    """

    wait_time = between(DEFAULT_WAIT_TIME_MIN, DEFAULT_WAIT_TIME_MAX)

    @property
    def task_id(self) -> str:
        """Returns the task_id from the environment's global configuration."""
        return self.environment.global_config.get("task_id", "unknown")

    def get_next_prompt(self) -> Tuple[str, Any]:
        """
        Fetches the next prompt from the shared queue.
        If the queue is empty, returns a default prompt.
        """
        task_logger = logger.bind(task_id=self.task_id)
        try:
            prompt_id, prompt_data = self.environment.prompt_queue.get_nowait()
            self.environment.prompt_queue.put_nowait(
                (prompt_id, prompt_data)
            )  # Cycle prompt back to the end
            return prompt_id, prompt_data
        except queue.Empty:
            task_logger.warning("Prompt queue is empty. Using default prompt.")
            return "default", DEFAULT_PROMPT

    def handle_request_kwargs(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Prepares the request payload and arguments based on the prompt and global config.
        Supports both text-only and multimodal (text + image) inputs.
        """
        task_logger = logger.bind(task_id=self.task_id)
        if GLOBAL_USER_CONFIG["api_path"] != "/v1/chat/completions":
            task_logger.error(f"Unsupported API path: {GLOBAL_USER_CONFIG['api_path']}")
            return None, None

        prompt_id, prompt_data = self.get_next_prompt()
        if not prompt_data:
            task_logger.warning(f"Received empty prompt data for ID {prompt_id}.")
            return None, None

        try:
            system_message = (
                [{"role": "system", "content": GLOBAL_USER_CONFIG["system_prompt"]}]
                if GLOBAL_USER_CONFIG["system_prompt"]
                else []
            )

            if isinstance(prompt_data, str):  # Text-only chat
                user_prompt = prompt_data
                messages = system_message + [{"role": "user", "content": user_prompt}]
            else:  # Multimodal chat
                user_prompt = prompt_data.get("prompt", "")
                image_base64 = prompt_data.get("image_base64", "")
                content_list = [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                    },
                ]
                messages = system_message + [
                    {
                        "role": "user",
                        "content": content_list,  # type: ignore
                    }
                ]

            payload = {
                "model": GLOBAL_USER_CONFIG["model_name"],
                "stream": GLOBAL_USER_CONFIG["stream_mode"],
                "messages": messages,
            }

            base_request_kwargs = {
                "json": payload,
                "headers": GLOBAL_USER_CONFIG["headers"],
                "catch_response": True,
                "name": "chat_completions",
                "verify": False,
                "timeout": DEFAULT_TIMEOUT,
            }
            return base_request_kwargs, user_prompt

        except Exception as e:
            task_logger.error(f"Failed to prepare request kwargs: {e}", exc_info=True)
            return None, None

    def _handle_general_exception(self, error_msg: str, response=None) -> None:
        """A centralized handler for logging exceptions during requests."""
        task_logger = logger.bind(task_id=self.task_id)
        task_logger.error(error_msg)

        if response:
            response.failure(error_msg)

        _fire_failure_event()

    def _process_stream_chunk(
        self,
        chunk: bytes,
        start_time: float,
        first_token_received: bool,
        first_thinking_received: bool,
        reasoning_is_active: bool,
        reasoning_ended: bool,
        first_output_token_time: float,
        first_thinking_token_time: float,
        model_output: str,
        reasoning_content: str,
        task_logger,
    ) -> Tuple[bool, bool, bool, bool, float, float, str, str]:
        """Process a single stream chunk and update state."""
        if not chunk or not chunk.startswith(b"data:"):
            return (
                first_token_received,
                first_thinking_received,
                reasoning_is_active,
                reasoning_ended,
                first_output_token_time,
                first_thinking_token_time,
                model_output,
                reasoning_content,
            )

        chunk = chunk.removeprefix(b"data: ")

        if chunk == b"[DONE]":
            return (
                first_token_received,
                first_thinking_received,
                reasoning_is_active,
                reasoning_ended,
                first_output_token_time,
                first_thinking_token_time,
                model_output,
                reasoning_content,
            )

        try:
            chunk_data = json.loads(chunk)
            delta = chunk_data.get("choices", [{}])[0].get("delta", {})
            content_chunk = delta.get("content", "")
            reasoning_chunk = delta.get("reasoning_content", "")

            if content_chunk:
                model_output += content_chunk
                if not first_token_received:
                    first_token_received = True
                    first_output_token_time = time.time()
                    ttfot = (first_output_token_time - start_time) * 1000
                    _fire_metric_event(
                        "Time_to_first_output_token", ttfot, len(content_chunk)
                    )

            if reasoning_chunk:
                reasoning_content += reasoning_chunk
                if not reasoning_is_active:
                    reasoning_is_active = True
                if not first_thinking_received:
                    first_thinking_received = True
                    first_thinking_token_time = time.time()
                    ttfrt = (first_thinking_token_time - start_time) * 1000
                    _fire_metric_event(
                        "Time_to_first_reasoning_token", ttfrt, len(reasoning_chunk)
                    )
            elif (
                reasoning_is_active
                and not reasoning_chunk
                and not reasoning_ended
                and content_chunk
            ):
                if first_thinking_received:
                    reasoning_ended = True
                    ttrc = (time.time() - first_thinking_token_time) * 1000
                    _fire_metric_event(
                        "Time_to_reasoning_completion", ttrc, len(reasoning_content)
                    )

        except (json.JSONDecodeError, IndexError, KeyError) as e:
            task_logger.warning(
                f"Could not process stream chunk: '{chunk.decode('utf-8', errors='replace')}'. Error: {e}"
            )

        return (
            first_token_received,
            first_thinking_received,
            reasoning_is_active,
            reasoning_ended,
            first_output_token_time,
            first_thinking_token_time,
            model_output,
            reasoning_content,
        )

    def _handle_response_error(self, response, task_logger) -> bool:
        """Handle HTTP status code errors. Returns True if error found."""
        if response.status_code != HTTP_OK:
            error_msg = f"Request failed with status {response.status_code}. Response: {response.text}"
            self._handle_general_exception(error_msg, response)
            return True
        return False

    def _check_stream_chunk_error(self, chunk: bytes, task_logger) -> Optional[str]:
        """Check streaming chunk for errors. Returns error message if found."""
        try:
            if not chunk or not isinstance(chunk, bytes):
                return None

            if chunk.startswith(b"data:"):
                chunk_content = chunk.removeprefix(b"data: ")

                if chunk_content == b"[DONE]":
                    return None

                if not chunk_content.strip():
                    return None

                try:
                    chunk_json = json.loads(chunk_content)
                    return _check_json_error(chunk_json)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    task_logger.debug(f"Failed to parse data chunk as JSON: {e}")
                    return None
            else:
                try:
                    if not chunk.strip():
                        return None

                    chunk_json = json.loads(chunk)
                    return _check_json_error(chunk_json)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    task_logger.debug(f"Failed to parse chunk as JSON: {e}")
                    return None

        except Exception as e:
            task_logger.warning(f"Unexpected error checking chunk for errors: {e}")
            return None

        return None

    def _handle_stream_request(
        self, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str]:
        """Handles a streaming API request and collects detailed performance metrics."""
        task_logger = logger.bind(task_id=self.task_id)
        model_output, reasoning_content = "", ""
        request_kwargs = {**base_request_kwargs, "stream": True}

        first_token_received, first_thinking_received = False, False
        reasoning_is_active, reasoning_ended = False, False
        first_output_token_time, first_thinking_token_time = 0.0, 0.0

        response = None
        try:
            with self.client.post(
                GLOBAL_USER_CONFIG["api_path"], **request_kwargs
            ) as response:
                # task_logger.info(
                #     f"Stream request response:{response.status_code}, {response.text}"
                # )

                if self._handle_response_error(response, task_logger):
                    return "", ""

                try:
                    for chunk in response.iter_lines():
                        error_msg = self._check_stream_chunk_error(chunk, task_logger)
                        if error_msg:
                            self._handle_general_exception(error_msg, response)
                            return "", ""

                        (
                            first_token_received,
                            first_thinking_received,
                            reasoning_is_active,
                            reasoning_ended,
                            first_output_token_time,
                            first_thinking_token_time,
                            model_output,
                            reasoning_content,
                        ) = self._process_stream_chunk(
                            chunk,
                            start_time,
                            first_token_received,
                            first_thinking_received,
                            reasoning_is_active,
                            reasoning_ended,
                            first_output_token_time,
                            first_thinking_token_time,
                            model_output,
                            reasoning_content,
                            task_logger,
                        )

                        if chunk == b"data: [DONE]":
                            break

                    # Fire completion events
                    total_time = (time.time() - start_time) * 1000
                    completion_time = (
                        (time.time() - first_output_token_time) * 1000
                        if first_token_received
                        else 0
                    )

                    _fire_metric_event(
                        "Time_to_output_completion", completion_time, len(model_output)
                    )
                    _fire_metric_event(
                        "Total_turnaround_time",
                        total_time,
                        len(model_output) + len(reasoning_content),
                    )
                    response.success()

                except (ConnectionError, TimeoutError, OSError) as e:
                    task_logger.error(f"Network error during stream processing: {e}")
                    self._handle_general_exception(str(e), response)

        except Exception as e:
            self._handle_general_exception(str(e), response)

        return reasoning_content, model_output

    def _handle_non_stream_request(
        self, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str]:
        """Handles a non-streaming API request."""
        task_logger = logger.bind(task_id=self.task_id)
        request_kwargs = {**base_request_kwargs, "stream": False}
        model_output, reasoning_content = "", ""

        try:
            with self.client.post(
                GLOBAL_USER_CONFIG["api_path"], **request_kwargs
            ) as response:
                total_time = (time.time() - start_time) * 1000

                if self._handle_response_error(response, task_logger):
                    return "", ""

                try:
                    resp_json = response.json()
                    # task_logger.info(f"Non-stream request response:{resp_json}")

                    error_msg = _check_json_error(resp_json)
                    if error_msg:
                        self._handle_general_exception(error_msg, response)
                        return "", ""

                    choice = resp_json.get("choices", [{}])[0]
                    message = choice.get("message", {})
                    model_output = message.get("content", "")
                    reasoning_content = message.get("reasoning_content", "")

                    _fire_metric_event(
                        "Total_turnaround_time",
                        total_time,
                        len(model_output) + len(reasoning_content),
                    )
                    response.success()

                except (json.JSONDecodeError, KeyError) as e:
                    task_logger.error(f"Failed to parse response JSON: {e}")
                    self._handle_general_exception(str(e), response)

        except Exception as e:
            self._handle_general_exception(str(e), response)

        return reasoning_content, model_output

    @task
    def chat_request(self):
        """
        The main Locust task that executes a single chat request.
        It calls the appropriate handler for streaming or non-streaming mode.
        """
        task_logger = logger.bind(task_id=self.task_id)
        base_request_kwargs, user_prompt = self.handle_request_kwargs()
        if not base_request_kwargs:
            task_logger.error("Failed to generate request arguments. Skipping task.")
            return

        if GLOBAL_USER_CONFIG["cert_config"]:
            base_request_kwargs["cert"] = GLOBAL_USER_CONFIG["cert_config"]

        start_time = time.time()
        reasoning_content, model_output = "", ""

        try:
            if GLOBAL_USER_CONFIG["stream_mode"]:
                reasoning_content, model_output = self._handle_stream_request(
                    base_request_kwargs, start_time
                )
            else:
                reasoning_content, model_output = self._handle_non_stream_request(
                    base_request_kwargs, start_time
                )
        except Exception as e:
            task_logger.error(
                f"Unhandled exception in chat_request. Error: {e}",
                exc_info=True,
            )

        if reasoning_content or model_output:
            self._log_token_counts(user_prompt, reasoning_content, model_output)

    def _log_token_counts(
        self, user_prompt: str, reasoning_content: str, model_output: str
    ) -> None:
        """Calculates and logs token counts for the completed request."""
        task_logger = logger.bind(task_id=self.task_id)
        try:
            model_name = GLOBAL_USER_CONFIG["model_name"]
            system_tokens = count_tokens(
                GLOBAL_USER_CONFIG["system_prompt"] or "", model_name
            )
            user_tokens = count_tokens(user_prompt, model_name)
            reasoning_tokens = count_tokens(reasoning_content, model_name)
            completion_tokens = count_tokens(model_output, model_name)

            total_output_tokens = reasoning_tokens + completion_tokens
            total_tokens = total_output_tokens + user_tokens + system_tokens

            GLOBAL_TASK_QUEUE["completion_tokens_queue"].put(int(total_output_tokens))
            GLOBAL_TASK_QUEUE["all_tokens_queue"].put(int(total_tokens))
        except Exception as e:
            task_logger.error(
                f"Failed to count tokens. Error: {e}",
                exc_info=True,
            )
