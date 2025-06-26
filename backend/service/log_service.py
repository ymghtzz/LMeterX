"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os.path
from collections import deque

from starlette.responses import JSONResponse

from config.config import LOG_DIR
from model.log import LogContentResponse
from utils.logger import be_logger as logger


def get_last_n_lines(file_path: str, n: int = 100) -> str:
    """
    Reads the last N lines from a file by seeking from the end.
    This method is more efficient for large files as it avoids reading the whole file.

    Args:
        file_path: The path to the file.
        n: The number of lines to retrieve.

    Returns:
        A string containing the last N lines. Returns an empty string on failure.
    """
    try:
        with open(file_path, "rb") as f:
            # Move to the end of the file
            f.seek(0, os.SEEK_END)
            block_size = 1024
            lines_found: deque[str] = deque()

            while f.tell() > 0 and len(lines_found) <= n:
                # Calculate the position and size of the next block to read
                seek_step = min(block_size, f.tell())
                f.seek(-seek_step, os.SEEK_CUR)
                chunk = f.read(seek_step)
                f.seek(-seek_step, os.SEEK_CUR)

                # Prepend to any partial line from previous chunk
                if lines_found:
                    lines_found[0] = chunk.decode("utf-8", "ignore") + lines_found[0]
                else:
                    lines_found.append(chunk.decode("utf-8", "ignore"))

                # Split into lines
                split_lines = lines_found[0].splitlines()

                # If we have more than one line, the first one is partial
                if len(split_lines) > 1:
                    lines_found[0] = split_lines.pop(0)
                    for line in reversed(split_lines):
                        lines_found.insert(1, line)

                if f.tell() == 0:
                    break

            return "\n".join(list(lines_found)[-n:])
    except Exception as e:
        logger.error(f"Failed to read log file: {str(e)}")
        return ""


def read_local_file(log_file_path: str, tail: int, offset: int) -> str:
    """
    Reads content from a local file, either the tail or from a specific offset.

    Args:
        log_file_path: The path to the log file.
        tail: The number of lines to read from the end. If 0, reads from offset.
        offset: The byte offset to start reading from. Used only if tail is 0.

    Returns:
        The content of the file as a string.
    """
    if tail == 0:
        with open(log_file_path, "r", encoding="utf-8") as f:
            if offset > 0:
                f.seek(offset)
            content = f.read()
    else:
        content = get_last_n_lines(file_path=log_file_path, n=tail)
    return content


async def get_service_log_svc(service_name: str, offset: int, tail: int):
    """
    Service function to get the log content for a given service name.

    It constructs the log file path, checks for its existence, and reads the content
    based on the offset and tail parameters.

    Args:
        service_name: The name of the service (e.g., "backend").
        offset: The byte offset to start reading from.
        tail: The number of lines to read from the end of the file.

    Returns:
        A `LogContentResponse` object on success, or a `JSONResponse` with an error
        message on failure.
    """
    if not service_name:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": "Service name cannot be empty"},
        )

    log_file_path = os.path.join(LOG_DIR, f"{service_name}.log")

    if not os.path.exists(log_file_path):
        logger.warning(f"Log file not found: {log_file_path}")
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "error": f"Log file for service '{service_name}' not found",
            },
        )
    try:
        content = read_local_file(log_file_path, tail, offset)
        file_size = os.path.getsize(log_file_path)
        return LogContentResponse(content=content, file_size=file_size)
    except Exception as e:
        logger.error(f"Failed to read log file {log_file_path}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": "Failed to read log file"},
        )


async def get_task_log_svc(task_id: str, offset: int, tail: int):
    """
    Service function to get the log content for a given task ID.

    It constructs the log file path, checks for its existence, and reads the content
    based on the offset and tail parameters.
    """
    if not task_id:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": "Task ID cannot be empty"},
        )

    log_file_path = os.path.join(LOG_DIR, "task", f"task_{task_id}.log")

    if not os.path.exists(log_file_path):
        logger.warning(f"Log file not found: {log_file_path}")
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "error": f"Log file for task '{task_id}' not found at {log_file_path}",
            },
        )

    try:
        content = read_local_file(log_file_path, tail, offset)
        file_size = os.path.getsize(log_file_path)
        return LogContentResponse(content=content, file_size=file_size)
    except Exception as e:
        logger.error(f"Failed to read log file {log_file_path}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": "Failed to read log file"},
        )
