"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import subprocess  # nosec B404

from sqlalchemy import select
from sqlalchemy.orm import Session

from engine.runner import LocustRunner
from model.task import Task
from service.result_service import ResultService
from utils.config import (
    ST_ENGINE_DIR,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_FAILED_REQUESTS,
    TASK_STATUS_LOCKED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_STOPPED,
    TASK_STATUS_STOPPING,
)
from utils.logger import add_task_log_sink, logger, remove_task_log_sink


class TaskService:
    """
    Provides services for managing the entire lifecycle of a performance test task.
    This includes creating, locking, executing, and stopping tasks.
    """

    def __init__(self):
        """Initializes the TaskService with a LocustRunner instance."""
        self.runner = LocustRunner(ST_ENGINE_DIR)
        self.result_service = ResultService()

    def update_task_status(
        self,
        session: Session,
        task: Task,
        status: str,
        error_message: str | None = None,
    ):
        """
        Updates the status of a given task.

        Args:
            session (Session): The SQLAlchemy database session.
            task (Task): The task object to update.
            status (str): The new status to set.
            error_message (str, optional): An error message to record if the task failed.
        """
        try:
            task.status = status  # type: ignore
            if error_message:
                # Limit error message length to avoid database field overflow
                # MySQL TEXT field can store up to 65,535 characters
                max_length = 65000  # Leave some buffer
                if len(error_message) > max_length:
                    truncated_message = (
                        error_message[: max_length - 100]
                        + f"\n... (truncated, original length: {len(error_message)})"
                    )
                    task.error_message = truncated_message  # type: ignore
                else:
                    task.error_message = error_message  # type: ignore
            session.commit()
        except Exception as e:
            if hasattr(task, "id") and task.id:
                task_logger = logger.bind(task_id=task.id)
                task_logger.exception(f"Failed to update status: {e}")
            else:
                logger.exception(f"Failed to update status for a task: {e}")
            session.rollback()

    def update_task_status_by_id(self, session: Session, task_id: str, status: str):
        """
        Updates the status of a task identified by its ID.

        Args:
            session (Session): The SQLAlchemy database session.
            task_id (str): The ID of the task to update.
            status (str): The new status to set.
        """
        task_logger = logger.bind(task_id=task_id)
        try:
            task = session.get(Task, task_id)
            if task:
                self.update_task_status(session, task, status)
            else:
                task_logger.warning(f"Could not find task to update status.")
        except Exception as e:
            task_logger.exception(f"Failed to update status for task: {e}")
            session.rollback()

    def get_and_lock_task(self, session: Session) -> Task | None:
        """
        Atomically retrieves and locks the next available task with 'created' status.

        This method uses a 'SELECT ... FOR UPDATE' query to ensure that only one
        engine instance can claim a task.

        Args:
            session (Session): The SQLAlchemy database session.

        Returns:
            Task | None: The locked task object, or None if no tasks are available.
        """
        try:
            # The transaction is handled by the get_db_session context manager
            query = (
                select(Task).where(Task.status == "created").with_for_update().limit(1)
            )
            task = session.execute(query).scalar_one_or_none()
            if task:
                task_logger = logger.bind(task_id=task.id)
                task_logger.info(f"Claimed and locked new task {task.id}.")
                task.status = "locked"  # type: ignore # Update status immediately
                session.commit()
                return task
            return None
        except Exception as e:
            logger.exception(f"Error while trying to get and lock a task: {e}")
            session.rollback()
            return None

    def reconcile_tasks_on_startup(self, session: Session):
        """
        Reconciles tasks on engine startup by checking for tasks in 'running' or
        'locked' states and cleaning up any that no longer have an active process.

        This is crucial for handling state inconsistencies that arise when the
        engine is restarted while tasks are being processed.
        Args:
            session (Session): The SQLAlchemy database session.
        """
        logger.info("Reconciling tasks on startup...")
        try:
            # Find all tasks that were in a transient state (locked or running)
            # during the last shutdown.
            stale_tasks = (
                session.execute(
                    select(Task).where(
                        Task.status.in_([TASK_STATUS_RUNNING, TASK_STATUS_LOCKED])
                    )
                )
                .scalars()
                .all()
            )

            if not stale_tasks:
                logger.info("No running or locked tasks found to reconcile.")
                return

            logger.info(f"Found {len(stale_tasks)} potentially stale tasks to check")
            for task in stale_tasks:
                handler_id = None
                try:
                    # Temporarily add a log sink for this specific task to capture reconciliation logs.
                    handler_id = add_task_log_sink(task.id)
                    task_logger = logger.bind(task_id=task.id)

                    if task.status == TASK_STATUS_LOCKED:
                        # The task was locked, but the engine restarted before the process
                        # was created. Mark it as failed directly.
                        task_logger.warning(
                            f"Task {task.id} was in '{task.status}' state during restart. "
                            f"Task {task.id}, Marking as FAILED as it never started."
                        )
                        error_message = "Task was aborted before execution due to an engine restart."
                        self.update_task_status(
                            session, task, TASK_STATUS_FAILED, error_message
                        )
                        continue

                    # For tasks in 'running' state, check for an orphaned process.
                    try:
                        # Use pgrep to check if a locust process with a specific task-id exists.
                        cmd = ["pgrep", "-f", f"locust .*--task-id {task.id}"]
                        subprocess.check_output(
                            cmd, stderr=subprocess.DEVNULL
                        )  # nosec B603

                        # If pgrep succeeds, the process exists and is now an orphan.
                        task_logger.warning(
                            f"Found orphaned locust process for task {task.id} in '{task.status}' state. "
                            f"Terminating it and marking task as FAILED."
                        )
                        try:
                            kill_cmd = ["pkill", "-f", f"locust .*--task-id {task.id}"]
                            subprocess.run(kill_cmd, check=True)  # nosec B603
                            task_logger.info(
                                f"Successfully terminated orphaned process."
                            )
                        except subprocess.CalledProcessError as e:
                            if e.returncode > 1:
                                task_logger.error(
                                    f"Failed to kill orphaned process: {e}"
                                )
                            else:
                                task_logger.warning(
                                    f"Orphaned process cleanup for task {task.id} was interrupted or the process was already gone (exit code {e.returncode}). This is likely safe to ignore."
                                )
                        except Exception as kill_e:
                            task_logger.error(
                                f"An unexpected error occurred while trying to kill orphaned process: {kill_e}"
                            )

                        error_message = "Task process was orphaned by an engine restart and has been terminated."
                        self.update_task_status(
                            session, task, TASK_STATUS_FAILED, error_message
                        )

                    except subprocess.CalledProcessError:
                        # pgrep returns a non-zero exit code, meaning no process was found.
                        task_logger.warning(
                            f"Task {task.id} was in '{task.status}' state, but no active process found. "
                            f"Marking as FAILED. This likely occurred during an engine restart."
                        )
                        error_message = (
                            "Task process was not found after an engine restart."
                        )
                        self.update_task_status(
                            session, task, TASK_STATUS_FAILED, error_message
                        )
                finally:
                    # Clean up the temporary log sink.
                    if handler_id is not None:
                        remove_task_log_sink(handler_id)

        except Exception as e:
            logger.exception(f"An error occurred during task reconciliation: {e}")

    def start_task(self, task: Task) -> dict:
        """
        Executes the performance test for a given task.

        Args:
            task (Task): The task to execute.

        Returns:
            dict: The result dictionary from the Locust runner, including run status.
        """
        task_logger = logger.bind(task_id=task.id)
        try:
            task_logger.info(f"Starting execution for task {task.id}.")
            result = self.runner.run_locust_process(task)
            return result
        except Exception as e:
            task_logger.exception(f"An unexpected error occurred during execution: {e}")
            return {
                "status": "FAILED",
                "locust_result": {},
                "stderr": str(e),
                "return_code": -1,
            }

    def process_task_pipeline(self, task: Task, session: Session):
        """
        Manages the complete pipeline for processing a single task.

        Args:
            task (Task): The task to process.
            session (Session): The SQLAlchemy database session.
        """
        handler_id = None
        task_logger = logger.bind(task_id=task.id)
        try:
            handler_id = add_task_log_sink(task.id)
            task_logger.info(f"Starting processing pipeline for task {task.id}.")
            self.update_task_status(session, task, TASK_STATUS_RUNNING)

            run_result = self.start_task(task)
            run_status = run_result.get("status")
            locust_result = run_result.get("locust_result", {})

            # Refresh the task state to get any updates that may have occurred
            # during the run, such as a manual stop request.
            session.refresh(task)

            if task.status in (TASK_STATUS_STOPPING, TASK_STATUS_STOPPED):
                task_logger.info(
                    f"Task {task.id} was stopped during execution. Marking as '{TASK_STATUS_STOPPED}'."
                )
                self.update_task_status(session, task, TASK_STATUS_STOPPED)
            elif run_status == "COMPLETED":
                task_logger.info(
                    f"Runner completed successfully. Processing results..."
                )
                self.update_task_status(session, task, TASK_STATUS_COMPLETED)
                if locust_result:
                    # Always insert results first, regardless of outcome
                    self.result_service.insert_locust_results(
                        session, locust_result, task.id
                    )
                else:
                    error_message = (
                        f"Runner completed but no result file was generated."
                    )
                    task_logger.error(f"{error_message}")
                    self.update_task_status(
                        session, task, TASK_STATUS_FAILED, error_message
                    )
            elif run_status == "FAILED_REQUESTS":
                task_logger.warning(
                    f"Runner completed with failed requests. Processing results..."
                )
                if locust_result:
                    # Insert results even when there are failures
                    self.result_service.insert_locust_results(
                        session, locust_result, task.id
                    )

                    # Get failure count from aggregated stats
                    total_failures = 0
                    aggregated_stats = None
                    for stats_entry in locust_result.get("stats", []):
                        if stats_entry.get("name") == "Aggregated":
                            aggregated_stats = stats_entry
                            break

                    if aggregated_stats:
                        total_failures = aggregated_stats.get("num_failures", 0)

                    error_message = f"Task {task.id} completed with {total_failures} failed requests."
                    task_logger.warning(f"{error_message}")
                    self.update_task_status(
                        session, task, TASK_STATUS_FAILED_REQUESTS, error_message
                    )
                else:
                    error_message = f"Task {task.id} had request failures but no result file was generated."
                    task_logger.error(f"{error_message}")
                    self.update_task_status(
                        session, task, TASK_STATUS_FAILED, error_message
                    )
            elif run_status == "FAILED":
                return_code = run_result.get("return_code", "unknown")
                stderr_details = run_result.get("stderr", "No stderr.")
                error_message = f"Task {task.id} execution failed (Locust exit code: {return_code}). Details: {stderr_details}"
                task_logger.error(f"Task execution failed.")
                self.update_task_status(
                    session, task, TASK_STATUS_FAILED, error_message
                )
            else:
                # Unexpected status from runner
                return_code = run_result.get("return_code", "unknown")
                stderr_details = run_result.get("stderr", "No stderr.")
                error_message = f"Task {task.id} returned unexpected status '{run_status}' (return code: {return_code}). Details: {stderr_details}"
                task_logger.error(f"Unexpected runner status: {run_status}")
                self.update_task_status(
                    session, task, TASK_STATUS_FAILED, error_message
                )

        except Exception as e:
            error_message = f"An unexpected error occurred in the pipeline: {e}"
            task_logger.exception(f"Pipeline failed with an unexpected error.")
            self.update_task_status(session, task, TASK_STATUS_FAILED, error_message)
        finally:
            if handler_id is not None:
                remove_task_log_sink(handler_id)

    def stop_task(self, task_id: str) -> bool:
        """
        Stops a running task by terminating its Locust process.

        Args:
            task_id (str): The ID of the task to stop.

        Returns:
            bool: True if the process was stopped successfully or was already stopped,
                  False if the stop attempt failed.
        """
        task_logger = logger.bind(task_id=task_id)
        process = self.runner.process_dict.get(task_id)

        if not process:
            task_logger.warning(
                f"Task {task_id}, Process not found in runner's dictionary. It might have finished or be on another node."
            )
            self.runner.process_dict.pop(task_id, None)
            return True

        if process.poll() is not None:
            task_logger.info(
                f"Task {task_id}, Process with PID {process.pid} has already terminated. Cleaning up."
            )
            self.runner.process_dict.pop(task_id, None)
            return True

        task_logger.info(
            f"Task {task_id}, Attempting to terminate process with PID {process.pid} (SIGTERM)."
        )
        try:
            process.terminate()
            process.wait(timeout=10)
            task_logger.info(
                f"Task {task_id}, Process terminated successfully via SIGTERM."
            )
            self.runner.process_dict.pop(task_id, None)
            return True
        except subprocess.TimeoutExpired:
            task_logger.warning(
                f"SIGTERM timed out for task {task_id}, process {process.pid}. Attempting to kill (SIGKILL)."
            )
            try:
                process.kill()
                process.wait(timeout=5)
                task_logger.info(
                    f"Task {task_id}, Process killed successfully via SIGKILL."
                )
                self.runner.process_dict.pop(task_id, None)
                return True
            except subprocess.TimeoutExpired:
                task_logger.error(
                    f"Task {task_id}, Failed to kill process {process.pid} even with SIGKILL. Manual intervention may be required."
                )
                return False
            except Exception as e:
                task_logger.exception(
                    f"Task {task_id}, An unexpected error occurred while trying to kill process {process.pid}: {e}"
                )
                return False
        except Exception as e:
            task_logger.exception(
                f"Task {task_id}, An unexpected error occurred while terminating process {process.pid}: {e}"
            )
            return False

    def get_stopping_task_ids(self, session: Session) -> list[str]:
        """
        Retrieves a list of task IDs with the 'stopping' status.

        Args:
            session (Session): The SQLAlchemy database session.

        Returns:
            list[str]: A list of task IDs to be stopped.
        """
        try:
            query = select(Task.id).where(Task.status == TASK_STATUS_STOPPING)
            stopping_task_ids = list(session.execute(query).scalars().all())
            if stopping_task_ids:
                logger.info(f"Found stopping tasks: {stopping_task_ids}")
            return stopping_task_ids
        except Exception as e:
            logger.exception("Failed to get stopping task IDs from the database.")
            return []
