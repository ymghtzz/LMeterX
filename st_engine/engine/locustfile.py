"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Optimized and refactored Locust test file for LLM performance testing.
"""

import json
import os
import ssl
import sys
import tempfile
import time
from typing import Any, Dict, Optional

import urllib3
from gevent import queue
from locust import FastHttpUser, between, events, task
from urllib3.exceptions import InsecureRequestWarning

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.core import (
    CertificateManager,
    ConfigManager,
    GlobalConfig,
    GlobalStateManager,
    ValidationManager,
)
from engine.processing import ErrorHandler, EventManager, RequestHandler, StreamHandler
from utils.common import count_tokens, mask_sensitive_data
from utils.config import (
    DEFAULT_API_PATH,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_WAIT_TIME_MAX,
    DEFAULT_WAIT_TIME_MIN,
    METRIC_TTT,
)
from utils.logger import logger

# Disable the specific InsecureRequestWarning from urllib3
urllib3.disable_warnings(InsecureRequestWarning)

# === GLOBAL STATE ===
# Initialize global state using the state manager
GlobalStateManager.initialize_global_state()


def get_global_config() -> GlobalConfig:
    """Thread-safe access to global configuration."""
    return GlobalStateManager.get_global_config()


def get_global_task_queue() -> Dict[str, queue.Queue]:
    """Thread-safe access to global task queue."""
    return GlobalStateManager.get_global_task_queue()


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
    global_config = get_global_config()

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
        global_config.task_id = task_id
        global_config.api_path = options.api_path
        global_config.request_payload = options.request_payload
        global_config.model_name = options.model_name
        global_config.system_prompt = options.system_prompt
        global_config.user_prompt = options.user_prompt
        global_config.stream_mode = str(options.stream_mode).lower() in ("true", "1")
        global_config.chat_type = int(options.chat_type)
        global_config.cert_file = options.cert_file
        global_config.key_file = options.key_file
        global_config.field_mapping = options.field_mapping
        global_config.test_data = options.test_data

        # Parse and validate configuration
        global_config.headers = ConfigManager.parse_headers(
            options.headers, task_logger
        )
        global_config.cookies = ConfigManager.parse_cookies(
            options.cookies, task_logger
        )
        global_config.cert_config = CertificateManager.configure_certificates(
            global_config.cert_file, global_config.key_file, task_logger
        )

        # Validate configuration before proceeding
        if not ValidationManager.validate_config(global_config, task_logger):
            raise ValueError("Invalid configuration provided")

        # Initialize prompt queue
        if not hasattr(environment, "prompt_queue"):
            try:
                from utils.common import init_prompt_queue

                environment.prompt_queue = init_prompt_queue(
                    chat_type=options.chat_type,
                    test_data=options.test_data or "",
                    task_logger=task_logger,
                )
            except Exception as e:
                task_logger.error(f"Failed to initialize prompt queue: {e}")
                environment.prompt_queue = queue.Queue()

        environment.global_config = global_config
        masked_config = mask_sensitive_data(global_config.__dict__)
        # task_logger.info(f"Locust initialization complete. Config: {masked_config}")
        GlobalStateManager.set_start_time(time.time())

    except Exception as e:
        task_logger.error(f"Error during Locust initialization: {e}", exc_info=True)
        raise


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Calculate final metrics and save results."""
    global_config = get_global_config()
    global_task_queue = get_global_task_queue()
    start_time = GlobalStateManager.get_start_time()

    task_id = global_config.task_id
    task_logger = logger.bind(task_id=task_id)
    end_time = time.time()

    execution_time = (end_time - start_time) if start_time else 0
    if execution_time <= 0:
        task_logger.warning(
            "Start time was not recorded; cannot calculate execution time."
        )

    try:
        from utils.common import calculate_custom_metrics, get_locust_stats

        custom_metrics = calculate_custom_metrics(
            task_id, global_task_queue, execution_time
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
class LLMTestUser(FastHttpUser):
    """A user class that simulates a client making requests to an LLM service."""

    wait_time = between(DEFAULT_WAIT_TIME_MIN, DEFAULT_WAIT_TIME_MAX)
    # Align FastHttp timeouts with previous requests timeout
    connection_timeout = DEFAULT_TIMEOUT
    network_timeout = DEFAULT_TIMEOUT

    # Class-level shared instances to reduce memory usage
    _shared_request_handler = None
    _shared_stream_handler = None

    def __init__(self, environment):
        """Initialize the LLMTestUser with environment and handlers.

        Args:
            environment: Locust environment object
        """
        super().__init__(environment)
        global_config = get_global_config()
        self.task_logger = logger.bind(task_id=global_config.task_id)

        # Use shared handlers to reduce memory footprint
        self.request_handler = self._get_request_handler()
        self.stream_handler = self._get_stream_handler()

        self._configure_ssl_settings()

    @classmethod
    def _get_request_handler(cls):
        """Get or create shared request handler."""
        if cls._shared_request_handler is None:
            global_config = get_global_config()
            cls._shared_request_handler = RequestHandler(
                global_config, logger.bind(task_id=global_config.task_id)
            )
        return cls._shared_request_handler

    @classmethod
    def _get_stream_handler(cls):
        """Get or create shared stream handler."""
        if cls._shared_stream_handler is None:
            global_config = get_global_config()
            cls._shared_stream_handler = StreamHandler(
                global_config, logger.bind(task_id=global_config.task_id)
            )
        return cls._shared_stream_handler

    def _configure_ssl_settings(self):
        """Configure SSL settings for FastHttpUser."""
        global_config = get_global_config()

        try:
            # Set skip SSL certificate verification (equivalent to requests verify=False)
            if hasattr(self.client, "verify"):
                self.client.verify = False

            # For newer FastHttp versions, use ssl_context or insecure options
            if hasattr(self.client, "insecure"):
                self.client.insecure = True
            elif hasattr(self.client, "ssl_options"):
                # Create SSL context with certificate verification disabled
                ssl_context = self._get_ssl_context()
                if ssl_context:
                    self.client.ssl_options = {"ssl_context": ssl_context}
            else:
                # For older FastHttp versions, try to set properties directly
                self._configure_legacy_ssl()

            self.task_logger.debug("SSL settings configured for FastHttpUser")

        except Exception as e:
            self.task_logger.warning(f"Failed to configure SSL settings: {e}")
            # Continue execution, do not interrupt because of SSL configuration failure

    def _get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create and configure SSL context."""
        global_config = get_global_config()

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        # If client certificate configuration is provided, add to SSL context
        if global_config.cert_config:
            try:
                if isinstance(global_config.cert_config, tuple):
                    # Separate certificate and key files
                    cert_file, key_file = global_config.cert_config
                    ssl_context.load_cert_chain(cert_file, key_file)
                    self.task_logger.info(f"Loaded client certificate: {cert_file}")
                elif isinstance(global_config.cert_config, str):
                    # Combined certificate+key file
                    ssl_context.load_cert_chain(global_config.cert_config)
                    self.task_logger.info(
                        f"Loaded client certificate: {global_config.cert_config}"
                    )
            except Exception as e:
                self.task_logger.warning(f"Failed to load client certificate: {e}")
                return None

        return ssl_context

    def _configure_legacy_ssl(self):
        """Configure SSL for older FastHttp versions."""
        global_config = get_global_config()

        if hasattr(self.client, "_client"):
            # Some FastHttp versions wrap the underlying client
            if hasattr(self.client._client, "verify"):
                self.client._client.verify = False

        # If client certificate configuration is provided, try to set (although it may not work)
        if global_config.cert_config:
            self.task_logger.warning(
                "Client certificate configuration may not be supported in this FastHttp version. "
                "Consider upgrading Locust or using HttpUser if mTLS is required."
            )

    def get_next_prompt(self) -> Dict[str, Any]:
        """Fetch the next prompt from the shared queue."""
        try:
            # Use a more robust queue implementation
            if (
                hasattr(self.environment, "prompt_queue")
                and not self.environment.prompt_queue.empty()
            ):
                prompt_data = self.environment.prompt_queue.get_nowait()
                # Put back into queue for other users
                self.environment.prompt_queue.put_nowait(prompt_data)
                return prompt_data
            else:
                self.task_logger.warning(
                    "Prompt queue is empty or not initialized. Using default prompt."
                )
                return {"id": "default", "prompt": DEFAULT_PROMPT}
        except queue.Empty:
            self.task_logger.warning("Prompt queue is empty. Using default prompt.")
            return {"id": "default", "prompt": DEFAULT_PROMPT}
        except Exception as e:
            self.task_logger.error(
                f"Error accessing prompt queue: {e}. Using default prompt."
            )
            return {"id": "default", "prompt": DEFAULT_PROMPT}

    def _log_token_counts(
        self,
        user_prompt: str,
        reasoning_content: str,
        model_output: str,
        usage_tokens: Optional[Dict[str, Optional[int]]] = None,
    ) -> None:
        """Calculate and log token counts for the completed request."""
        global_config = get_global_config()
        global_task_queue = get_global_task_queue()

        try:
            model_name = global_config.model_name or ""
            system_prompt = global_config.system_prompt or ""

            # Validate inputs
            user_prompt = user_prompt or ""
            reasoning_content = reasoning_content or ""
            model_output = model_output or ""

            # Prefer usage_tokens if available and valid
            completion_tokens = None
            total_tokens = None

            if usage_tokens:
                completion_tokens = usage_tokens.get("completion_tokens")
                total_tokens = usage_tokens.get("total_tokens")

            # Fallback: manual counting if completion_tokens and total_tokens are missing
            if completion_tokens is None or total_tokens is None:
                system_tokens = (
                    count_tokens(system_prompt, model_name) if system_prompt else 0
                )
                user_tokens = (
                    count_tokens(user_prompt, model_name) if user_prompt else 0
                )
                reasoning_tokens = (
                    count_tokens(reasoning_content, model_name)
                    if reasoning_content
                    else 0
                )
                output_tokens = (
                    count_tokens(model_output, model_name) if model_output else 0
                )

                completion_tokens = reasoning_tokens + output_tokens
                total_tokens = system_tokens + user_tokens + completion_tokens

            # Ensure integer and log - only if tokens are not None and positive
            if completion_tokens is not None and completion_tokens > 0:
                global_task_queue["completion_tokens_queue"].put(int(completion_tokens))
            if total_tokens is not None and total_tokens > 0:
                global_task_queue["all_tokens_queue"].put(int(total_tokens))

        except Exception as e:
            self.task_logger.error(f"Failed to count tokens: {e}", exc_info=True)

    @task
    def chat_request(self):
        """Main Locust task that executes a single chat request."""
        global_config = get_global_config()

        prompt_data = self.get_next_prompt()

        base_request_kwargs, user_prompt = self.request_handler.prepare_request_kwargs(
            prompt_data
        )
        # self.task_logger.info(f"base_request_kwargs: {base_request_kwargs}")

        if not base_request_kwargs:
            self.task_logger.error(
                "Failed to generate request arguments. Skipping task."
            )
            return

        # fix: remove request-level cert config, because it's already configured at session level
        # original code: if global_config.cert_config: base_request_kwargs["cert"] = global_config.cert_config

        start_time = time.time()
        reasoning_content, model_output = "", ""
        usage_tokens = None
        request_name = (
            base_request_kwargs.get("name", "failure")
            if base_request_kwargs
            else "failure"
        )

        try:
            if global_config.stream_mode:
                reasoning_content, model_output = (
                    self.stream_handler.handle_stream_request(
                        self.client, base_request_kwargs, start_time
                    )
                )
            else:
                reasoning_content, model_output, usage_tokens = (
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

        if reasoning_content or model_output or usage_tokens:
            self._log_token_counts(
                user_prompt or "", reasoning_content, model_output, usage_tokens
            )
