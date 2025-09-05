"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os
from functools import lru_cache
from typing import Any, Dict, Optional


class MultiprocessingConfig:
    """Multi-process configuration management class, manage all configurations and cache results to improve performance."""

    def __init__(self) -> None:
        self._config_cache: Optional[Dict[str, Any]] = None
        self._cpu_count_cache: Optional[int] = None
        self._is_docker_cache: Optional[bool] = None

    @property
    def config(self) -> Dict[str, Any]:
        """Get multiprocessing configuration, use cache to avoid repeated reading of environment variables."""
        if self._config_cache is None:
            self._config_cache = {
                "enable_multiprocess": os.environ.get(
                    "ENABLE_MULTIPROCESS", "auto"
                ).lower(),
                "cpu_cores": os.environ.get("LOCUST_CPU_CORES", ""),
                "processes": os.environ.get("LOCUST_PROCESSES", ""),
                "multiprocess_threshold": int(
                    os.environ.get("MULTIPROCESS_THRESHOLD", "5")
                ),
                "min_users_per_process": int(
                    os.environ.get("MIN_USERS_PER_PROCESS", "5")
                ),
                "force_single_process": os.environ.get(
                    "FORCE_SINGLE_PROCESS", "false"
                ).lower()
                == "true",
                "manager_timeout": int(os.environ.get("MANAGER_TIMEOUT", "30")),
                "fallback_queue_type": os.environ.get(
                    "FALLBACK_QUEUE_TYPE", "gevent"
                ).lower(),
            }
        return self._config_cache

    @property
    def cpu_count(self) -> int:
        """Get CPU core count, use cache to avoid repeated detection."""
        if self._cpu_count_cache is None:
            self._cpu_count_cache = self._detect_cpu_count()
        return self._cpu_count_cache

    @property
    def is_docker(self) -> bool:
        """Check if running in Docker environment, use cache to avoid repeated checks."""
        if self._is_docker_cache is None:
            self._is_docker_cache = (
                os.path.exists("/.dockerenv")
                or os.environ.get("DOCKER_CONTAINER") == "true"
            )
        return self._is_docker_cache

    def _detect_cpu_count(self) -> int:
        """Detect CPU core count."""
        # Use environment variable to specify CPU core count
        cpu_cores = self.config["cpu_cores"].strip()
        if cpu_cores and cpu_cores.replace(".", "").isdigit():
            return max(1, int(float(cpu_cores)))

        # Fallback to legacy LOCUST_PROCESSES for backward compatibility
        legacy_processes = self.config["processes"].strip()
        if legacy_processes and legacy_processes.isdigit():
            return max(1, int(legacy_processes))

        # Try system CPU detection
        try:
            import multiprocessing

            system_cpu_count = multiprocessing.cpu_count()

            # Respect container limits in Docker environment
            if self.is_docker:
                return min(system_cpu_count, 8)  # Limit to 8 processes for safety

            return system_cpu_count
        except (ImportError, NotImplementedError):
            return 1

    def should_enable_multiprocess(
        self, concurrent_users: int, cpu_count: Optional[int] = None
    ) -> bool:
        """Determine if multiprocessing should be enabled based on CPU count and concurrent users."""
        if cpu_count is None:
            cpu_count = self.cpu_count

        config = self.config

        # Force single process mode
        if config["force_single_process"]:
            return False

        # Check if explicitly disabled
        if config["enable_multiprocess"] in ("false", "0", "no"):
            return False

        # Multi-process requirements (hard constraints)
        if cpu_count <= 1:
            return False

        # Hard constraint: Concurrent users must be > threshold to enable multiprocessing
        if concurrent_users <= config["multiprocess_threshold"]:
            return False

        # If explicitly enabled and meets constraints, use multiprocessing
        if config["enable_multiprocess"] in ("true", "1", "yes"):
            return True

        # Automatic mode: Enable for high concurrent scenarios (checked above)
        return True

    def should_use_multiprocessing_manager(self) -> bool:
        """Determine if multiprocessing manager should be used."""
        config = MultiprocessingConfig()

        # Force single process mode
        if config.config["force_single_process"]:
            return False

        # Check if explicitly disabled
        if config.config["enable_multiprocess"] in ("false", "0", "no"):
            return False

        # Check if running in environment where multiprocessing might fail
        if config.is_docker:
            # More conservative in Docker
            return config.config["enable_multiprocess"] in ("true", "1", "yes")

        # Check if running in single process Locust
        if os.environ.get("LOCUST_PROCESSES", "1") == "1":
            return False

        # Check system resource limits
        if not config._check_system_resources():
            return False

        return True

    def _check_system_resources(self) -> bool:
        """Check if system resources meet multiprocessing requirements."""
        # Check file descriptor limit
        try:
            import resource

            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            if (
                soft < 1000
            ):  # If file descriptor limit is too low, disable multiprocessing
                return False
        except Exception:
            pass

        # Check memory availability
        try:
            import psutil

            memory = psutil.virtual_memory()
            if (
                memory.available < 500 * 1024 * 1024
            ):  # If available memory is less than 500MB
                return False
        except ImportError:
            pass

        return True

    def get_process_count(
        self, concurrent_users: int, cpu_count: Optional[int] = None
    ) -> int:
        """Get optimal process count for multiprocessing testing."""
        if cpu_count is None:
            cpu_count = self.cpu_count

        if not self.should_enable_multiprocess(concurrent_users, cpu_count):
            return 1

        # Calculate optimal process count based on concurrent users
        min_users_per_process = self.config["min_users_per_process"]
        max_processes_by_users = max(1, concurrent_users // min_users_per_process)

        # Use the minimum of CPU count and user-based limit
        return min(cpu_count, max_processes_by_users)


# Global configuration instance
_config = MultiprocessingConfig()


# === Public interface functions ===
def get_cpu_count() -> int:
    """Get CPU core count for multiprocessing testing."""
    return _config.cpu_count


def get_multiprocessing_config() -> Dict[str, Any]:
    """Get multiprocessing configuration from environment variables."""
    return _config.config.copy()


def should_enable_multiprocess(
    concurrent_users: int, cpu_count: Optional[int] = None
) -> bool:
    """Determine if multiprocessing should be enabled based on CPU count and concurrent users."""
    return _config.should_enable_multiprocess(concurrent_users, cpu_count)


def should_use_multiprocessing_manager() -> bool:
    """Determine if multiprocessing manager should be used."""
    return _config.should_use_multiprocessing_manager()


def get_process_count(concurrent_users: int, cpu_count: Optional[int] = None) -> int:
    """Get optimal process count for multiprocessing testing."""
    return _config.get_process_count(concurrent_users, cpu_count)


def get_fallback_queue_type() -> str:
    """Get fallback queue type when multiprocessing manager fails."""
    return _config.config["fallback_queue_type"]


# === multiprocess configuration constants ===
# Legacy compatibility - will be deprecated in future versions, replaced with dynamic calculation
DEFAULT_ENABLE_MULTIPROCESS = os.environ.get(
    "ENABLE_MULTIPROCESS", "auto"
).lower() not in ("false", "0", "no")

DEFAULT_PROCESS_COUNT = get_cpu_count() if DEFAULT_ENABLE_MULTIPROCESS else 1

# Performance tuning parameters, clearer names
MULTIPROCESS_THRESHOLD = int(
    os.environ.get("MULTIPROCESS_THRESHOLD", "5")
)  # Min users to enable multiprocess (must be > 1000)

MIN_USERS_PER_PROCESS = int(
    os.environ.get("MIN_USERS_PER_PROCESS", "5")
)  # Min users each process should handle (updated from 500)


__all__ = [
    "get_cpu_count",
    "get_multiprocessing_config",
    "should_enable_multiprocess",
    "should_use_multiprocessing_manager",
    "get_process_count",
    "get_fallback_queue_type",
    "DEFAULT_ENABLE_MULTIPROCESS",
    "DEFAULT_PROCESS_COUNT",
    "MULTIPROCESS_THRESHOLD",
    "MIN_USERS_PER_PROCESS",
]
