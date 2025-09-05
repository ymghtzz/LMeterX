"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import json
import os
import shutil
import subprocess  # nosec B404
import tempfile
import threading

from config.multiprocess import (
    get_cpu_count,
    get_process_count,
    should_enable_multiprocess,
)
from model.task import Task
from utils.common import mask_sensitive_command
from utils.logger import logger


class LocustRunner:
    """
    A class to manage the execution of Locust performance tests in a subprocess.

    Attributes:
        process_dict (dict): A dictionary to store running subprocesses,
                             mapping task IDs to process objects.
        base_dir (str): The base directory of the engine, used to locate the locustfile.
    """

    process_dict: dict[str, subprocess.Popen] = {}

    def __init__(self, base_dir):
        """
        Initializes the LocustRunner.

        Args:
            base_dir (str): The base directory of the engine.
        """
        self.base_dir = base_dir
        # Track processes that are currently being terminated to avoid duplicate signals
        self._terminating_processes = set()

    def run_locust_process(self, task: Task) -> dict:
        """
        Runs a Locust test as a separate process.

        Args:
            task (Task): The task object containing the test parameters.

        Returns:
            dict: A dictionary containing the results of the test execution,
                  including status, stdout, stderr, return code, and
                  the parsed Locust result JSON.
        """
        task_logger = logger.bind(task_id=task.id)
        try:
            cmd = self._build_locust_command(task)

            # Verify locustfile exists before executing
            locustfile_path = cmd[2]  # The -f argument value
            if not os.path.exists(locustfile_path):
                error_msg = f"Locustfile not found at path: {locustfile_path}"
                task_logger.error(error_msg)
                return {
                    "status": "FAILED",
                    "stdout": "",
                    "stderr": error_msg,
                    "return_code": -1,
                    "locust_result": {},
                }

            masked_cmd = mask_sensitive_command(cmd)
            task_logger.info(
                f"Task {task.id}, Executing Locust command: {' '.join(masked_cmd)}"
            )

            env = os.environ.copy()
            env.update({"TASK_ID": str(task.id)})

            process = subprocess.Popen(  # nosec B603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
                shell=False,
            )
            self.process_dict[str(task.id)] = process
            task_logger.info(f"Started Locust process {process.pid}.")

            stdout, stderr = self._capture_process_output(
                process, str(task.id), int(task.duration)
            )

            result_file = os.path.join(
                tempfile.gettempdir(), "locust_result", str(task.id), "result.json"
            )
            locust_result = self._load_locust_result(result_file, str(task.id))

            # Locust exit codes: 0 = success, 1 = test failures, >1 = locust error
            if process.returncode == 0:
                status = "COMPLETED"
                task_logger.info(
                    f"Locust process completed successfully with exit code {process.returncode}."
                )
            elif process.returncode == 1:
                status = "FAILED_REQUESTS"
                task_logger.warning(
                    f"Locust process completed with test failures (exit code {process.returncode})."
                )
            else:
                status = "FAILED"
                task_logger.error(
                    f"Locust process failed with return code {process.returncode}."
                )

            return {
                "status": status,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": process.returncode,
                "locust_result": locust_result,
            }
        except Exception as e:
            task_logger.exception(
                f"Task {task.id}, An error occurred while running the Locust process: {e}"
            )
            return {
                "status": "FAILED",
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "locust_result": {},
            }

    def _build_locust_command(self, task: Task) -> list:
        """
        Builds the command-line arguments for running Locust.

        Args:
            task (Task): The task object containing the test parameters.

        Returns:
            list: A list of command-line arguments for the subprocess.
        """
        # Fix the locustfile path - it should be in st_engine/engine/ directory
        locustfile_path = os.path.join(self.base_dir, "engine", "locustfile.py")
        command = [
            "locust",
            "-f",
            locustfile_path,
            "--host",
            task.target_host,
            "--users",
            str(task.concurrent_users),
            "--spawn-rate",
            str(task.spawn_rate),
            "--run-time",
            f"{task.duration}s",
            "--headless",
            "--only-summary",
            "--stop-timeout",
            "99",
            "--api_path",
            task.api_path or "/chat/completions",
            "--headers",
            task.headers,
            "--cookies",
            task.cookies or "{}",
            "--model_name",
            task.model or "",
            "--stream_mode",
            task.stream_mode,
            "--chat_type",
            str(task.chat_type or 0),
            "--task-id",
            task.id,
        ]

        # Add multi-process support if enabled and more than 1 process is configured
        cpu_count = get_cpu_count()
        concurrent_users = int(task.concurrent_users)
        process_count = get_process_count(concurrent_users, cpu_count)

        if (
            should_enable_multiprocess(concurrent_users, cpu_count)
            and process_count > 1
        ):
            command.extend(["--processes", str(process_count)])
            task_logger = logger.bind(task_id=task.id)
            task_logger.info(
                f"Enabling multi-process mode with {process_count} processes "
                f"(CPU cores: {cpu_count}, concurrent users: {concurrent_users})"
            )

        # Add custom request payload if specified
        if task.request_payload:
            command.extend(["--request_payload", task.request_payload])

        # Add field mapping if specified
        if task.field_mapping:
            command.extend(["--field_mapping", task.field_mapping])

        # Add api_path if specified
        if task.api_path:
            command.extend(["--api_path", task.api_path])

        # Add system prompt if specified
        if task.system_prompt:
            command.extend(["--system_prompt", task.system_prompt])

        # Add test_data if specified
        if task.test_data:
            command.extend(["--test_data", task.test_data])

        # Add certificate file parameters if they exist
        if task.cert_file:
            command.extend(["--cert_file", task.cert_file])

        if task.key_file:
            command.extend(["--key_file", task.key_file])

        return command

    def _capture_process_output(
        self, process: subprocess.Popen, task_id: str, task_duration_seconds: int
    ):
        """
        Captures the stdout and stderr from the running subprocess in real-time.

        This method uses separate threads to read the output pipes, preventing the
        application from blocking. It also implements a robust timeout and
        termination logic for the Locust process.

        Args:
            process (subprocess.Popen): The subprocess object.
            task_id (str): The ID of the task, used for logging.
            task_duration_seconds (int): The expected duration of the task.

        Returns:
            tuple[str, str]: A tuple containing the captured stdout and stderr as strings.
        """
        stdout: list[str] = []
        stderr: list[str] = []
        task_logger = logger.bind(task_id=task_id)

        def read_output(pipe, lines, stream_name):
            """Reads lines from a stream and appends them to a list."""
            buffer = ""
            while True:
                try:
                    # Read in larger chunks to reduce fragmentation
                    chunk = pipe.read(1024)
                    if not chunk:
                        break

                    buffer += chunk
                    # Process complete lines
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if line.strip():  # Only process non-empty lines
                            lines.append(line + "\n")

                            # Write raw locust output to task log file using raw=True to avoid formatting issues
                            task_logger.opt(raw=True).info(line + "\n")

                except Exception as e:
                    task_logger.error(f"Error reading {stream_name}: {e}")
                    break

            # Handle any remaining content in buffer
            if buffer.strip():
                lines.append(buffer)
                task_logger.opt(raw=True).info(buffer.rstrip() + "\n")

            pipe.close()

        stdout_thread = threading.Thread(
            target=read_output, args=(process.stdout, stdout, "stdout")
        )
        stderr_thread = threading.Thread(
            target=read_output, args=(process.stderr, stderr, "stderr")
        )

        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()

        # Calculate a generous timeout for the process to complete.
        # This includes the task duration, Locust's own stop timeout, and an extra buffer.
        locust_stop_timeout_config = 99
        wait_timeout_total = task_duration_seconds + locust_stop_timeout_config + 30
        task_logger.info(
            f"Waiting for Locust process {process.pid} to complete with a timeout of {wait_timeout_total} seconds."
        )

        try:
            process.wait(timeout=wait_timeout_total)
            task_logger.info(
                f"Locust process {process.pid} finished with return code {process.returncode}."
            )
        except subprocess.TimeoutExpired:
            task_logger.error(
                f"Locust process (PID: {process.pid}) "
                f"timed out after {wait_timeout_total} seconds. Terminating."
            )
            process.terminate()
            try:
                process.wait(timeout=10)
                task_logger.warning(
                    f"Locust process {process.pid} terminated with code {process.returncode}."
                )
            except subprocess.TimeoutExpired:
                task_logger.error(
                    f"Locust process {process.pid} did not terminate gracefully after 10s. Killing."
                )
                process.kill()
                process.wait()
                task_logger.error(
                    f"Locust process {process.pid} killed. Return code: {process.returncode}."
                )
            stderr.append(f"Locust process timed out and was terminated/killed.\n")
        except Exception as e:
            task_logger.exception(
                f"An error occurred while waiting for the Locust process {process.pid}: {e}"
            )

        # Wait for the output reading threads to finish.
        join_timeout = 10
        stdout_thread.join(timeout=join_timeout)
        stderr_thread.join(timeout=join_timeout)

        if stdout_thread.is_alive():
            task_logger.warning(
                f"Stdout reading thread for Locust process {process.pid} did not finish in {join_timeout}s."
            )
        if stderr_thread.is_alive():
            task_logger.warning(
                f"Stderr reading thread for Locust process {process.pid} did not finish in {join_timeout}s."
            )

        return "".join(stdout), "".join(stderr)

    def _load_locust_result(self, result_file: str, task_id: str):
        """
        Loads the Locust result JSON file.

        After loading, it cleans up the temporary result directory.

        Args:
            result_file (str): The path to the Locust result JSON file.
            task_id (str): The ID of the task, used for logging.

        Returns:
            dict: The parsed JSON data from the result file, or an empty dict if an error occurs.
        """
        task_logger = logger.bind(task_id=task_id)
        result_dir = os.path.dirname(result_file)
        try:
            if not os.path.exists(result_file):
                task_logger.error(f"Locust result file not found at {result_file}")
                return {}

            with open(result_file, "r") as f:
                result_data = json.load(f)

            task_logger.info(
                f"Successfully loaded Locust result file from {result_file}"
            )
            return result_data

        except json.JSONDecodeError:
            task_logger.error(
                f"Failed to decode JSON from {result_file}. The file might be corrupted or empty."
            )
            return {}
        except Exception as e:
            task_logger.exception(
                f"An error occurred while loading Locust result file for task: {e}"
            )
            return {}
        finally:
            if os.path.exists(result_dir):
                try:
                    shutil.rmtree(result_dir)
                    # task_logger.info(
                    #     f"Cleaned up temporary result directory: {result_dir}"
                    # )
                except Exception as e:
                    task_logger.error(
                        f"Failed to clean up temporary result directory {result_dir}: {e}"
                    )
