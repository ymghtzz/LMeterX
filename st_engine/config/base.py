"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os

# === BASE PATHS ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ST_ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# === LOG PATHS ===
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_TASK_DIR = os.path.join(LOG_DIR, "task")

# === DATA PATHS ===
DATA_DIR = os.path.join(ST_ENGINE_DIR, "data")
PROMPTS_DIR = os.path.join(DATA_DIR, "prompts")
IMAGES_DIR = os.path.join(DATA_DIR, "pic")

# === UPLOAD PATHS ===
# Handle different environments: Docker vs local development
if os.path.exists("/app") and os.getcwd().startswith("/app"):
    # Docker environment: use /app/upload_files
    UPLOAD_FOLDER = "/app/upload_files"
else:
    # Local development: use project root upload_files
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "upload_files")

# === HTTP CONSTANTS ===
HTTP_OK = 200
DEFAULT_TIMEOUT = 180
DEFAULT_WAIT_TIME_MIN = 1
DEFAULT_WAIT_TIME_MAX = 3

# === DEFAULT VALUES ===
DEFAULT_PROMPT = "Tell me about the history of Artificial Intelligence."
DEFAULT_API_PATH = "/chat/completions"
DEFAULT_CONTENT_TYPE = "application/json"

# === STREAMING CONSTANTS ===
STREAM_END_MARKERS = ["[DONE]", "[END]", "DONE", "END"]
STREAM_ERROR_MARKERS = ["[ERROR]", "ERROR"]
MAX_CHUNK_SIZE = 1000  # Maximum chunk size to process
MAX_OUTPUT_LENGTH = 1000000  # Maximum output length to prevent memory issues

# === STREAMING PERFORMANCE ===
STREAM_BUFFER_SIZE = 2048  # Stream read buffer size
JSON_BUFFER_MAX_SIZE = 10240  # Maximum JSON buffer size before discarding
INCOMPLETE_JSON_RETRY_COUNT = 3  # Max retries for incomplete JSON chunks
STREAM_DEBUG_ENABLED = False  # Enable detailed stream debugging (impacts performance)

# === STREAMING RESILIENCE ===
STREAM_READ_TIMEOUT = 30  # Timeout for individual stream read operations (seconds)
STREAM_MAX_RETRIES = 3  # Maximum retries for failed stream reads
STREAM_RETRY_DELAY_BASE = 0.5  # Base delay for exponential backoff (seconds)
STREAM_RETRY_DELAY_MAX = 2.0  # Maximum retry delay (seconds)
STREAM_CHUNK_TIMEOUT_THRESHOLD = (
    300  # Max time since last successful chunk (seconds) - Increased for long responses
)

# === HIGH CONCURRENCY OPTIMIZATIONS ===
MULTIPROCESS_CHUNK_TIMEOUT_THRESHOLD = (
    600  # Extended timeout for multi-process scenarios (seconds)
)
MULTIPROCESS_MAX_RETRIES = 5  # More retries for multi-process scenarios
MULTIPROCESS_RETRY_DELAY_MAX = 5.0  # Longer delays for multi-process scenarios
STREAM_ADAPTIVE_TIMEOUT_ENABLED = (
    True  # Enable adaptive timeout based on response length
)

# === LOCUST CONFIGURATION ===
LOCUST_STOP_TIMEOUT = 99
LOCUST_WAIT_TIMEOUT_BUFFER = 30

# === TOKENIZATION ===
# Token estimation
DEFAULT_TOKEN_RATIO = 4  # chars per token estimation
TOKENIZER_CACHE_SIZE = 128
TOKEN_COUNT_CACHE_SIZE = 8192

# === DATA VALIDATION ===
MAX_QUEUE_SIZE = 10000
MIN_PROMPT_LENGTH = 1

# === SENSITIVE DATA ===
SENSITIVE_KEYS = ["authorization"]

__all__ = [
    # paths
    "BASE_DIR",
    "ST_ENGINE_DIR",
    "LOG_DIR",
    "LOG_TASK_DIR",
    "DATA_DIR",
    "PROMPTS_DIR",
    "IMAGES_DIR",
    "UPLOAD_FOLDER",
    # http
    "HTTP_OK",
    "DEFAULT_TIMEOUT",
    "DEFAULT_WAIT_TIME_MIN",
    "DEFAULT_WAIT_TIME_MAX",
    "DEFAULT_PROMPT",
    "DEFAULT_API_PATH",
    "DEFAULT_CONTENT_TYPE",
    # streaming
    "STREAM_END_MARKERS",
    "STREAM_ERROR_MARKERS",
    "MAX_CHUNK_SIZE",
    "MAX_OUTPUT_LENGTH",
    "STREAM_BUFFER_SIZE",
    "JSON_BUFFER_MAX_SIZE",
    "INCOMPLETE_JSON_RETRY_COUNT",
    "STREAM_DEBUG_ENABLED",
    "STREAM_READ_TIMEOUT",
    "STREAM_MAX_RETRIES",
    "STREAM_RETRY_DELAY_BASE",
    "STREAM_RETRY_DELAY_MAX",
    "STREAM_CHUNK_TIMEOUT_THRESHOLD",
    "MULTIPROCESS_CHUNK_TIMEOUT_THRESHOLD",
    "MULTIPROCESS_MAX_RETRIES",
    "MULTIPROCESS_RETRY_DELAY_MAX",
    "STREAM_ADAPTIVE_TIMEOUT_ENABLED",
    # locust
    "LOCUST_STOP_TIMEOUT",
    "LOCUST_WAIT_TIMEOUT_BUFFER",
    # tokenization
    "DEFAULT_TOKEN_RATIO",
    "TOKENIZER_CACHE_SIZE",
    "TOKEN_COUNT_CACHE_SIZE",
    "MAX_QUEUE_SIZE",
    "MIN_PROMPT_LENGTH",
    # sensitive
    "SENSITIVE_KEYS",
]
