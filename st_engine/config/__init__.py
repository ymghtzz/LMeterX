"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

# base
from .base import *

# business
from .business import *

# multiprocess
from .multiprocess import *

# backward compatibility
__all__ = [
    # base
    "BASE_DIR",
    "ST_ENGINE_DIR",
    "LOG_DIR",
    "LOG_TASK_DIR",
    "DATA_DIR",
    "PROMPTS_DIR",
    "IMAGES_DIR",
    "UPLOAD_FOLDER",
    "HTTP_OK",
    "DEFAULT_TIMEOUT",
    "DEFAULT_WAIT_TIME_MIN",
    "DEFAULT_WAIT_TIME_MAX",
    "DEFAULT_PROMPT",
    "DEFAULT_API_PATH",
    "DEFAULT_CONTENT_TYPE",
    "STREAM_END_MARKERS",
    "STREAM_ERROR_MARKERS",
    "MAX_CHUNK_SIZE",
    "MAX_OUTPUT_LENGTH",
    "LOCUST_STOP_TIMEOUT",
    "LOCUST_WAIT_TIMEOUT_BUFFER",
    "DEFAULT_TOKEN_RATIO",
    "TOKENIZER_CACHE_SIZE",
    "TOKEN_COUNT_CACHE_SIZE",
    "MAX_QUEUE_SIZE",
    "MIN_PROMPT_LENGTH",
    "SENSITIVE_KEYS",
    # multiprocess
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
    # business
    "TASK_STATUS_CREATED",
    "TASK_STATUS_LOCKED",
    "TASK_STATUS_RUNNING",
    "TASK_STATUS_STOPPING",
    "TASK_STATUS_STOPPED",
    "TASK_STATUS_COMPLETED",
    "TASK_STATUS_FAILED",
    "TASK_STATUS_FAILED_REQUESTS",
    "METRIC_TTFOT",
    "METRIC_TTFRT",
    "METRIC_TTRC",
    "METRIC_TTOC",
    "METRIC_TTT",
]
