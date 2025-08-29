"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os

# Get the absolute path of the project's root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get the absolute path of the backend directory
BE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directory for storing log files
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_TASK_DIR = os.path.join(LOG_DIR, "task")

# Directory for storing uploaded files
# Handle different environments: Docker vs local development
if os.path.exists("/app") and os.getcwd().startswith("/app"):
    # Docker environment: use /app/upload_files (matches docker-compose volume mapping)
    UPLOAD_FOLDER = "/app/upload_files"
else:
    # Local development: use project root upload_files
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "upload_files")

# File upload security configuration
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
MAX_FILENAME_LENGTH = 255
MAX_TASK_ID_LENGTH = 64

# Allowed file extensions by type
ALLOWED_EXTENSIONS = {
    "cert": {"crt", "pem", "key"},
    "dataset": {"json", "csv", "txt", "jsonl"},
}

# Allowed MIME types by file type
ALLOWED_MIME_TYPES = {
    "cert": {
        "application/x-x509-ca-cert",
        "application/x-pem-file",
        "text/plain",
        "application/octet-stream",
        "application/pem-certificate-chain",
    },
    "dataset": {
        "application/json",
        "text/plain",
        "text/csv",
        "application/jsonl",
        "text/jsonl",
        "application/x-jsonl",
        "application/octet-stream",
    },
}

# Dangerous patterns for path traversal detection
DANGEROUS_PATTERNS = [
    r"\.\.",  # .. (directory traversal)
    r"/",  # / (absolute path)
    r"\\",  # \ (Windows path separator)
    r"%",  # URL encoding
    r"<",  # HTML/XML injection
    r">",
    r'"',
    r"'",
    r"&",
    r"\|",  # Command injection (escaped pipe)
    r";",
    r"`",
    r"\$",  # Escaped dollar sign
    r"\(",  # Escaped parentheses
    r"\)",
    r"\[",  # Escaped brackets
    r"\]",
    r"\{",  # Escaped braces
    r"\}",
]

# Task ID validation pattern
TASK_ID_PATTERN = r"^[a-zA-Z0-9_-]+$"
