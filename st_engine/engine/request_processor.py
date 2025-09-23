"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import orjson

from config.base import DEFAULT_API_PATH, DEFAULT_PROMPT
from config.business import METRIC_TTOC, METRIC_TTT
from engine.core import (
    ConfigManager,
    FieldMapping,
    GlobalConfig,
    GlobalStateManager,
    StreamMetrics,
)
from utils.error_handler import ErrorResponse
from utils.event_handler import EventManager

global_state = GlobalStateManager()


# === STREAM PROCESSING ===
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
                # Check if key is a valid integer (including negative numbers)
                try:
                    index = int(key)
                    if isinstance(current, list):
                        current = current[index]
                    else:
                        return ""
                except ValueError:
                    # Key is not an integer, treat as dict key
                    if isinstance(current, list) and current:
                        if isinstance(current[0], dict):
                            current = current[0].get(key, {})
                        else:
                            return ""
                    elif isinstance(current, dict):
                        current = current.get(key, {})
                    else:
                        return ""

            # Ensure we never return None, always return a string
            if current is None:
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
                    # task_logger.info(f"Stream end, response: {chunk_str}")
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
                    # task_logger.info(f"Stream end, response: {chunk_str}")
                    return metrics
                content_chunk = chunk_str

        except (json.JSONDecodeError, IndexError, KeyError):
            task_logger.error(f"Error processing chunk: {chunk_str}")
            EventManager.fire_failure_event(
                name="failure",
                response_time=0,
                response_length=0,
                exception=Exception(f"Error processing chunk: {chunk_str}"),
            )
            return metrics

        # Process content tokens with enhanced safety checks
        if (
            content_chunk
            and isinstance(content_chunk, str)
            and len(content_chunk.strip()) > 0
        ):
            # Ensure metrics.model_output is not None
            if metrics.model_output is None:
                task_logger.warning(
                    "metrics.model_output was None, initializing to empty string"
                )
                metrics.model_output = ""

            # Prevent memory issues by limiting output length
            current_output_len = len(metrics.model_output)
            content_chunk_len = len(content_chunk)

            if current_output_len + content_chunk_len > MAX_OUTPUT_LENGTH:
                task_logger.warning(
                    f"Output length exceeded {MAX_OUTPUT_LENGTH} characters, truncating"
                )
                content_chunk = content_chunk[: MAX_OUTPUT_LENGTH - current_output_len]

            metrics.model_output += content_chunk
            if not metrics.first_token_received:
                metrics.first_token_received = True
                metrics.first_output_token_time = time.time()
                # Enhanced safety check for start_time and time calculations
                try:
                    if (
                        start_time is not None
                        and start_time > 0
                        and metrics.first_output_token_time is not None
                    ):
                        ttfot = (metrics.first_output_token_time - start_time) * 1000
                        if ttfot >= 0:  # Ensure positive time difference
                            EventManager.fire_metric_event(
                                "Time_to_first_output_token", ttfot, len(content_chunk)
                            )
                except Exception as e:
                    task_logger.warning(
                        f"Error calculating first output token time: {e}"
                    )
                # task_logger.info(f"Recv first output token: {content_chunk}")

        # Process reasoning tokens with enhanced safety checks
        if (
            reasoning_chunk
            and isinstance(reasoning_chunk, str)
            and len(reasoning_chunk.strip()) > 0
        ):
            # Ensure metrics.reasoning_content is not None
            if metrics.reasoning_content is None:
                task_logger.warning(
                    "metrics.reasoning_content was None, initializing to empty string"
                )
                metrics.reasoning_content = ""

            # Prevent memory issues by limiting reasoning content length
            current_reasoning_len = len(metrics.reasoning_content)
            reasoning_chunk_len = len(reasoning_chunk)

            if current_reasoning_len + reasoning_chunk_len > MAX_OUTPUT_LENGTH:
                task_logger.warning(
                    f"Reasoning content length exceeded {MAX_OUTPUT_LENGTH} characters, truncating"
                )
                reasoning_chunk = reasoning_chunk[
                    : MAX_OUTPUT_LENGTH - current_reasoning_len
                ]

            metrics.reasoning_content += reasoning_chunk
            if not metrics.reasoning_is_active:
                metrics.reasoning_is_active = True
            if not metrics.first_thinking_received:
                metrics.first_thinking_received = True
                metrics.first_thinking_token_time = time.time()
                # Enhanced safety check for start_time and time calculations
                try:
                    if (
                        start_time is not None
                        and start_time > 0
                        and metrics.first_thinking_token_time is not None
                    ):
                        ttfrt = (metrics.first_thinking_token_time - start_time) * 1000
                        if ttfrt >= 0:  # Ensure positive time difference
                            EventManager.fire_metric_event(
                                "Time_to_first_reasoning_token",
                                ttfrt,
                                len(reasoning_chunk),
                            )
                except Exception as e:
                    task_logger.warning(
                        f"Error calculating first reasoning token time: {e}"
                    )
                # task_logger.info(f"Recv first reasoning token: {reasoning_chunk}")
        elif (
            metrics.reasoning_is_active
            and not reasoning_chunk
            and not metrics.reasoning_ended
            and content_chunk
        ):
            if (
                metrics.first_thinking_received
                and metrics.first_thinking_token_time is not None
            ):
                metrics.reasoning_ended = True
                try:
                    current_time = time.time()
                    ttrc = (current_time - metrics.first_thinking_token_time) * 1000
                    if ttrc >= 0:  # Ensure positive time difference
                        # Ensure metrics.reasoning_content is not None before calling len()
                        reasoning_content_len = (
                            len(metrics.reasoning_content)
                            if metrics.reasoning_content is not None
                            else 0
                        )
                        EventManager.fire_metric_event(
                            "Time_to_reasoning_completion",
                            ttrc,
                            reasoning_content_len,
                        )
                except Exception as e:
                    task_logger.warning(
                        f"Error calculating reasoning completion time: {e}"
                    )
                # task_logger.info(
                #     f"Recv reasoning completion: {metrics.reasoning_content}"
                # )

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
        processed_chunk = StreamProcessor.remove_chunk_prefix(chunk_str, field_mapping)

        if not processed_chunk:
            return False, None, metrics

        # Check if matches stop_flag directly
        if StreamProcessor.check_stop_flag(processed_chunk, field_mapping):
            return True, None, metrics  # Normal stream end

        # Check if data format is JSON
        if field_mapping.data_format == "json":
            try:
                chunk_data = orjson.loads(processed_chunk)
            except (orjson.JSONDecodeError, TypeError) as e:
                task_logger.error(
                    f"Failed to parse chunk as JSON: {e} | Chunk: {processed_chunk}"
                )
                return True, f"JSON parsing error: {e}", metrics

            # Check end_field stop condition
            if StreamProcessor.check_end_field_stop(chunk_data, field_mapping):
                return True, None, metrics  # Normal stream end

            # Check for JSON errors
            error_msg = ErrorResponse._handle_json_error(chunk_data)
            if error_msg:
                return True, error_msg, metrics  # Error occurred

            # Extract and update metrics
            metrics = StreamProcessor.extract_metrics_from_chunk(
                chunk_data, field_mapping, metrics, start_time, task_logger
            )
        else:
            # For non-JSON format, treat processed_chunk as content
            metrics.content += processed_chunk
            if not metrics.first_token_received:
                metrics.first_token_received = True
                metrics.first_output_token_time = time.time()
                if start_time > 0 and metrics.first_output_token_time:
                    ttfot = (metrics.first_output_token_time - start_time) * 1000
                    EventManager.fire_metric_event(
                        "Time_to_first_output_token", ttfot, 0
                    )
        return False, None, metrics  # Continue processing


