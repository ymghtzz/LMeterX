"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Optimized and refactored Locust test file for LLM performance testing.
"""

import json
import os
import signal
import ssl
import sys
import tempfile
import time
from dataclasses import field
from typing import Any, Dict, Optional, Tuple, Union

import urllib3
from gevent import queue
from locust import FastHttpUser, between, events, task
from urllib3.exceptions import InsecureRequestWarning

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.base import (
    DEFAULT_API_PATH,
    DEFAULT_CONTENT_TYPE,
    DEFAULT_PROMPT,
    DEFAULT_TIMEOUT,
    DEFAULT_WAIT_TIME_MAX,
    DEFAULT_WAIT_TIME_MIN,
)

# Local imports after path setup
from engine.core import (  # noqa: E402
    CertificateManager,
    ConfigManager,
    GlobalConfig,
    GlobalStateManager,
    ValidationManager,
)
from engine.processing import ErrorHandler, RequestHandler, StreamHandler  # noqa: E402
from utils.common import count_tokens, mask_sensitive_data  # noqa: E402
from utils.logger import logger  # noqa: E402

# Disable the specific InsecureRequestWarning from urllib3
urllib3.disable_warnings(InsecureRequestWarning)

# === SIGNAL HANDLING ===
# Flag to track if we're already in shutdown process
_shutdown_in_progress = False
custom_metrics_aggregated: Dict[str, Any] = {}


def graceful_signal_handler(signum, frame):
    """
    Custom signal handler to gracefully handle SIGTERM when Locust is already shutting down.
    This prevents the "stopping state" exception from being raised.
    """
    global _shutdown_in_progress

    task_id = os.environ.get("TASK_ID", "unknown")
    task_logger = GlobalStateManager.get_task_logger(task_id)

    if _shutdown_in_progress:
        return

    _shutdown_in_progress = True

    # For worker processes, ensure metrics are sent before exit
    try:
        try:
            from locust.runners import WorkerRunner

            WorkerRunner = WorkerRunner
        except ImportError:
            WorkerRunner = None

        # Check if this is a worker process
        if hasattr(frame, "f_globals") and "environment" in frame.f_globals:
            env = frame.f_globals["environment"]
            is_worker = False
            if WorkerRunner is not None:
                is_worker = hasattr(env, "runner") and isinstance(
                    env.runner, WorkerRunner
                )
            else:
                is_worker = hasattr(env, "runner") and "WorkerRunner" in str(
                    type(env.runner)
                )

            if is_worker:
                task_logger.debug(
                    f"Worker process {os.getpid()} received signal {signum}, ensuring metrics are sent..."
                )

                # Send metrics to Master immediately
                try:
                    from utils.common import calculate_custom_metrics

                    global_task_queue = GlobalStateManager.get_global_task_queue()
                    start_time = GlobalStateManager.get_start_time()
                    end_time = time.time()
                    execution_time = (end_time - start_time) if start_time else 0

                    custom_metrics = calculate_custom_metrics(
                        task_id, global_task_queue, execution_time
                    )

                    # Send directly to Master
                    if hasattr(env, "runner") and hasattr(env.runner, "send_message"):
                        # Send metrics
                        env.runner.send_message("worker_custom_metrics", custom_metrics)
                        task_logger.debug(
                            f"Emergency metrics sent to master: {custom_metrics}"
                        )

                        # Send confirmation
                        env.runner.send_message(
                            "worker_metrics_sent", {"pid": os.getpid()}
                        )
                        task_logger.debug(f"Emergency confirmation sent to master")

                        # Wait a short time to ensure message is sent
                        import time

                        time.sleep(0.5)
                    else:
                        task_logger.warning(
                            "Cannot send metrics to master, runner not available"
                        )

                except Exception as e:
                    task_logger.error(f"Failed to send emergency metrics: {e}")
    except Exception as e:
        task_logger.warning(f"Error in graceful signal handler: {e}")

    # Let the default signal handler proceed, but our flag will prevent duplicate User.stop() calls
    # Restore the default signal handler and re-raise the signal
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


# === GLOBAL STATE ===
# Global state will be initialized when needed, not at module import time


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
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (used as fallback when start_time is unavailable)",
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
    task_logger = GlobalStateManager.get_task_logger(task_id)

    # Register custom signal handler to handle graceful shutdown
    try:
        signal.signal(signal.SIGTERM, graceful_signal_handler)
        signal.signal(signal.SIGINT, graceful_signal_handler)
    except Exception as e:
        task_logger.warning(f"Failed to register custom signal handlers: {e}")

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
        global_config.duration = int(options.duration)

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
        GlobalStateManager.set_start_time(time.time())

        # Build SSL context once per process if needed
        try:
            GlobalStateManager.build_ssl_context_if_needed(global_config.cert_config)
        except Exception:
            pass

    except Exception as e:
        task_logger.error(f"Error during Locust initialization: {e}", exc_info=True)
        raise


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Register message handlers when test starts"""
    try:
        # Check if this is a worker process
        from locust.runners import WorkerRunner

        is_worker = isinstance(environment.runner, WorkerRunner)

        if is_worker:
            # Worker process: register handler to respond to Master requests
            task_logger = GlobalStateManager.get_task_logger(
                os.environ.get("TASK_ID", "unknown")
            )
            task_logger.debug(
                f"Worker process {os.getpid()} started, registered message handlers"
            )

            # Register worker message handler
            def on_master_msg(environment, msg, **_):
                if msg.type == "request_metrics":
                    # Send metrics immediately when Master requests
                    try:
                        from utils.common import calculate_custom_metrics

                        global_task_queue = GlobalStateManager.get_global_task_queue()
                        start_time = GlobalStateManager.get_start_time()
                        end_time = time.time()
                        execution_time = (end_time - start_time) if start_time else 0

                        custom_metrics = calculate_custom_metrics(
                            os.environ.get("TASK_ID", "unknown"),
                            global_task_queue,
                            execution_time,
                        )

                        # Add PID to metrics for proper identification
                        custom_metrics["pid"] = os.getpid()

                        environment.runner.send_message(
                            "worker_custom_metrics", custom_metrics
                        )
                        task_logger.debug(
                            f"Metrics sent in response to master request: {custom_metrics}"
                        )

                    except Exception as e:
                        task_logger.error(
                            f"Failed to send metrics in response to master request: {e}"
                        )

            environment.runner.register_message("request_metrics", on_master_msg)
        else:
            # Master process: register handler to receive Worker messages
            task_logger = GlobalStateManager.get_task_logger(
                os.environ.get("TASK_ID", "unknown")
            )
            task_logger.debug(
                f"Master process {os.getpid()} started, registering message handlers"
            )

            # Initialize message storage lists
            environment.worker_metrics_list = []
            environment.worker_confirmations = set()
            environment.incremental_metrics_list = []
            environment.worker_metrics_received = set()  # Track received Worker PIDs

            # Register Master message handler
            def on_worker_msg(environment, msg, **_):
                if msg.type == "worker_custom_metrics":
                    # Check if we've already received metrics from this Worker
                    worker_pid = msg.data.get("pid", "unknown")
                    if worker_pid not in environment.worker_metrics_received:
                        environment.worker_metrics_received.add(worker_pid)
                        environment.worker_metrics_list.append(msg.data)
                        task_logger.debug(
                            f"Master received worker metrics from PID {worker_pid}: {msg.data}"
                        )
                    else:
                        task_logger.warning(
                            f"Duplicate metrics received from worker PID {worker_pid}"
                        )
                elif msg.type == "worker_metrics_sent":
                    worker_pid = msg.data.get("pid", "unknown")
                    environment.worker_confirmations.add(worker_pid)
                    task_logger.debug(
                        f"Master received confirmation from worker {worker_pid}"
                    )
                elif msg.type == "worker_incremental_metrics":
                    environment.incremental_metrics_list.append(msg.data)

            try:
                environment.runner.register_message(
                    "worker_custom_metrics", on_worker_msg
                )
                environment.runner.register_message(
                    "worker_metrics_sent", on_worker_msg
                )
                environment.runner.register_message(
                    "worker_incremental_metrics", on_worker_msg
                )
                task_logger.debug("Master message handlers registered successfully")
            except Exception as e:
                task_logger.error(f"Failed to register master message handlers: {e}")

    except Exception as e:
        # Ignore errors, don't affect test execution
        task_logger = GlobalStateManager.get_task_logger(
            os.environ.get("TASK_ID", "unknown")
        )
        task_logger.warning(f"Error in on_test_start: {e}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Handle metrics aggregation when test stops"""
    global_config = get_global_config()
    task_id = global_config.task_id
    task_logger = GlobalStateManager.get_task_logger(task_id)

    execution_time = None
    start_time = GlobalStateManager.get_start_time()
    end_time = time.time()

    try:
        if start_time is not None and end_time is not None:
            execution_time = max(end_time - start_time, 0.001)
        else:
            duration = getattr(global_config, "duration", None)
            if duration is not None and duration > 0:
                execution_time = float(duration)
            else:
                execution_time = 60.0
                task_logger.error(
                    f"Failed to get effective execution time: start_time={start_time}, duration={duration}"
                )

                raise ValueError(
                    f"Failed to get effective execution time: start_time={start_time}, duration={duration}"
                )

    except Exception as e:
        task_logger.error(
            f"Failed to calculate execution time: {str(e)}", exc_info=True
        )
        execution_time = 60.0
        raise RuntimeError(f"Failed to calculate execution time: {str(e)}")

    from utils.common import calculate_custom_metrics, get_locust_stats

    # Check if this is a worker process
    is_worker = False
    try:
        from locust.runners import WorkerRunner

        is_worker = isinstance(environment.runner, WorkerRunner)
    except ImportError:
        is_worker = "WorkerRunner" in str(type(environment.runner))

    # Check if this is a multi-process mode
    is_multiprocess = False
    worker_count = 0
    try:
        worker_count = getattr(environment.runner, "worker_count", 0)
        if worker_count > 0:
            has_workers_attr = hasattr(environment.runner, "workers")
            has_worker_runner = hasattr(environment.runner, "_worker_connections")
            if has_workers_attr or has_worker_runner:
                is_multiprocess = True
                task_logger.debug(
                    f"Detected multi-process mode: worker_count={worker_count}, has_workers={has_workers_attr}, has_worker_runner={has_worker_runner}"
                )
            else:
                is_multiprocess = worker_count > 1
                task_logger.debug(
                    f"Ambiguous case: worker_count={worker_count}, assuming {'multi-process' if is_multiprocess else 'single-process'} mode"
                )
        else:
            is_multiprocess = False
            task_logger.debug("Detected single process mode: worker_count=0")
    except Exception as e:
        task_logger.warning(f"Error detecting multi-process mode: {e}")
        is_multiprocess = False

    task_logger.debug(
        f"Process type: {'Worker' if is_worker else 'Master'}, "
        f"Multi-process: {is_multiprocess}, Worker count: {worker_count}, "
        f"Execution time: {execution_time}"
    )

    # === WORKER PROCESS LOGIC ===
    if is_worker:
        # Worker process: collect basic metrics only
        try:
            global_task_queue = get_global_task_queue()

            # Get basic metrics without TPS
            worker_metrics = calculate_custom_metrics(
                task_id, global_task_queue, execution_time
            )
            worker_metrics["pid"] = os.getpid()

            task_logger.debug(
                f"Worker {os.getpid()} calculated metrics: {worker_metrics}"
            )

            # Send basic metrics to Master
            try:
                for attempt in range(3):
                    try:
                        environment.runner.send_message(
                            "worker_custom_metrics", worker_metrics
                        )
                        task_logger.debug(
                            f"Worker {os.getpid()} sent metrics to master (attempt {attempt + 1})"
                        )

                        # Send confirmation message
                        environment.runner.send_message(
                            "worker_metrics_sent", {"pid": os.getpid()}
                        )
                        task_logger.debug(
                            f"Worker {os.getpid()} sent confirmation (attempt {attempt + 1})"
                        )

                        import gevent

                        gevent.sleep(0.5)
                        break
                    except Exception as e:
                        task_logger.warning(
                            f"Worker {os.getpid()} failed to send metrics (attempt {attempt + 1}): {e}"
                        )
                        if attempt < 2:
                            import gevent

                            gevent.sleep(1)
                        else:
                            raise
            except Exception as e:
                task_logger.error(
                    f"Worker {os.getpid()} failed to send metrics after all attempts: {e}"
                )

            # Wait for Master processing
            import gevent

            gevent.sleep(3)

        except Exception as e:
            task_logger.error(f"Worker {os.getpid()} failed to send metrics: {e}")
        return

    # === MASTER PROCESS LOGIC ===
    # Master process: aggregate basic metrics and calculate TPS
    worker_metrics_list = getattr(environment, "worker_metrics_list", [])
    worker_confirmations = getattr(environment, "worker_confirmations", set())

    # Wait for Worker metrics in multi-process mode
    if is_multiprocess and worker_count > 0:
        import gevent

        max_wait_time = 15  # Increased wait time for better reliability
        wait_time = 0
        request_attempts = 0
        max_request_attempts = 3

        # Multiple attempts to request Worker metrics for better reliability
        while (
            request_attempts < max_request_attempts
            and len(worker_metrics_list) < worker_count
        ):
            try:
                if hasattr(environment.runner, "send_message"):
                    task_logger.debug(
                        f"Requesting metrics from workers (attempt {request_attempts + 1})..."
                    )
                    environment.runner.send_message(
                        "request_metrics", {"request": "all_metrics"}
                    )
                    gevent.sleep(2)  # Give more time for workers to respond
                    request_attempts += 1
            except Exception as e:
                task_logger.warning(
                    f"Failed to request worker metrics (attempt {request_attempts + 1}): {e}"
                )
                request_attempts += 1
                gevent.sleep(1)

        # Wait for worker responses with progressive timeout
        while len(worker_metrics_list) < worker_count and wait_time < max_wait_time:
            gevent.sleep(0.5)
            wait_time += 0.5

            # Log progress every 2 seconds
            if wait_time % 2 == 0:
                task_logger.debug(
                    f"Waiting for worker metrics... ({len(worker_metrics_list)}/{worker_count}) after {wait_time}s"
                )

        # Final status check
        if len(worker_metrics_list) < worker_count:
            task_logger.warning(
                f"Only received {len(worker_metrics_list)} worker metrics out of {worker_count} expected workers after {max_wait_time}s"
            )

            # Try to get partial metrics from available workers
            if len(worker_metrics_list) > 0:
                task_logger.info(
                    f"Proceeding with metrics from {len(worker_metrics_list)} available workers"
                )
            else:
                task_logger.error(
                    "No worker metrics received, falling back to master metrics only"
                )
        else:
            task_logger.info(
                f"Successfully collected metrics from all {worker_count} workers"
            )

    # Aggregate basic metrics
    total_reqs = 0
    total_comp_tokens = 0
    total_all_tokens = 0

    if is_multiprocess:
        # Multi-process mode: aggregate from worker metrics
        if worker_metrics_list:
            task_logger.debug(
                f"Multi-process mode: aggregating {len(worker_metrics_list)} worker metrics"
            )

            processed_pids = set()
            for wm in worker_metrics_list:
                pid = wm.get("pid")
                if pid not in processed_pids:
                    processed_pids.add(pid)
                    total_reqs += wm.get("reqs_num", 0)
                    total_comp_tokens += wm.get("completion_tokens", 0)
                    total_all_tokens += wm.get("all_tokens", 0)
                    task_logger.debug(f"Aggregated worker metrics from PID {pid}: {wm}")

            task_logger.debug(
                f"Multi-process mode: aggregated {len(processed_pids)} unique worker metrics"
            )
        else:
            # Fallback: use Master's local metrics
            task_logger.warning(
                "No worker metrics received, falling back to master local metrics"
            )
            global_task_queue = get_global_task_queue()
            master_metrics = calculate_custom_metrics(
                task_id, global_task_queue, execution_time
            )
            total_reqs = master_metrics["reqs_num"]
            total_comp_tokens = master_metrics["completion_tokens"]
            total_all_tokens = master_metrics["all_tokens"]
    else:
        # Single-process mode: use Master's local metrics
        task_logger.debug("Single process mode: using master local metrics")
        global_task_queue = get_global_task_queue()
        master_metrics = calculate_custom_metrics(
            task_id, global_task_queue, execution_time
        )
        total_reqs = master_metrics["reqs_num"]
        total_comp_tokens = master_metrics["completion_tokens"]
        total_all_tokens = master_metrics["all_tokens"]

    # Calculate final TPS metrics using aggregated data and total execution time
    custom_metrics = {
        "reqs_num": total_reqs,
        "req_throughput": total_reqs / execution_time if execution_time > 0 else 0,
        "completion_tps": (
            total_comp_tokens / execution_time if execution_time > 0 else 0
        ),
        "total_tps": total_all_tokens / execution_time if execution_time > 0 else 0,
        "avg_completion_tokens_per_req": (
            total_comp_tokens / total_reqs if total_reqs > 0 else 0
        ),
        "avg_total_tokens_per_req": (
            total_all_tokens / total_reqs if total_reqs > 0 else 0
        ),
    }

    # Get Locust standard statistics
    locust_stats = get_locust_stats(task_id, environment.stats)

    # Save results
    result_file = os.path.join(
        tempfile.gettempdir(), "locust_result", task_id, "result.json"
    )
    os.makedirs(os.path.dirname(result_file), exist_ok=True)
    with open(result_file, "w") as f:
        json.dump(
            {
                "custom_metrics": custom_metrics,
                "locust_stats": locust_stats,
            },
            f,
            indent=4,
        )

    task_logger.debug(f"Final aggregated metrics: {custom_metrics}")


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
        self.task_logger = GlobalStateManager.get_task_logger(global_config.task_id)

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
                global_config, GlobalStateManager.get_task_logger(global_config.task_id)
            )
        return cls._shared_request_handler

    @classmethod
    def _get_stream_handler(cls):
        """Get or create shared stream handler."""
        if cls._shared_stream_handler is None:
            global_config = get_global_config()
            cls._shared_stream_handler = StreamHandler(
                global_config, GlobalStateManager.get_task_logger(global_config.task_id)
            )
        return cls._shared_stream_handler

    def _configure_ssl_settings(self):
        """Configure SSL settings for FastHttpUser."""
        global_config = get_global_config()

        try:
            # Set skip SSL certificate verification (equivalent to requests verify=False)
            if hasattr(self.client, "verify"):
                self.client.verify = False

            ssl_context = self._get_ssl_context()
            if ssl_context:
                if hasattr(self.client, "ssl_options"):
                    self.client.ssl_options = {"ssl_context": ssl_context}
                elif hasattr(self.client, "_client"):
                    # legacy version fallback
                    try:
                        self.client._client.ssl_options = {"ssl_context": ssl_context}
                    except Exception:
                        pass
            # only set insecure when you want to skip server certificate verification
            if hasattr(self.client, "insecure"):
                self.client.insecure = True

        except Exception as e:
            self.task_logger.warning(f"Failed to configure SSL settings: {e}")
            # Continue execution, do not interrupt because of SSL configuration failure

    def _get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create and configure SSL context."""
        # Reuse globally built SSL context to avoid per-user overhead
        ssl_context = GlobalStateManager.get_ssl_context()
        return ssl_context

    def _configure_legacy_ssl(self):
        """Configure SSL for older FastHttp versions."""
        global_config = get_global_config()

        if hasattr(self.client, "_client"):
            # Some FastHttp versions wrap the underlying client
            if hasattr(self.client._client, "verify"):
                self.client._client.verify = False

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

            user_prompt = user_prompt or ""
            reasoning_content = reasoning_content or ""
            model_output = model_output or ""

            # Prefer usage_tokens if available and valid
            completion_tokens = 0
            total_tokens = 0

            # Check if we have valid usage_tokens with required fields
            if (
                usage_tokens
                and isinstance(usage_tokens, dict)
                and usage_tokens.get("completion_tokens") is not None
                and usage_tokens.get("total_tokens") is not None
            ):
                # Use tokens directly from API response (preferred for both streaming and non-streaming)
                completion_tokens = usage_tokens.get("completion_tokens", 0) or 0
                total_tokens = usage_tokens.get("total_tokens", 0) or 0
                self.task_logger.debug(
                    f"Using API-provided usage tokens: completion={completion_tokens}, total={total_tokens}"
                )
            else:
                # Fallback: manual counting if usage_tokens are missing or incomplete
                self.task_logger.debug(
                    "API usage tokens unavailable or incomplete, falling back to manual token counting"
                )
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
            if (
                completion_tokens
                and isinstance(completion_tokens, (int, float))
                and completion_tokens > 0
            ):
                global_task_queue["completion_tokens_queue"].put(int(completion_tokens))
            if (
                total_tokens
                and isinstance(total_tokens, (int, float))
                and total_tokens > 0
            ):
                global_task_queue["all_tokens_queue"].put(int(total_tokens))

            # REMOVED: incremental_metrics sending logic
            # This was causing the inconsistency between worker metrics and incremental metrics
            # In multi-process mode, we now rely solely on worker metrics calculated via calculate_custom_metrics()
            # In single-process mode, we rely on master's local metrics calculated via calculate_custom_metrics()

        except Exception as e:
            self.task_logger.error(f"Failed to count tokens: {e}", exc_info=True)

    @task
    def chat_request(self):
        """Main Locust task that executes a single chat request."""
        global_config = get_global_config()
        # Check if we need dataset mode (avoid unnecessary queue operations)
        needs_dataset = bool(
            global_config.test_data and global_config.test_data.strip()
        )
        prompt_data = self.get_next_prompt() if needs_dataset else None
        base_request_kwargs, user_prompt = self.request_handler.prepare_request_kwargs(
            prompt_data
        )
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
                reasoning_content, model_output, usage_tokens = (
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
            self.task_logger.error(f"Unhandled exception in chat_request: {e}")
            # Record the failure event for unhandled exceptions with enhanced context
            try:
                response_time = (
                    (time.time() - start_time) * 1000 if start_time is not None else 0
                )
            except Exception:
                response_time = 0

            ErrorHandler.handle_general_exception(
                f"Unhandled exception in chat_request: {e}",
                self.task_logger,
                response=None,
                response_time=response_time,
                additional_context={
                    "stream_mode": global_config.stream_mode,
                    "api_path": global_config.api_path,
                    "prompt_preview": (
                        str(user_prompt)[:100] if user_prompt else "No prompt"
                    ),
                    "task_id": global_config.task_id,
                    "request_name": request_name,
                },
            )

        if reasoning_content or model_output or usage_tokens:
            self._log_token_counts(
                user_prompt or "", reasoning_content, model_output, usage_tokens
            )

    def stop(self, force=False):
        """
        Override the default stop method to handle duplicate stop attempts gracefully.
        This prevents the "stopping state" exception when Locust receives multiple stop signals.
        """
        global _shutdown_in_progress

        # If we're already in shutdown process, return gracefully
        if _shutdown_in_progress:
            return

        # Check if user is already in stopping state
        if hasattr(self, "_state") and self._state == "stopping":
            return

        try:
            # Call the parent stop method with error handling
            super().stop(force=force)
        except Exception as e:
            # Handle the specific "stopping state" exception
            error_msg = str(e).lower()
            if "stopping" in error_msg or "unexpected state" in error_msg:
                # Mark as stopped to prevent further attempts
                if hasattr(self, "_state"):
                    self._state = "stopped"
            else:
                # Re-raise unexpected exceptions
                self.task_logger.error(f"Unexpected error during User.stop(): {e}")
                raise
