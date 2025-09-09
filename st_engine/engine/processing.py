"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Stream processing and error handling for the stress testing engine.
"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from locust import events

from config.base import (
    DEFAULT_API_PATH,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    HTTP_OK,
    JSON_BUFFER_MAX_SIZE,
    MAX_OUTPUT_LENGTH,
    MULTIPROCESS_CHUNK_TIMEOUT_THRESHOLD,
    MULTIPROCESS_MAX_RETRIES,
    MULTIPROCESS_RETRY_DELAY_MAX,
    STREAM_ADAPTIVE_TIMEOUT_ENABLED,
    STREAM_BUFFER_SIZE,
    STREAM_CHUNK_TIMEOUT_THRESHOLD,
    STREAM_DEBUG_ENABLED,
    STREAM_MAX_RETRIES,
    STREAM_RETRY_DELAY_BASE,
    STREAM_RETRY_DELAY_MAX,
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

            # Check for HTTP error status in response - with proper type checking
            # if "status" in json_data:
            #     status_value = json_data["status"]
            #     # Handle both string and integer status values
            #     if isinstance(status_value, str):
            #         # For string status, check if it indicates an error
            #         if status_value.lower() not in ["ok", "success", "completed"]:
            #             return f"HTTP error status: {status_value}"
            #     elif isinstance(status_value, (int, float)):
            #         # For numeric status, check if it's not 200
            #         if int(status_value) != 200:
            #             return f"HTTP error status: {status_value}"

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

                # Extract usage information if present
                if "usage" in chunk_data and isinstance(chunk_data["usage"], dict):
                    usage = chunk_data["usage"]
                    usage_tokens: Dict[str, Optional[int]] = {
                        "prompt_tokens": None,
                        "completion_tokens": None,
                        "total_tokens": None,
                    }

                    # Extract token counts with flexible field names
                    for key, value in usage.items():
                        if isinstance(value, (int, float)):
                            if "prompt" in key.lower():
                                usage_tokens["prompt_tokens"] = int(value)
                            elif "completion" in key.lower():
                                usage_tokens["completion_tokens"] = int(value)
                            elif "total" in key.lower():
                                usage_tokens["total_tokens"] = int(value)

                    # Update metrics with usage information (overwrite with latest)
                    metrics.usage_tokens = usage_tokens
                    task_logger.debug(
                        f"Updated usage tokens from stream: {usage_tokens}"
                    )

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

        except (json.JSONDecodeError, IndexError, KeyError) as e:
            # Improved error handling - don't crash on parse errors, just log and continue
            task_logger.debug(
                f"Chunk processing error (continuing): {e} | Chunk: {chunk_str[:100]}..."
            )
            # Don't fire failure events for parsing errors as they may be incomplete chunks
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
        """Check streaming chunk for errors with improved JSON handling."""
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
                    error_result = ErrorHandler.check_json_error(chunk_json)
                    return error_result
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    # Improved error logging with better context
                    task_logger.debug(
                        f"JSON parsing failed (likely incomplete chunk): {e} | "
                        f"Chunk preview: {chunk_content[:200] if chunk_content else 'No content'}..."
                    )
                    # Don't treat JSON parsing errors as fatal - they might be incomplete chunks
                    return None

            return None

        except Exception as e:
            task_logger.warning(f"Unexpected error checking chunk for errors: {e}")
            return None


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
        self._is_multiprocess = self._detect_multiprocess_environment()
        self._adaptive_config = self._get_adaptive_config()

    def _detect_multiprocess_environment(self) -> bool:
        """Detect if running in multi-process environment."""
        try:
            import os

            # Check environment variables that indicate multi-process mode
            if os.environ.get("LOCUST_PROCESSES"):
                return True

            # Check if there are multiple Python processes with similar command lines
            import psutil

            current_pid = os.getpid()
            current_cmdline = " ".join(psutil.Process(current_pid).cmdline())

            locust_processes = 0
            for proc in psutil.process_iter(["pid", "cmdline"]):
                try:
                    if (
                        proc.info["cmdline"]
                        and "locust" in " ".join(proc.info["cmdline"]).lower()
                    ):
                        locust_processes += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return locust_processes > 1
        except Exception:
            # If detection fails, assume single process for safety
            return False

    @staticmethod
    def _detect_multiprocess_static() -> bool:
        """Static method to detect if running in multi-process environment."""
        try:
            import os

            # Check environment variables that indicate multi-process mode
            if os.environ.get("LOCUST_PROCESSES"):
                return True

            # Simple heuristic: check for multiple locust processes
            try:
                import psutil

                locust_processes = 0
                for proc in psutil.process_iter(["cmdline"]):
                    try:
                        cmdline = proc.info["cmdline"]
                        if cmdline and any(
                            "locust" in str(arg).lower() for arg in cmdline
                        ):
                            locust_processes += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                return locust_processes > 1
            except ImportError:
                # psutil not available, use fallback
                return False
        except Exception:
            return False

    def _get_adaptive_config(self) -> Dict[str, Any]:
        """Get adaptive configuration based on environment."""
        if not STREAM_ADAPTIVE_TIMEOUT_ENABLED:
            return {
                "max_retries": STREAM_MAX_RETRIES,
                "timeout_threshold": STREAM_CHUNK_TIMEOUT_THRESHOLD,
                "retry_delay_max": STREAM_RETRY_DELAY_MAX,
            }

        if self._is_multiprocess:
            self.task_logger.debug(
                "Multi-process environment detected, using extended timeouts"
            )
            return {
                "max_retries": MULTIPROCESS_MAX_RETRIES,
                "timeout_threshold": MULTIPROCESS_CHUNK_TIMEOUT_THRESHOLD,
                "retry_delay_max": MULTIPROCESS_RETRY_DELAY_MAX,
            }
        else:
            return {
                "max_retries": STREAM_MAX_RETRIES,
                "timeout_threshold": STREAM_CHUNK_TIMEOUT_THRESHOLD,
                "retry_delay_max": STREAM_RETRY_DELAY_MAX,
            }

    @staticmethod
    def _iter_stream_lines(response) -> Any:
        """Yield response lines as bytes for both requests and FastHttp responses."""
        # requests.Response has iter_lines
        if hasattr(response, "iter_lines") and callable(response.iter_lines):
            for line in response.iter_lines():
                if line is None:
                    continue
                yield (
                    line
                    if isinstance(line, (bytes, bytearray))
                    else str(line).encode("utf-8", errors="ignore")
                )
            return

        # FastHttp's Response has a `stream` file-like
        stream_obj = getattr(response, "stream", None)
        if stream_obj is None:
            # Fallback: no streaming iterator available
            text = getattr(response, "text", "") or ""
            if text:
                for part in text.split("\n"):
                    yield part.encode("utf-8", errors="ignore")
            return

        buffer = b""
        try:
            while True:
                chunk = stream_obj.read(1024)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line:
                        yield line.strip()
        except Exception:
            # Best-effort: flush remaining buffer
            if buffer:
                yield buffer.strip()

    @staticmethod
    def _iter_stream_chunks_with_json_buffer(
        response, field_mapping: FieldMapping, task_logger
    ) -> Any:
        """Improved streaming iterator with JSON buffer handling for SSE streams."""

        class JsonBufferManager:
            def __init__(self):
                self.buffer = ""
                self.stats = {
                    "incomplete_chunks": 0,
                    "buffer_overflows": 0,
                    "successful_parses": 0,
                }

            def process_sse_line(self, line_str: str) -> Any:
                """Process a single SSE line and manage JSON buffer with enhanced error handling."""
                if not line_str:
                    return

                # Handle SSE data lines
                if line_str.startswith(field_mapping.stream_prefix):
                    json_content = line_str[len(field_mapping.stream_prefix) :].strip()

                    # Check for stop condition
                    if json_content == field_mapping.stop_flag:
                        yield json_content.encode("utf-8", errors="ignore")
                        return

                    # Try to parse as complete JSON first
                    if json_content and field_mapping.data_format == "json":
                        if StreamHandler._is_complete_json(json_content):
                            # Complete JSON found, flush any previous buffer and yield this
                            if self.buffer.strip() and StreamHandler._is_complete_json(
                                self.buffer
                            ):
                                self.stats["successful_parses"] += 1
                                yield self.buffer.encode("utf-8", errors="ignore")
                            self.buffer = ""
                            self.stats["successful_parses"] += 1
                            yield json_content.encode("utf-8", errors="ignore")
                        else:
                            # Incomplete JSON, add to buffer with size check
                            if (
                                len(self.buffer) + len(json_content)
                                > JSON_BUFFER_MAX_SIZE
                            ):
                                # Buffer overflow protection
                                self.stats["buffer_overflows"] += 1
                                if STREAM_DEBUG_ENABLED:
                                    task_logger.warning(
                                        f"JSON buffer overflow, discarding old data. Stats: {self.stats}"
                                    )
                                self.buffer = (
                                    json_content  # Start fresh with current content
                                )
                            else:
                                self.buffer += json_content

                            self.stats["incomplete_chunks"] += 1

                            # Check if buffer now contains complete JSON
                            if StreamHandler._is_complete_json(self.buffer):
                                self.stats["successful_parses"] += 1
                                yield self.buffer.encode("utf-8", errors="ignore")
                                self.buffer = ""
                    else:
                        # Non-JSON data or empty content
                        yield json_content.encode("utf-8", errors="ignore")
                else:
                    # Non-data lines (like event types), yield as-is
                    yield line_str.encode("utf-8", errors="ignore")

            def flush_remaining(self) -> Any:
                """Flush any remaining complete JSON in buffer."""
                if self.buffer.strip() and StreamHandler._is_complete_json(self.buffer):
                    self.stats["successful_parses"] += 1
                    yield self.buffer.encode("utf-8", errors="ignore")
                elif self.buffer.strip():
                    # Log incomplete JSON for debugging but don't crash
                    if STREAM_DEBUG_ENABLED:
                        task_logger.debug(
                            f"Discarding incomplete JSON buffer (length: {len(self.buffer)}): {self.buffer[:100]}..."
                        )
                        task_logger.debug(f"Buffer manager stats: {self.stats}")
                    else:
                        task_logger.debug(
                            f"Discarding incomplete JSON buffer (length: {len(self.buffer)})"
                        )

        buffer_manager = JsonBufferManager()

        # Handle requests.Response with iter_lines
        if hasattr(response, "iter_lines") and callable(response.iter_lines):
            for line in response.iter_lines():
                if line is None:
                    continue

                try:
                    line_str = (
                        line.decode("utf-8", errors="replace")
                        if isinstance(line, bytes)
                        else str(line)
                    )
                    yield from buffer_manager.process_sse_line(line_str)
                except Exception as e:
                    task_logger.warning(f"Error processing SSE line: {e}")
                    continue

            # Flush any remaining complete JSON in buffer
            yield from buffer_manager.flush_remaining()
            return

        # Handle FastHttp's Response with stream attribute
        stream_obj = getattr(response, "stream", None)
        if stream_obj is None:
            # Fallback: no streaming iterator available
            text = getattr(response, "text", "") or ""
            if text:
                for part in text.split("\n"):
                    yield from buffer_manager.process_sse_line(part)

                # Flush any remaining complete JSON in buffer
                yield from buffer_manager.flush_remaining()
            return

        # Custom buffer handling for FastHttp stream with adaptive configuration
        buffer = b""
        retry_count = 0
        # Detect multi-process environment for adaptive configuration
        is_multiprocess = StreamHandler._detect_multiprocess_static()
        if is_multiprocess and STREAM_ADAPTIVE_TIMEOUT_ENABLED:
            max_retries = MULTIPROCESS_MAX_RETRIES
            timeout_threshold = MULTIPROCESS_CHUNK_TIMEOUT_THRESHOLD
            max_retry_delay = MULTIPROCESS_RETRY_DELAY_MAX
        else:
            max_retries = STREAM_MAX_RETRIES
            timeout_threshold = STREAM_CHUNK_TIMEOUT_THRESHOLD
            max_retry_delay = STREAM_RETRY_DELAY_MAX
        last_successful_chunk_time = time.time()

        try:
            while True:
                try:
                    chunk = stream_obj.read(STREAM_BUFFER_SIZE)
                    if not chunk:
                        # End of stream reached
                        break

                    # Reset retry count on successful read
                    retry_count = 0
                    last_successful_chunk_time = time.time()
                    buffer += chunk

                    # Process complete lines
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        if line:
                            try:
                                line_str = line.decode(
                                    "utf-8", errors="replace"
                                ).strip()
                                yield from buffer_manager.process_sse_line(line_str)
                            except Exception as e:
                                task_logger.debug(
                                    f"Error processing buffered line: {e}"
                                )
                                continue

                except Exception as read_error:
                    error_msg = str(read_error)
                    current_time = time.time()

                    # Check if this is a timeout or incomplete response
                    if (
                        "timed out" in error_msg.lower()
                        or "incomplete" in error_msg.lower()
                    ):
                        retry_count += 1

                        # Calculate how long since last successful chunk
                        time_since_last_chunk = (
                            current_time - last_successful_chunk_time
                        )

                        if (
                            retry_count <= max_retries
                            and time_since_last_chunk < timeout_threshold
                        ):
                            task_logger.debug(
                                f"Stream read error (attempt {retry_count}/{max_retries}): {error_msg}. "
                                f"Retrying after {retry_count}s delay..."
                            )

                            # Brief exponential backoff
                            time.sleep(
                                min(
                                    retry_count * STREAM_RETRY_DELAY_BASE,
                                    max_retry_delay,
                                )
                            )
                            continue
                        else:
                            # Max retries exceeded or timeout threshold reached
                            task_logger.warning(
                                f"Stream read failed after {retry_count} retries or timeout "
                                f"({time_since_last_chunk:.1f}s since last chunk): {error_msg}"
                            )
                            break
                    else:
                        # Non-retryable error
                        task_logger.warning(f"Non-retryable stream error: {error_msg}")
                        break

        except Exception as e:
            task_logger.warning(f"Error in stream iteration: {e}")
        finally:
            # Handle remaining data in buffers with enhanced processing
            if buffer:
                try:
                    remaining_str = buffer.decode("utf-8", errors="replace").strip()
                    if remaining_str:
                        # Try to process remaining data as complete lines
                        for line in remaining_str.split("\n"):
                            line = line.strip()
                            if line:
                                try:
                                    yield from buffer_manager.process_sse_line(line)
                                except Exception as e:
                                    task_logger.debug(
                                        f"Error processing remaining line: {e}"
                                    )
                except Exception as e:
                    task_logger.debug(f"Error processing remaining buffer: {e}")

            # Always flush remaining complete JSON in buffer
            try:
                yield from buffer_manager.flush_remaining()
            except Exception as e:
                task_logger.debug(f"Error flushing buffer manager: {e}")

    @staticmethod
    def _is_complete_json(json_str: str) -> bool:
        """Check if a string contains complete, valid JSON."""
        if not json_str or not json_str.strip():
            return False

        try:
            json.loads(json_str)
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    def handle_stream_request(
        self, client, base_request_kwargs: Dict[str, Any], start_time: float
    ) -> Tuple[str, str, Dict[str, Optional[int]]]:
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
        usage_tokens: Dict[str, Optional[int]] = {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }

        try:
            actual_request_start_time = time.time()
            with client.post(self.config.api_path, **request_kwargs) as response:
                if self._handle_response_error(response, start_time, request_name):
                    has_failed = True
                    return "", "", usage_tokens

                try:
                    # Process as streaming response with improved JSON buffering
                    chunks_processed = 0
                    last_valid_usage = None

                    for chunk in self._iter_stream_chunks_with_json_buffer(
                        response, field_mapping, self.task_logger
                    ):
                        chunks_processed += 1
                        # self.task_logger.info(f"chunk: {chunk}")
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
                                additional_context={
                                    "chunk_preview": (
                                        chunk[:100] if chunk else "No chunk data"
                                    ),
                                    "api_path": self.config.api_path,
                                    "request_name": request_name,
                                },
                            )
                            has_failed = True
                            # Fix: mark response as failed
                            if hasattr(response, "failure"):
                                response.failure(error_msg)
                            # Return partial results if available
                            if metrics.usage_tokens or last_valid_usage:
                                final_usage = (
                                    metrics.usage_tokens
                                    or last_valid_usage
                                    or usage_tokens
                                )
                                return (
                                    metrics.reasoning_content,
                                    metrics.model_output,
                                    final_usage,
                                )
                            return "", "", usage_tokens

                        old_usage = metrics.usage_tokens
                        metrics = StreamProcessor.process_chunk(
                            chunk,
                            field_mapping,
                            actual_request_start_time,
                            metrics,
                            self.task_logger,
                        )

                        # Keep track of the latest valid usage tokens
                        if metrics.usage_tokens:
                            last_valid_usage = metrics.usage_tokens
                        elif old_usage:
                            last_valid_usage = old_usage

                    self.task_logger.debug(
                        f"Processed {chunks_processed} chunks successfully"
                    )

                    # Use the best available usage information
                    final_usage_tokens = (
                        metrics.usage_tokens or last_valid_usage or usage_tokens
                    )

                    # Only mark as success if no failures occurred
                    if not has_failed:
                        # Fire completion events for streaming with enhanced safety checks
                        try:
                            current_time = time.time()
                            total_time = (
                                (current_time - start_time) * 1000
                                if start_time is not None and start_time > 0
                                else 0
                            )

                            completion_time = 0.0
                            if (
                                metrics.first_token_received
                                and metrics.first_output_token_time is not None
                                and metrics.first_output_token_time > 0
                            ):
                                completion_time = (
                                    current_time - metrics.first_output_token_time
                                ) * 1000

                            # Ensure metrics fields are not None before calling len()
                            model_output_len = (
                                len(metrics.model_output)
                                if metrics.model_output is not None
                                else 0
                            )
                            reasoning_content_len = (
                                len(metrics.reasoning_content)
                                if metrics.reasoning_content is not None
                                else 0
                            )

                            EventManager.fire_metric_event(
                                METRIC_TTOC,
                                completion_time,
                                model_output_len,
                            )
                            EventManager.fire_metric_event(
                                METRIC_TTT,
                                total_time,
                                model_output_len + reasoning_content_len,
                            )
                            response.success()

                        except Exception as e:
                            self.task_logger.error(
                                f"Error calculating streaming metrics: {e}"
                            )
                            response.success()  # Still mark as success since we got response
                    else:
                        # Mark as partial success if we have some data
                        if chunks_processed > 0 and (
                            metrics.model_output or metrics.reasoning_content
                        ):
                            self.task_logger.warning(
                                f"Partial stream processing success: {chunks_processed} chunks processed"
                            )
                            # Don't mark as complete failure if we got partial data
                            if hasattr(response, "success"):
                                response.success()

                except OSError as e:
                    self._handle_stream_error(e, response, start_time, request_name)
                    has_failed = True
                    # Return partial results if available
                    if metrics.usage_tokens:
                        return (
                            metrics.reasoning_content,
                            metrics.model_output,
                            metrics.usage_tokens,
                        )
                except (json.JSONDecodeError, ValueError) as e:
                    response_time = (time.time() - start_time) * 1000
                    ErrorHandler.handle_general_exception(
                        f"Stream data parsing error: {e}",
                        self.task_logger,
                        response,
                        response_time,
                    )
                    has_failed = True
                    # Return partial results if available
                    if metrics.usage_tokens:
                        return (
                            metrics.reasoning_content,
                            metrics.model_output,
                            metrics.usage_tokens,
                        )

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
            has_failed = True
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
            has_failed = True

        # Ensure we always return the correct type (never None)
        return_usage: Dict[str, Optional[int]] = (
            usage_tokens  # Default to initialized value
        )

        if "final_usage_tokens" in locals() and final_usage_tokens:
            return_usage = final_usage_tokens
        elif metrics.usage_tokens:
            return_usage = metrics.usage_tokens

        return (
            metrics.reasoning_content,
            metrics.model_output,
            return_usage,
        )

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

                if self._handle_response_error(response, start_time, request_name):
                    has_failed = True
                    return "", "", usage_tokens

                try:
                    resp_json = response.json()
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
                        has_failed = True
                        return "", "", usage_tokens

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
            has_failed = True

        return reasoning_content, model_output, usage_tokens

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
