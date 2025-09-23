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

# === LOCUST CONFIGURATION ===
LOCUST_STOP_TIMEOUT = 60
LOCUST_WAIT_TIMEOUT_BUFFER = 30

# === DATA VALIDATION ===
MAX_QUEUE_SIZE = 10000

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
    # locust
    "LOCUST_STOP_TIMEOUT",
    "LOCUST_WAIT_TIMEOUT_BUFFER",
    # sensitive
    "SENSITIVE_KEYS",
]
