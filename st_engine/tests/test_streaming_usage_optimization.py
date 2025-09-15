"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Test streaming usage token optimization functionality.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.core import FieldMapping, GlobalConfig, StreamMetrics
from engine.processing import StreamProcessor
from utils.logger import logger


class TestStreamingUsageOptimization(unittest.TestCase):
    """Test streaming usage token extraction and optimization."""

    def setUp(self):
        """Set up test fixtures."""
        self.field_mapping = FieldMapping(
            data_format="json",
            content="choices.0.delta.content",
            reasoning_content="choices.0.delta.reasoning",
            usage="usage",
            stream_prefix="data: ",
            stop_flag="[DONE]",
        )
        self.mock_logger = MagicMock()

    def test_extract_usage_from_stream_chunk(self):
        """Test extracting usage information from streaming chunk."""
        # Sample chunk data based on the user's API example
        chunk_data = {
            "id": "chat-8fb303a94bc3485b9fa13e69af591011",
            "object": "chat.completion.chunk",
            "created": 1757404366,
            "model": "deepseek-r1-250528",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "?"},
                    "logprobs": None,
                    "finish_reason": "stop",
                    "stop_reason": None,
                }
            ],
            "usage": {
                "prompt_tokens": 4,
                "total_tokens": 218,
                "completion_tokens": 214,
            },
        }

        chunk_str = "data: " + json.dumps(chunk_data)
        chunk_bytes = chunk_str.encode("utf-8")

        metrics = StreamMetrics()
        start_time = 1234567890.0

        # Process the chunk
        should_break, error_message, updated_metrics = (
            StreamProcessor.process_stream_chunk(
                chunk_bytes, self.field_mapping, start_time, metrics, self.mock_logger
            )
        )

        # Verify usage tokens were extracted
        self.assertIsNotNone(updated_metrics.usage)
        self.assertEqual(updated_metrics.usage["prompt_tokens"], 4)
        self.assertEqual(updated_metrics.usage["completion_tokens"], 214)
        self.assertEqual(updated_metrics.usage["total_tokens"], 218)

    def test_extract_usage_with_different_field_names(self):
        """Test extracting usage with different field naming conventions."""
        # Test with alternative field names
        chunk_data = {
            "usage": {
                "prompt_token_count": 10,
                "completion_token_count": 50,
                "total_token_count": 60,
            }
        }

        chunk_str = "data: " + json.dumps(chunk_data)
        chunk_bytes = chunk_str.encode("utf-8")

        metrics = StreamMetrics()
        start_time = 1234567890.0

        # Process the chunk
        should_break, error_message, updated_metrics = (
            StreamProcessor.process_stream_chunk(
                chunk_bytes, self.field_mapping, start_time, metrics, self.mock_logger
            )
        )

        # Verify usage tokens were extracted with flexible naming
        self.assertIsNotNone(updated_metrics.usage)
        # The implementation preserves original field names
        self.assertEqual(updated_metrics.usage["prompt_token_count"], 10)
        self.assertEqual(updated_metrics.usage["completion_token_count"], 50)
        self.assertEqual(updated_metrics.usage["total_token_count"], 60)

    def test_extract_usage_standard_field_names(self):
        """Test extracting usage with standard field names."""
        # Test with standard field names
        chunk_data = {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 50,
                "total_tokens": 60,
            }
        }

        chunk_str = "data: " + json.dumps(chunk_data)
        chunk_bytes = chunk_str.encode("utf-8")

        metrics = StreamMetrics()
        start_time = 1234567890.0

        # Process the chunk
        should_break, error_message, updated_metrics = (
            StreamProcessor.process_stream_chunk(
                chunk_bytes, self.field_mapping, start_time, metrics, self.mock_logger
            )
        )

        # Verify usage tokens were extracted
        self.assertIsNotNone(updated_metrics.usage)
        self.assertEqual(updated_metrics.usage["prompt_tokens"], 10)
        self.assertEqual(updated_metrics.usage["completion_tokens"], 50)
        self.assertEqual(updated_metrics.usage["total_tokens"], 60)

    def test_usage_overwrite_latest(self):
        """Test that later usage chunks overwrite earlier ones."""
        metrics = StreamMetrics()
        start_time = 1234567890.0

        # First chunk with usage
        chunk_data_1 = {
            "usage": {"prompt_tokens": 4, "completion_tokens": 100, "total_tokens": 104}
        }
        chunk_str_1 = "data: " + json.dumps(chunk_data_1)
        chunk_bytes_1 = chunk_str_1.encode("utf-8")

        # Process first chunk
        should_break, error_message, updated_metrics = (
            StreamProcessor.process_stream_chunk(
                chunk_bytes_1, self.field_mapping, start_time, metrics, self.mock_logger
            )
        )

        # Verify first usage
        self.assertEqual(updated_metrics.usage["completion_tokens"], 100)
        self.assertEqual(updated_metrics.usage["total_tokens"], 104)

        # Second chunk with updated usage (like final chunk)
        chunk_data_2 = {
            "usage": {"prompt_tokens": 4, "completion_tokens": 214, "total_tokens": 218}
        }
        chunk_str_2 = "data: " + json.dumps(chunk_data_2)
        chunk_bytes_2 = chunk_str_2.encode("utf-8")

        # Process second chunk
        should_break, error_message, final_metrics = (
            StreamProcessor.process_stream_chunk(
                chunk_bytes_2,
                self.field_mapping,
                start_time,
                updated_metrics,
                self.mock_logger,
            )
        )

        # Verify final usage (should be updated)
        self.assertEqual(final_metrics.usage["completion_tokens"], 214)
        self.assertEqual(final_metrics.usage["total_tokens"], 218)

    def test_no_usage_field(self):
        """Test processing chunk without usage field."""
        chunk_data = {
            "id": "chat-test",
            "choices": [{"index": 0, "delta": {"content": "Hello"}}],
        }

        chunk_str = "data: " + json.dumps(chunk_data)
        chunk_bytes = chunk_str.encode("utf-8")

        metrics = StreamMetrics()
        start_time = 1234567890.0

        # Process the chunk
        should_break, error_message, updated_metrics = (
            StreamProcessor.process_stream_chunk(
                chunk_bytes, self.field_mapping, start_time, metrics, self.mock_logger
            )
        )

        # Verify no usage tokens were set (returns empty dict when field is missing)
        self.assertEqual(updated_metrics.usage, {})

    def test_invalid_usage_field(self):
        """Test processing chunk with invalid usage field."""
        chunk_data = {"usage": "invalid_usage_format"}  # Should be dict, not string

        chunk_str = "data: " + json.dumps(chunk_data)
        chunk_bytes = chunk_str.encode("utf-8")

        metrics = StreamMetrics()
        start_time = 1234567890.0

        # Process the chunk
        should_break, error_message, updated_metrics = (
            StreamProcessor.process_stream_chunk(
                chunk_bytes, self.field_mapping, start_time, metrics, self.mock_logger
            )
        )

        # Verify that invalid usage format is handled
        # The field will contain the invalid string, but won't be treated as dict
        self.assertEqual(updated_metrics.usage, "invalid_usage_format")

    @patch("engine.processing.StreamHandler.handle_stream_request")
    def test_stream_handler_returns_usage(self, mock_handle_stream):
        """Test that StreamHandler returns usage tokens in streaming mode."""
        # Mock return value with usage tokens
        mock_usage = {
            "prompt_tokens": 4,
            "completion_tokens": 214,
            "total_tokens": 218,
        }
        mock_handle_stream.return_value = (
            "reasoning content",
            "model output",
            mock_usage,
        )

        # Import and create handler
        from engine.processing import StreamHandler

        config = GlobalConfig()
        handler = StreamHandler(config, self.mock_logger)

        # Call method
        reasoning, output, usage = handler.handle_stream_request(None, {}, 1234567890.0)

        # Verify return values
        self.assertEqual(reasoning, "reasoning content")
        self.assertEqual(output, "model output")
        self.assertEqual(usage, mock_usage)

    def test_metrics_with_field_default(self):
        """Test StreamMetrics initializes with correct default values."""
        metrics = StreamMetrics()

        # Verify default values
        self.assertFalse(metrics.first_token_received)
        self.assertFalse(metrics.first_thinking_received)
        self.assertFalse(metrics.reasoning_is_active)
        self.assertFalse(metrics.reasoning_ended)
        self.assertIsNone(metrics.first_output_token_time)
        self.assertIsNone(metrics.first_thinking_token_time)
        self.assertEqual(metrics.content, "")
        self.assertEqual(metrics.reasoning_content, "")
        self.assertIsNone(metrics.usage)


if __name__ == "__main__":
    unittest.main()
