"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os.path

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
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            # For small files, just read all and return last n lines
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            # If file is small (< 50KB), read all lines and return last n
            if file_size < 50 * 1024:
                f.seek(0)
                all_lines = f.readlines()
                return "".join(all_lines[-n:]) if all_lines else ""

            # For larger files, use a more reliable approach
            # Start from end and read backwards in larger chunks
            buffer_size = 8192
            lines: list[str] = []
            buffer = ""
            position = file_size

            while position > 0 and len(lines) < n:
                # Calculate chunk size to read
                chunk_size = min(buffer_size, position)
                position -= chunk_size

                # Read chunk from current position
                f.seek(position)
                chunk = f.read(chunk_size)

                # Prepend chunk to buffer
                buffer = chunk + buffer

                # Split buffer into lines
                lines_in_buffer = buffer.split("\n")

                # Keep the first part (might be incomplete line) in buffer
                buffer = lines_in_buffer[0]

                # Add complete lines to our lines list (in reverse order since we're reading backwards)
                for line in reversed(lines_in_buffer[1:]):
                    lines.insert(0, line)
                    if len(lines) >= n:
                        break

                # If we've reached the beginning of file, add the remaining buffer as a line
                if position == 0 and buffer:
                    lines.insert(0, buffer)

            # Take last n lines and join them with newlines
            result_lines = lines[-n:] if len(lines) > n else lines
            return "\n".join(result_lines) + (
                "\n" if result_lines and not result_lines[-1].endswith("\n") else ""
            )

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
