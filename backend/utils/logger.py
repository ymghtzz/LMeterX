"""Logger configuration for LLMeter Backend.

Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os
import sys

from loguru import logger

from config.config import LOG_DIR

# --- Logger Configuration ---

# Remove the default logger configuration to avoid duplicate output.
logger.remove()

# Check if we're in testing environment
if not os.environ.get("TESTING"):
    # Ensure the log directory exists.
    os.makedirs(LOG_DIR, exist_ok=True)

    # Configure file logging only if not in testing mode.
    logger.add(
        os.path.join(LOG_DIR, "backend.log"),
        rotation="5 MB",
        retention="10 days",
        compression="zip",
        encoding="utf-8",
        level="INFO",
        backtrace=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {file}:{line} | {message}",  # noqa: E501
    )

# Configure console logging.
logger.add(
    sys.stdout,
    level="INFO",
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",  # noqa: E501
)

be_logger = logger
