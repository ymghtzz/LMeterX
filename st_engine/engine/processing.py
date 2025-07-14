"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Stream processing and error handling for the stress testing engine.
"""

import json
import time
from typing import Any, Dict, Optional

from locust import events

from engine.core import FieldMapping, StreamMetrics
from utils.config import MAX_OUTPUT_LENGTH


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
        except Exception:
            # Log parsing errors but don't treat them as API errors
            return None

    @staticmethod
    def handle_general_exception(
        error_msg: str,
        task_logger,
        response=None,
        response_time: float = 0,
        request_name: str = "failure",
    ) -> None:
        """Centralized handler for logging exceptions during requests."""
        task_logger.error(error_msg)
        if response:
            response.failure(error_msg)
        else:
            # If no response object available (e.g., connection failed),
            # we need to manually fire the failure event with the correct request name
            EventManager.fire_failure_event(
                name=request_name,
                response_time=response_time,
                exception=Exception(error_msg),
            )


# === EVENT MANAGEMENT ===
class EventManager:
    """Manages Locust events and metrics."""

    @staticmethod
    def fire_failure_event(
        name: str = "failure",
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

        except (json.JSONDecodeError, IndexError, KeyError):
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
                EventManager.fire_metric_event(
                    "Time_to_first_output_token", ttfot, len(content_chunk)
                )

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
                    "Time_to_first_reasoning_token", ttfrt, len(reasoning_chunk)
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
                    "Time_to_reasoning_completion", ttrc, len(metrics.reasoning_content)
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