# === REQUEST HANDLERS ===
class PayloadBuilder:
    """Handles different types of API requests."""

    def __init__(self, config: GlobalConfig, task_logger) -> None:
        """Initialize the PayloadBuilder with configuration and logger.

        Args:
            config: Global configuration object
            task_logger: Task-specific logger instance
        """
        self.config = config
        self.task_logger = task_logger

    def prepare_request_kwargs(
        self, prompt_data: Optional[Dict[str, Any]]
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

            # Check if we're in dataset mode
            is_dataset_mode = bool(
                self.config.test_data and self.config.test_data.strip()
            )

            if not is_dataset_mode:
                # No dataset mode - use payload directly
                user_prompt = self._extract_prompt_from_payload(payload)
            else:
                # Dataset mode - update payload with prompt data
                if prompt_data is None:
                    self.task_logger.error(
                        "Dataset mode enabled but no prompt data provided"
                    )
                    return None, None

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
                else "custom_api"
            )

            base_request_kwargs = {
                "json": payload,
                "headers": self.config.headers,
                "catch_response": True,
                "name": request_name,
                "verify": False,
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
                current = self._navigate_to_key(current, key)
                if current is None:
                    return

            # Set the final field value
            self._set_final_value(current, keys[-1], value)

        except (KeyError, IndexError, TypeError, ValueError):
            # If we can't set the nested field, log a warning but don't fail
            pass

    def _navigate_to_key(self, current: Any, key: str) -> Any:
        """Navigate to a key in nested data structure."""
        # Check if key is a valid integer (including negative numbers)
        try:
            index = int(key)
            if isinstance(current, list):
                return current[index]
            else:
                return None
        except ValueError:
            # Key is not an integer, treat as dict key
            if isinstance(current, list) and current:
                if isinstance(current[0], dict):
                    return current[0].setdefault(key, {})
                else:
                    return None
            elif isinstance(current, dict):
                return current.setdefault(key, {})
            else:
                return None

    def _set_final_value(self, current: Any, final_key: str, value: str) -> None:
        """Set the final value in the data structure."""
        try:
            final_index = int(final_key)
            if isinstance(current, list):
                # For negative indices, ensure we're within bounds
                if -len(current) <= final_index < len(current):
                    current[final_index] = value
        except ValueError:
            # Final key is not an integer, treat as dict key
            if isinstance(current, dict):
                current[final_key] = value
            elif isinstance(current, list) and current and isinstance(current[0], dict):
                current[0][final_key] = value


# === STREAM HANDLERS ===
class APIClient:
    """Handles streaming and non-streaming request processing."""

    def __init__(self, config: GlobalConfig, task_logger) -> None:
        """Initialize the APIClient with configuration and logger.

        Args:
            config: Global configuration object
            task_logger: Task-specific logger instance
        """
        self.config = config
        self.task_logger = task_logger
        # Create ErrorResponse instance
        self.error_handler = ErrorResponse(config, task_logger)

    def _iter_stream_lines(self, response) -> Any:
        """Yield complete SSE lines using \n\n as delimiter. Robust version for HttpUser."""
        # For HttpUser, response is a requests.Response object
        if not hasattr(response, "iter_lines"):
            self.task_logger.error("Response object does not support streaming.")
            return

        try:
            for line in response.iter_lines(
                chunk_size=8192, decode_unicode=False, delimiter=b"\n"
            ):
                if not line:
                    continue
                # Ensure line is bytes
                if isinstance(line, str):
                    line = line.encode("utf-8", errors="ignore")
                yield line
        except Exception as e:
            self.task_logger.error(f"Error iterating over stream lines: {e}")
            # Yield any remaining buffer if possible, but don't let it crash the whole test.
            pass

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
                if self.error_handler._handle_status_code_error(
                    response, start_time, request_name
                ):
                    return "", "", usage

                try:
                    # Process as streaming response
                    for chunk in self._iter_stream_lines(response):
                        should_break, error_message, metrics = (
                            StreamProcessor.process_stream_chunk(
                                chunk,
                                field_mapping,
                                actual_start_time,
                                metrics,
                                self.task_logger,
                            )
                        )

                        if should_break:
                            if error_message:
                                # Error occurred, mark failure and exit
                                self.error_handler._handle_general_exception_event(
                                    error_msg=error_message,
                                    response=response,
                                    response_time=(time.time() - start_time) * 1000,
                                    additional_context={
                                        "chunk_preview": (
                                            chunk if chunk else "No chunk data"
                                        ),
                                        "api_path": self.config.api_path,
                                        "request_name": request_name,
                                    },
                                )
                                return "", "", usage
                            # Normal end of stream, break the loop
                            break

                    # Fire completion events for streaming
                    try:
                        current_time = time.time()
                        total_time = (
                            (current_time - actual_start_time) * 1000
                            if actual_start_time is not None and actual_start_time > 0
                            else 0
                        )

                        completion_time = 0
                        if (
                            metrics.first_token_received
                            and metrics.first_output_token_time is not None
                            and metrics.first_output_token_time > 0
                        ):
                            completion_time = (
                                current_time - metrics.first_output_token_time
                            ) * 1000
                        EventManager.fire_metric_event(METRIC_TTOC, completion_time, 0)
                        EventManager.fire_metric_event(METRIC_TTT, total_time, 0)
                        response.success()

                        except Exception as e:
                            self.task_logger.error(
                                f"Error calculating streaming metrics: {e}"
                            )
                            response.success()  # Still mark as success since we got response

                except OSError as e:
                    self.error_handler._handle_stream_error(
                        e, response, start_time, request_name
                    )
                    return "", "", usage
                except (orjson.JSONDecodeError, ValueError) as e:
                    response_time = (time.time() - start_time) * 1000
                    self.error_handler._handle_general_exception_event(
                        error_msg=f"Stream data parsing error: {e}",
                        response=response,
                        response_time=response_time,
                        additional_context={
                            "api_path": self.config.api_path,
                            "request_name": request_name,
                        },
                    )
                    return "", "", usage
        except (ConnectionError, TimeoutError) as e:
            response_time = (time.time() - start_time) * 1000
            self.error_handler._handle_general_exception_event(
                error_msg=f"Connection error: {e}",
                response=response,
                response_time=response_time,
                additional_context={
                    "api_path": self.config.api_path,
                    "request_name": request_name,
                },
            )
            has_failed = True
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.task_logger.error(f"Stream processing error: {e}")
            self.error_handler._handle_general_exception_event(
                error_msg=f"Unexpected error: {e}",
                response=response,
                response_time=response_time,
                additional_context={
                    "api_path": self.config.api_path,
                    "request_name": request_name,
                },
            )
            has_failed = True

        return metrics.reasoning_content, metrics.model_output

    def handle_non_stream_request(
        self, client, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str, Dict[str, Optional[int]]]:
        """Handle non-streaming API request."""

        json_payload = base_request_kwargs.get("json", {})
        if isinstance(json_payload, dict) and json_payload.get("stream") is True:
            error_msg = (
                "Payload contains 'stream': true, but task is configured for non-streaming mode (stream_mode=False). "
                "Please either set stream_mode=True in task config, or remove 'stream' field from payload."
            )
            self.task_logger.error(error_msg)
            response_time = (time.time() - start_time) * 1000
            self.error_handler._handle_general_exception_event(
                error_msg=error_msg,
                response=None,
                response_time=response_time,
                additional_context={
                    "api_path": self.config.api_path,
                    "request_name": base_request_kwargs.get(
                        "name", "non_stream_mismatch"
                    ),
                },
            )
            return (
                "",
                "",
                {
                    "completion_tokens": None,
                    "total_tokens": None,
                },
            )
        self.task_logger.info(f"base_request_kwargs: {base_request_kwargs}")

        request_kwargs = {**base_request_kwargs, "stream": False}
        model_output, reasoning_content = "", ""
        field_mapping = ConfigManager.parse_field_mapping(
            self.config.field_mapping or ""
        )
        request_name = base_request_kwargs.get("name", "failure")
        usage_tokens: Dict[str, Optional[int]] = {
            "completion_tokens": None,
            "total_tokens": None,
        }

        has_failed = False
        try:
            with client.post(self.config.api_path, **request_kwargs) as response:
                total_time = (time.time() - start_time) * 1000

                if self.error_handler._handle_status_code_error(
                    response, start_time, request_name
                ):
                    return "", "", usage

                try:
                    resp_json = response.json()
                    # self.task_logger.info(f"resp_json: {resp_json}")
                except (orjson.JSONDecodeError, KeyError) as e:
                    self.task_logger.error(f"Failed to parse response JSON: {e}")
                    self.error_handler._handle_general_exception_event(
                        error_msg=str(e),
                        response=response,
                        response_time=total_time,
                        additional_context={
                            "api_path": self.config.api_path,
                            "request_name": request_name,
                        },
                    )
                    return "", "", usage

                error_msg = ErrorResponse._handle_json_error(resp_json)
                if error_msg:
                    self.error_handler._handle_general_exception_event(
                        error_msg=error_msg,
                        response=response,
                        response_time=total_time,
                        additional_context={
                            "response_preview": (
                                str(resp_json) if resp_json else "No response data"
                            ),
                            "api_path": self.config.api_path,
                            "request_name": request_name,
                        },
                    )
                    return "", "", usage

                EventManager.fire_metric_event(
                    METRIC_TTT,
                    total_time,
                    0,
                )

                # Extract token counts from usage field if available
                if "usage" in resp_json and isinstance(resp_json["usage"], dict):
                    usage = resp_json["usage"]
                self.task_logger.debug(f"usage: {usage}")

                if usage["total_tokens"] is None:
                    content = (
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

                    # Extract token counts from usage field if available
                    if "usage" in resp_json and isinstance(resp_json["usage"], dict):
                        usage = resp_json["usage"]
                        # Look for completion tokens
                        for key, value in usage.items():
                            if "completion" in key.lower() and isinstance(
                                value, (int, float)
                            ):
                                usage_tokens["completion_tokens"] = int(value)
                                break
                        # Look for total tokens
                        for key, value in usage.items():
                            if "total" in key.lower() and isinstance(
                                value, (int, float)
                            ):
                                usage_tokens["total_tokens"] = int(value)
                                break

                    # Only mark as success if no failures occurred
                    if not has_failed:
                        try:
                            # Ensure output fields are not None before calling len()
                            model_output_len = (
                                len(model_output) if model_output is not None else 0
                            )
                            reasoning_content_len = (
                                len(reasoning_content)
                                if reasoning_content is not None
                                else 0
                            )

                            EventManager.fire_metric_event(
                                METRIC_TTT,
                                total_time,
                                model_output_len + reasoning_content_len,
                            )
                            response.success()
                        except Exception as e:
                            self.task_logger.error(
                                f"Error calculating non-streaming metrics: {e}"
                            )
                            response.success()  # Still mark as success since we got response

                except (json.JSONDecodeError, KeyError) as e:
                    self.task_logger.error(f"Failed to parse response JSON: {e}")
                    ErrorHandler.handle_general_exception(
                        str(e), self.task_logger, response, total_time
                    )
                    has_failed = True

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.error_handler._handle_general_exception_event(
                error_msg=f"Unexpected error: {e}",
                response=response,
                response_time=response_time,
                additional_context={
                    "api_path": self.config.api_path,
                    "request_name": request_name,
                },
            )
            return "", "", usage
