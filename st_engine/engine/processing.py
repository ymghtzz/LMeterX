"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Stream processing and error handling for the stress testing engine.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import orjson
from locust import events

from config.base import (
    DEFAULT_API_PATH,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    HTTP_OK,
)
from config.business import METRIC_TTOC, METRIC_TTT
from engine.core import ConfigManager, FieldMapping, GlobalConfig, StreamMetrics
from utils.logger import logger


# === ERROR HANDLING ===
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
            event_error = json_data.get("event", "")

            # API-specific error checks
            error_details = json_data.get("error", {})
            if isinstance(error_details, dict):
                error_type = error_details.get("type", "")
                error_message = error_details.get("message", "")
                if error_type or error_message:
                    return f"API error - type: {error_type}, message: {error_message}"

            if code < 0:
                return f"Response contains error code: {json_data}"

            if error and str(error).strip():
                return f"Response contains error: {json_data}"

            if output_object == "error":
                return f"Response object type is error: {json_data}"

            if event_error == "error":
                return f"Response event type is error: {json_data}"

            return None
        except Exception as e:
            # Enhanced logging for parsing errors
            return f"Error parsing response JSON for error checking: {e}"

    @staticmethod
    def handle_general_exception(
        error_msg: str,
        task_logger,
        response=None,
        response_time: float = 0,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Centralized handler for logging exceptions during requests."""
        # Enhanced error logging with context
        context_info = ""
        if additional_context:
            context_info = f" | Context: {additional_context}"

        full_error_msg = f"{error_msg}{context_info}"
        task_logger.error(full_error_msg)

        try:
            EventManager.fire_failure_event(
                name="failure",
                response_time=response_time,
                response_length=0,
                exception=Exception(full_error_msg),
            )
        except Exception as fire_err:
            # Never let event firing escalate; log and continue
            task_logger.warning(f"Failed to emit failure event: {fire_err}")


# === EVENT MANAGEMENT ===
class EventManager:
    """Manages Locust events and metrics."""

    @staticmethod
    def fire_failure_event(
        name: str = "failure",
        response_time: float = 0.0,
        response_length: int = 0,
        exception: Optional[Exception] = None,
    ) -> None:
        """Fire failure events with proper Locust event format."""
        # Enhanced safety checks for all parameters
        try:
            response_time = (
                float(response_time)
                if isinstance(response_time, (int, float)) and response_time >= 0
                else 0.0
            )
        except Exception:
            response_time = 0.0

        try:
            response_length = (
                int(response_length)
                if isinstance(response_length, (int, float)) and response_length >= 0
                else 0
            )
        except Exception:
            response_length = 0

        exception_info = exception or Exception("Request failed")

        try:
            # Use the correct Locust event API based on version
            if hasattr(events, "request_failure"):
                # Legacy Locust version
                events.request_failure.fire(
                    request_type="POST",
                    name=name,
                    response_time=int(response_time),
                    response_length=int(response_length),
                    exception=exception_info,
                )
            else:
                # Modern Locust version
                events.request.fire(
                    request_type="POST",
                    name=name,
                    response_time=int(response_time),
                    response_length=int(response_length),
                    exception=exception_info,
                    success=False,
                )
        except Exception as e:
            # Never crash on metrics emission
            logger.warning(f"Failed to fire failure event: {e}")

    @staticmethod
    def fire_metric_event(
        name: str, response_time: float, response_length: int
    ) -> None:
        """Fire metric events."""
        # Enhanced safety checks for all parameters
        try:
            response_time = (
                float(response_time)
                if isinstance(response_time, (int, float)) and response_time >= 0
                else 0.0
            )
        except Exception:
            response_time = 0.0

        try:
            response_length = (
                int(response_length)
                if isinstance(response_length, (int, float)) and response_length >= 0
                else 0
            )
        except Exception:
            response_length = 0

        name = str(name) if name is not None else "metric"

        try:
            # Use the correct Locust event API based on version
            if hasattr(events, "request_success"):
                # Legacy Locust version
                events.request_success.fire(
                    request_type="metric",
                    name=name,
                    response_time=int(response_time),
                    response_length=int(response_length),
                )
            else:
                # Modern Locust version
                events.request.fire(
                    request_type="metric",
                    name=name,
                    response_time=int(response_time),
                    response_length=int(response_length),
                    success=True,
                )
        except Exception as e:
            logger.warning(f"Failed to fire metric event '{name}': {e}")


# === STREAM PROCESSING ===
class StreamProcessor:
    """Handles streaming response processing."""

    @staticmethod
    def get_field_value(data: Dict[str, Any], path: str) -> Any:
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

            # Return the actual value, preserve original type
            if current is None:
                return ""
            return current
        except (KeyError, IndexError, TypeError, ValueError):
            return ""

    @staticmethod
    def remove_chunk_prefix(chunk_str: str, field_mapping: FieldMapping) -> str:
        """Remove prefix from chunk string based on field mapping configuration."""
        if field_mapping.end_prefix:
            return chunk_str.replace(field_mapping.end_prefix, "").strip()
        elif field_mapping.stream_prefix and chunk_str.startswith(
            field_mapping.stream_prefix
        ):
            return chunk_str[len(field_mapping.stream_prefix) :].strip()
        else:
            return chunk_str.strip()

    @staticmethod
    def check_stop_flag(processed_chunk: str, field_mapping: FieldMapping) -> bool:
        """Check if the processed chunk matches the stop flag."""
        stop_flag = (
            field_mapping.stop_flag.strip() if field_mapping.stop_flag else "[DONE]"
        )
        return processed_chunk == stop_flag

    @staticmethod
    def check_end_field_stop(
        processed_chunk: Dict[str, Any], field_mapping: FieldMapping
    ) -> bool:
        """Check if end_field value matches stop flag."""
        if not field_mapping.end_field:
            return False

        stop_flag = (
            field_mapping.stop_flag.strip() if field_mapping.stop_flag else "[DONE]"
        )
        end_value = StreamProcessor.get_field_value(
            processed_chunk, field_mapping.end_field
        )
        # Convert to string for comparison
        end_value = str(end_value) if end_value else ""
        return end_value == stop_flag

    @staticmethod
    def extract_metrics_from_chunk(
        chunk_data: Dict[str, Any],
        field_mapping: FieldMapping,
        metrics: StreamMetrics,
        start_time: float,
        task_logger,
    ) -> StreamMetrics:
        """Extract and update metrics from chunk data."""
        # Extract usage tokens
        usage_extracted = False
        if field_mapping.usage:
            metrics.usage = StreamProcessor.get_field_value(
                chunk_data, field_mapping.usage
            )

            if metrics.usage and isinstance(metrics.usage, dict):
                has_completion_tokens = any(
                    "completion" in key and value not in (None, 0)
                    for key, value in metrics.usage.items()
                    if isinstance(value, (int, float))
                )

                has_total_tokens = any(
                    "total" in key and value not in (None, 0)
                    for key, value in metrics.usage.items()
                    if isinstance(value, (int, float))
                )
                if has_completion_tokens and has_total_tokens:
                    usage_extracted = True

        # Extract content
        if field_mapping.content:
            content_chunk = StreamProcessor.get_field_value(
                chunk_data, field_mapping.content
            )
            # Convert to string for content fields
            content_chunk = str(content_chunk) if content_chunk else ""
            if (
                content_chunk
                and isinstance(content_chunk, str)
                and content_chunk.strip()
            ):

                if not metrics.first_token_received:
                    metrics.first_token_received = True
                    metrics.first_output_token_time = time.time()
                    if start_time > 0 and metrics.first_output_token_time:
                        ttfot = (metrics.first_output_token_time - start_time) * 1000
                        EventManager.fire_metric_event(
                            "Time_to_first_output_token", ttfot, 0
                        )
                if not usage_extracted:
                    metrics.content += content_chunk

        # Extract reasoning content
        if field_mapping.reasoning_content:
            reasoning_chunk = StreamProcessor.get_field_value(
                chunk_data, field_mapping.reasoning_content
            )
            # Convert to string for reasoning content fields
            reasoning_chunk = str(reasoning_chunk) if reasoning_chunk else ""
            if (
                reasoning_chunk
                and isinstance(reasoning_chunk, str)
                and reasoning_chunk.strip()
            ):

                if not metrics.reasoning_is_active:
                    metrics.reasoning_is_active = True
                if not metrics.first_thinking_received:
                    metrics.first_thinking_received = True
                    metrics.first_thinking_token_time = time.time()
                    if start_time > 0 and metrics.first_thinking_token_time:
                        ttfrt = (metrics.first_thinking_token_time - start_time) * 1000
                        EventManager.fire_metric_event(
                            "Time_to_first_reasoning_token", ttfrt, 0
                        )
                if not usage_extracted:
                    metrics.reasoning_content += reasoning_chunk

            elif (
                metrics.reasoning_is_active
                and not reasoning_chunk
                and not metrics.reasoning_ended
                and field_mapping.content  # Only if we have content in this chunk
            ):
                content_chunk = StreamProcessor.get_field_value(
                    chunk_data, field_mapping.content
                )
                # Convert to string for content check
                content_chunk = str(content_chunk) if content_chunk else ""
                if (
                    content_chunk
                    and metrics.first_thinking_received
                    and metrics.first_thinking_token_time
                ):
                    metrics.reasoning_ended = True
                    current_time = time.time()
                    ttrc = (current_time - metrics.first_thinking_token_time) * 1000
                    EventManager.fire_metric_event(
                        "Time_to_reasoning_completion", ttrc, 0
                    )

        return metrics

    @staticmethod
    def process_stream_chunk(
        chunk: bytes,
        field_mapping: FieldMapping,
        start_time: float,
        metrics: StreamMetrics,
        task_logger,
    ) -> Tuple[bool, Optional[str], StreamMetrics]:
        """
        Process a single stream chunk according to the specified logic.

        Returns:
            (should_break, error_message, updated_metrics)
            - should_break: True if should exit the stream loop
            - error_message: Error message if there's an error, None otherwise
            - updated_metrics: Updated metrics object
        """
        if not chunk:
            return False, None, metrics

        try:
            chunk_str = chunk.decode("utf-8", errors="replace").strip()
        except UnicodeDecodeError as e:
            task_logger.warning(f"Failed to decode chunk: {e}")
            return False, None, metrics

        if not chunk_str:
            return False, None, metrics

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
            error_msg = ErrorHandler.check_json_error(chunk_data)
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
class RequestHandler:
    """Handles different types of API requests."""

    def __init__(self, config: GlobalConfig, task_logger) -> None:
        """Initialize the RequestHandler with configuration and logger.

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
                payload = orjson.loads(str(self.config.request_payload))
            except orjson.JSONDecodeError as e:
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
                # Removed "verify": False and timeout, these are not valid for FastHttpUser
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
                prompt_value = StreamProcessor.get_field_value(
                    payload, field_mapping.prompt
                )
                return str(prompt_value) if prompt_value else ""
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
class StreamHandler:
    """Handles streaming and non-streaming request processing."""

    def __init__(self, config: GlobalConfig, task_logger) -> None:
        """Initialize the StreamHandler with configuration and logger.

        Args:
            config: Global configuration object
            task_logger: Task-specific logger instance
        """
        self.config = config
        self.task_logger = task_logger

    @staticmethod
    def _iter_stream_lines(response) -> Any:
        """Yield complete SSE lines using \n\n as delimiter."""
        # Case 1: requests.Response with iter_lines
        if hasattr(response, "iter_lines") and callable(response.iter_lines):
            for line in response.iter_lines():
                if line:
                    yield (
                        line
                        if isinstance(line, (bytes, bytearray))
                        else str(line).encode("utf-8", errors="ignore")
                    )
            return

        # Case 2: FastHttp-like response with stream
        stream_obj = getattr(response, "stream", None)
        if stream_obj is not None:
            buffer = b""
            try:
                while True:
                    chunk = stream_obj.read(8192)
                    if not chunk:
                        break
                    buffer += chunk

                    # Process all complete data blocks (delimited by \n\n)
                    while b"\n\n" in buffer:
                        part, buffer = buffer.split(b"\n\n", 1)
                        part = part.strip()
                        if not part:
                            continue

                        if part.startswith(b"data:"):
                            data_content = part[5:].strip()  # 去掉 'data:'
                            if data_content != b"[DONE]":
                                yield data_content

                if buffer.strip():
                    buffer = buffer.strip()
                    if buffer == b"[DONE]" or buffer.startswith(b"data:"):
                        data_content = (
                            buffer[5:].strip()
                            if buffer.startswith(b"data:")
                            else buffer
                        )
                        yield data_content

            except Exception as e:
                if buffer.strip():
                    yield buffer.strip()
                raise e
            return

        # Case 3: Fallback to .text
        text = getattr(response, "text", "") or ""
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    yield data.encode("utf-8", errors="ignore")

    @staticmethod
    def _iter_stream_lines_old(response) -> Any:
        """Yield response lines as bytes for both requests and FastHttp responses."""
        # Case 1: requests.Response with iter_lines
        if hasattr(response, "iter_lines") and callable(response.iter_lines):
            for line in response.iter_lines():
                if line is not None:
                    yield (
                        line
                        if isinstance(line, (bytes, bytearray))
                        else str(line).encode("utf-8", errors="ignore")
                    )
            return

        # Case 2: FastHttp-like response with stream
        stream_obj = getattr(response, "stream", None)
        if stream_obj is not None:
            buffer = b""
            try:
                while True:
                    chunk = stream_obj.read(8192)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if line:
                            yield line.strip()
            except Exception:
                if buffer:
                    yield buffer.strip()
            return

        # Case 3: Fallback to .text
        text = getattr(response, "text", "") or ""
        for part in text.splitlines():
            part = part.strip()
            if part:
                yield part.encode("utf-8", errors="ignore")

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
        actual_start_time = 0.0
        request_name = base_request_kwargs.get("name", "failure")
        usage: Dict[str, Optional[int]] = {
            "completion_tokens": None,
            "total_tokens": None,
        }

        try:
            actual_start_time = time.time()
            with client.post(self.config.api_path, **request_kwargs) as response:
                if self._handle_response_error(response, start_time, request_name):
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
                                ErrorHandler.handle_general_exception(
                                    error_message,
                                    self.task_logger,
                                    response,
                                    (time.time() - start_time) * 1000,
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

                        EventManager.fire_metric_event(
                            METRIC_TTOC,
                            completion_time,
                            0,
                        )
                        EventManager.fire_metric_event(METRIC_TTT, total_time, 0)
                        response.success()

                    except Exception as e:
                        self.task_logger.error(
                            f"Error calculating streaming metrics: {e}"
                        )
                        response.success()  # Still mark as success since we got response

                except OSError as e:
                    self._handle_stream_error(e, response, start_time, request_name)
                    return "", "", usage
                except (orjson.JSONDecodeError, ValueError) as e:
                    response_time = (time.time() - start_time) * 1000
                    ErrorHandler.handle_general_exception(
                        f"Stream data parsing error: {e}",
                        self.task_logger,
                        response,
                        response_time,
                    )
                    return "", "", usage
        except (ConnectionError, TimeoutError) as e:
            response_time = (time.time() - start_time) * 1000
            ErrorHandler.handle_general_exception(
                f"Connection error: {e}",
                self.task_logger,
                response,
                response_time,
                additional_context={
                    "api_path": self.config.api_path,
                    "request_name": request_name,
                },
            )
            return "", "", usage
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            ErrorHandler.handle_general_exception(
                f"Unexpected error: {e}",
                self.task_logger,
                response,
                response_time,
                additional_context={
                    "api_path": self.config.api_path,
                    "request_name": request_name,
                },
            )
            return "", "", usage
        return metrics.reasoning_content, metrics.content, metrics.usage

    def _handle_stream_error(
        self, e: OSError, response, start_time: float, request_name: str
    ) -> None:
        """Handle specific stream processing errors."""
        error_details = str(e)
        response_time = (time.time() - start_time) * 1000

        if "Read timed out" in error_details:
            self.task_logger.error(
                f"Stream request timeout (current timeout: {DEFAULT_TIMEOUT} seconds): {error_details}."
            )
        elif "Connection" in error_details:
            self.task_logger.error(f"Network connection error: {error_details}.")
        else:
            self.task_logger.error(f"Stream processing network error: {error_details}")

        ErrorHandler.handle_general_exception(
            error_details,
            self.task_logger,
            response,
            response_time,
            additional_context={
                "api_path": self.config.api_path,
                "request_name": request_name,
            },
        )

    def handle_non_stream_request(
        self, client, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str, Dict[str, Optional[int]]]:
        """Handle non-streaming API request."""
        request_kwargs = {**base_request_kwargs, "stream": False}
        content, reasoning_content = "", ""
        field_mapping = ConfigManager.parse_field_mapping(
            self.config.field_mapping or ""
        )
        request_name = base_request_kwargs.get("name", "failure")
        usage: Dict[str, Optional[int]] = {
            "completion_tokens": None,
            "total_tokens": None,
        }

        try:
            with client.post(self.config.api_path, **request_kwargs) as response:
                total_time = (time.time() - start_time) * 1000

                if self._handle_response_error(response, start_time, request_name):
                    return "", "", usage

                try:
                    resp_json = response.json()
                    # self.task_logger.info(f"resp_json: {resp_json}")
                except (orjson.JSONDecodeError, KeyError) as e:
                    self.task_logger.error(f"Failed to parse response JSON: {e}")
                    ErrorHandler.handle_general_exception(
                        str(e), self.task_logger, response, total_time
                    )
                    return "", "", usage

                error_msg = ErrorHandler.check_json_error(resp_json)
                if error_msg:
                    ErrorHandler.handle_general_exception(
                        error_msg,
                        self.task_logger,
                        response,
                        total_time,
                        additional_context={
                            "response_preview": (
                                str(resp_json)[:200]
                                if resp_json
                                else "No response data"
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
                    content = str(content) if content else ""

                    reasoning_content = (
                        StreamProcessor.get_field_value(
                            resp_json, field_mapping.reasoning_content
                        )
                        if field_mapping.reasoning_content
                        else ""
                    )
                    reasoning_content = (
                        str(reasoning_content) if reasoning_content else ""
                    )
                response.success()
                return reasoning_content, content, usage

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            ErrorHandler.handle_general_exception(
                str(e),
                self.task_logger,
                response,
                total_time,
                additional_context={
                    "api_path": self.config.api_path,
                    "request_name": request_name,
                },
            )
            return "", "", usage

    def _handle_response_error(
        self, response, start_time: float = 0, request_name: str = "failure"
    ) -> bool:
        """Handle HTTP status code errors."""
        # Add safety checks for response object
        if response is None:
            error_msg = "Response object is None"
            response_time = (time.time() - start_time) * 1000 if start_time > 0 else 0
            ErrorHandler.handle_general_exception(
                error_msg, self.task_logger, None, response_time
            )
            return True

        # Safely get status code with fallback
        try:
            status_code = getattr(response, "status_code", None)
            if status_code is None:
                error_msg = "Response object has no status_code attribute"
                response_time = (
                    (time.time() - start_time) * 1000 if start_time > 0 else 0
                )
                ErrorHandler.handle_general_exception(
                    error_msg, self.task_logger, response, response_time
                )
                return True

            if status_code != HTTP_OK:
                # Safely get response text
                response_text = getattr(
                    response, "text", "Unable to retrieve response text"
                )
                error_msg = f"Request failed with status {status_code}. Response: {response_text}"
                response_time = (
                    (time.time() - start_time) * 1000 if start_time > 0 else 0
                )
                ErrorHandler.handle_general_exception(
                    error_msg, self.task_logger, response, response_time
                )
                return True
        except Exception as e:
            error_msg = f"Error checking response status: {e}"
            response_time = (time.time() - start_time) * 1000 if start_time > 0 else 0
            ErrorHandler.handle_general_exception(
                error_msg,
                self.task_logger,
                response,
                response_time,
                additional_context={
                    "api_path": self.config.api_path,
                    "request_name": request_name,
                },
            )
            return True

        return False
