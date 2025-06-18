"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os

# --- Task Status Constants ---
# These constants represent the various states a task can be in.
TASK_STATUS_CREATED = "created"
TASK_STATUS_LOCKED = "locked"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_STOPPING = "stopping"
TASK_STATUS_STOPPED = "stopped"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"


# --- Directory Paths ---
# Base directory of the project.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Directory of the performance testing engine.
ST_ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directory to store log files.
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_TASK_DIR = os.path.join(LOG_DIR, "task")
