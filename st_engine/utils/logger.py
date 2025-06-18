"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os
import sys

from loguru import logger

from config.config import LOG_DIR, LOG_TASK_DIR

# --- Logger Configuration ---

# Ensure the log directory exists.

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(LOG_TASK_DIR, exist_ok=True)


# Remove the default logger to prevent duplicate output.
logger.remove()


def is_system_log(record):
    """Filter for system logs (not task-related)."""
    return "task_id" not in record["extra"]


# Configure the file logger for system logs
logger.add(
    os.path.join(LOG_DIR, "engine.log"),  # Path to the log file.
    rotation="5 MB",  # Rotates the log file when it reaches 5 MB.
    retention="10 days",  # Retains log files for 10 days.
    compression="zip",  # Compresses rotated log files.
    encoding="utf-8",  # Sets the file encoding.
    level="INFO",  # Minimum log level to be written to the file.
    backtrace=False,  # Do not show the full stack trace.
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {file}:{line} | {message}",
    filter=is_system_log,  # Only log records without 'task_id'
    # enqueue=True,  # Asynchronous writing.
)

# Configure the console logger.
logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
)


def add_task_log_sink(task_id: str) -> int:
    """
    Adds a specific log sink for a given task ID.
    """
    task_log_file = os.path.join(LOG_TASK_DIR, f"task_{task_id}.log")

    def is_current_task_log(record):
        return "task_id" in record["extra"] and record["extra"]["task_id"] == task_id

    handler_id = logger.add(
        task_log_file,
        rotation="5 MB",
        retention="10 days",
        compression="zip",
        encoding="utf-8",
        level="INFO",
        backtrace=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {file}:{line} | {message}",
        filter=is_current_task_log,
    )
    return handler_id


def remove_task_log_sink(handler_id: int):
    """
    Removes a log sink by its handler ID.
    """
    logger.remove(handler_id)


st_logger = logger
