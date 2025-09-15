"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.

Enhanced event handler for robust multiprocess communication.
"""

import os
import threading
import time
from collections import defaultdict
from typing import Any, Dict, Optional, Set

from locust import events

from engine.core import GlobalStateManager
from engine.process_manager import get_multiprocess_manager
from utils.logger import logger


class EnhancedEventHandler:
    """Enhanced event handler with robust worker management."""

    def __init__(self):
        self._message_handlers = {}
        self._worker_confirmations: Set[str] = set()
        self._metrics_received: Dict[str, Dict[str, Any]] = {}
        self._request_ids: Set[str] = set()  # Track request IDs for deduplication
        self._lock = threading.RLock()
        self._cleanup_interval = 30.0  # seconds
        self._last_cleanup = time.time()
        # Worker registry for this event handler
        self._worker_registry: Dict[str, Dict[str, Any]] = {}

    def register_worker_handlers(self, environment):
        """Register enhanced worker message handlers."""
        task_id = os.environ.get("TASK_ID", "unknown")
        task_logger = GlobalStateManager.get_task_logger(task_id)

        try:
            from locust.runners import WorkerRunner

            is_worker = isinstance(environment.runner, WorkerRunner)
        except ImportError:
            is_worker = "WorkerRunner" in str(type(environment.runner))

        if is_worker:
            self._register_worker_handlers(environment, task_logger)
        else:
            self._register_master_handlers(environment, task_logger)

    def _register_worker_handlers(self, environment, task_logger):
        """Register worker-side message handlers."""
        worker_pid = os.getpid()
        worker_id = f"worker_{worker_pid}_{int(time.time())}"

        # Register worker locally
        self._register_worker(worker_id, worker_pid)

        def on_master_request(environment, msg, **_):
            """Handle master requests for metrics."""
            try:
                if msg.type == "request_metrics":
                    self._send_worker_metrics(environment, worker_id, task_logger)
                elif msg.type == "worker_heartbeat":
                    self._send_worker_heartbeat(environment, worker_id, task_logger)
            except Exception as e:
                task_logger.error(f"Error handling master request: {e}")

        try:
            environment.runner.register_message("request_metrics", on_master_request)
            environment.runner.register_message("worker_heartbeat", on_master_request)
            task_logger.info(
                f"Worker {worker_id} (PID: {worker_pid}) registered message handlers"
            )
        except Exception as e:
            task_logger.error(f"Failed to register worker message handlers: {e}")

    def _register_master_handlers(self, environment, task_logger):
        """Register master-side message handlers."""
        master_pid = os.getpid()

        # Initialize master-side tracking
        environment.worker_metrics_list = []
        environment.worker_confirmations = set()
        environment.worker_registry = {}
        environment.worker_metrics_count = {}

        def on_worker_message(environment, msg, **_):
            """Handle worker messages with enhanced deduplication."""
            try:
                if msg.type == "worker_custom_metrics":
                    self._handle_worker_metrics(environment, msg, task_logger)
                elif msg.type == "worker_metrics_sent":
                    self._handle_worker_confirmation(environment, msg, task_logger)
                elif msg.type == "worker_heartbeat_response":
                    self._handle_worker_heartbeat(environment, msg, task_logger)
                else:
                    task_logger.debug(f"Received unknown message type: {msg.type}")
            except Exception as e:
                task_logger.error(f"Error processing worker message: {e}")

        try:
            environment.runner.register_message(
                "worker_custom_metrics", on_worker_message
            )
            environment.runner.register_message(
                "worker_metrics_sent", on_worker_message
            )
            environment.runner.register_message(
                "worker_heartbeat_response", on_worker_message
            )
            task_logger.info(
                f"Master {master_pid} registered enhanced message handlers"
            )
        except Exception as e:
            task_logger.error(f"Failed to register master message handlers: {e}")

    def _register_worker(self, worker_id: str, worker_pid: int) -> None:
        """Register a worker locally."""
        with self._lock:
            self._worker_registry[worker_id] = {
                "pid": worker_pid,
                "registered_at": time.time(),
                "last_heartbeat": time.time(),
                "metrics_count": 0,
            }

    def _unregister_worker(self, worker_id: str) -> None:
        """Unregister a worker locally."""
        with self._lock:
            self._worker_registry.pop(worker_id, None)

    def _update_worker_metrics(self, worker_id: str, metrics: Dict[str, Any]) -> None:
        """Update worker metrics locally."""
        with self._lock:
            if worker_id in self._worker_registry:
                self._worker_registry[worker_id]["last_metrics"] = metrics
                self._worker_registry[worker_id]["metrics_count"] += 1

    def _is_worker_registered(self, worker_id: str) -> bool:
        """Check if worker is registered locally."""
        with self._lock:
            return worker_id in self._worker_registry

    def _send_worker_metrics(self, environment, worker_id: str, task_logger):
        """Send worker metrics to master."""
        try:
            from typing import cast

            from utils.common import calculate_custom_metrics

            global_task_queue = GlobalStateManager.get_global_task_queue()
            start_time = GlobalStateManager.get_start_time()
            end_time = time.time()
            execution_time = float((end_time - start_time) if start_time else 0)

            custom_metrics = calculate_custom_metrics(
                os.environ.get("TASK_ID", "unknown"),
                cast(Dict[str, Any], global_task_queue),
                execution_time,
            )

            # Add worker identification
            worker_metrics = {
                **custom_metrics,
                "worker_id": worker_id,
                "pid": os.getpid(),
                "request_id": f"{worker_id}_{int(time.time() * 1000)}",
                "timestamp": time.time(),
            }

            # Update local worker metrics
            self._update_worker_metrics(worker_id, worker_metrics)

            # Send to master
            environment.runner.send_message("worker_custom_metrics", worker_metrics)
            environment.runner.send_message(
                "worker_metrics_sent",
                {"worker_id": worker_id, "pid": os.getpid(), "timestamp": time.time()},
            )

            task_logger.debug(f"Worker {worker_id} sent metrics to master")

        except Exception as e:
            task_logger.error(f"Failed to send worker metrics: {e}")

    def _send_worker_heartbeat(self, environment, worker_id: str, task_logger):
        """Send worker heartbeat to master."""
        try:
            heartbeat_data = {
                "worker_id": worker_id,
                "pid": os.getpid(),
                "timestamp": time.time(),
                "status": "alive",
            }

            environment.runner.send_message("worker_heartbeat_response", heartbeat_data)
            task_logger.debug(f"Worker {worker_id} sent heartbeat")

        except Exception as e:
            task_logger.error(f"Failed to send worker heartbeat: {e}")

    def _handle_worker_metrics(self, environment, msg, task_logger):
        """Handle worker metrics with enhanced deduplication."""
        try:
            worker_id = msg.data.get(
                "worker_id", f"unknown_{msg.data.get('pid', 'unknown')}"
            )
            request_id = msg.data.get(
                "request_id", f"{worker_id}_{int(time.time() * 1000)}"
            )
            pid = msg.data.get("pid", "unknown")

            with self._lock:
                # Enhanced deduplication using request_id
                if request_id in self._request_ids:
                    task_logger.debug(
                        f"Duplicate metrics ignored from worker {worker_id} (request_id: {request_id})"
                    )
                    return

                self._request_ids.add(request_id)

                # Store metrics
                self._metrics_received[request_id] = {
                    "worker_id": worker_id,
                    "pid": pid,
                    "timestamp": time.time(),
                    "data": msg.data,
                }

                environment.worker_metrics_list.append(msg.data)

                # Update worker registry
                if worker_id not in environment.worker_registry:
                    environment.worker_registry[worker_id] = {
                        "first_seen": time.time(),
                        "metrics_count": 0,
                        "pid": pid,
                    }

                environment.worker_registry[worker_id]["metrics_count"] += 1
                environment.worker_metrics_count[worker_id] = (
                    environment.worker_registry[worker_id]["metrics_count"]
                )

                task_logger.debug(
                    f"Master received metrics from worker {worker_id} (request_id: {request_id})"
                )

        except Exception as e:
            task_logger.error(f"Error handling worker metrics: {e}")

    def _handle_worker_confirmation(self, environment, msg, task_logger):
        """Handle worker confirmation messages."""
        try:
            worker_id = msg.data.get(
                "worker_id", f"unknown_{msg.data.get('pid', 'unknown')}"
            )
            pid = msg.data.get("pid", "unknown")

            environment.worker_confirmations.add(worker_id)
            task_logger.debug(
                f"Master received confirmation from worker {worker_id} (PID: {pid})"
            )

        except Exception as e:
            task_logger.error(f"Error handling worker confirmation: {e}")

    def _handle_worker_heartbeat(self, environment, msg, task_logger):
        """Handle worker heartbeat messages."""
        try:
            worker_id = msg.data.get(
                "worker_id", f"unknown_{msg.data.get('pid', 'unknown')}"
            )
            pid = msg.data.get("pid", "unknown")

            # Update worker heartbeat locally
            with self._lock:
                if worker_id in self._worker_registry:
                    self._worker_registry[worker_id]["last_heartbeat"] = time.time()

            task_logger.debug(
                f"Master received heartbeat from worker {worker_id} (PID: {pid})"
            )

        except Exception as e:
            task_logger.error(f"Error handling worker heartbeat: {e}")

    def request_worker_metrics(self, environment, task_logger):
        """Request metrics from all workers."""
        try:
            if hasattr(environment.runner, "send_message"):
                task_logger.debug("Requesting metrics from all workers...")
                environment.runner.send_message(
                    "request_metrics",
                    {"request": "final_metrics", "timestamp": time.time()},
                )

                # Also send heartbeat request
                environment.runner.send_message(
                    "worker_heartbeat",
                    {"request": "heartbeat", "timestamp": time.time()},
                )

        except Exception as e:
            task_logger.warning(f"Failed to request worker metrics: {e}")

    def cleanup_old_requests(self):
        """Clean up old request IDs to prevent memory leaks."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        with self._lock:
            # Remove old request IDs (older than 1 hour)
            old_requests = [
                req_id
                for req_id, data in self._metrics_received.items()
                if current_time - data["timestamp"] > 3600
            ]

            for req_id in old_requests:
                self._request_ids.discard(req_id)
                del self._metrics_received[req_id]

            if old_requests:
                logger.debug(f"Cleaned up {len(old_requests)} old request IDs")

            self._last_cleanup = current_time


# Global event handler instance
_event_handler = EnhancedEventHandler()


def get_event_handler() -> EnhancedEventHandler:
    """Get the global event handler instance."""
    return _event_handler


def register_enhanced_handlers(environment):
    """Register enhanced event handlers."""
    _event_handler.register_worker_handlers(environment)


def request_worker_metrics(environment, task_logger):
    """Request metrics from all workers."""
    _event_handler.request_worker_metrics(environment, task_logger)


def cleanup_old_requests():
    """Clean up old request data."""
    _event_handler.cleanup_old_requests()
