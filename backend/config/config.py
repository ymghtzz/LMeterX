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
UPLOAD_FOLDER = os.path.join(BE_DIR, "upload_files")
