"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from sqlalchemy.orm import Session

from model.task import TaskResult
from utils.logger import st_logger as logger


class ResultService:
    """
    A service class for handling operations related to test results.
    """

    def insert_locust_results(
        self, session: Session, locust_result: dict, task_id: str
    ):
        """
        Parses the results from a Locust test run and inserts them into the database.

        This method handles both standard Locust statistics and custom metrics
        (like token-based throughput).

        Args:
            session (Session): The SQLAlchemy database session.
            locust_result (dict): A dictionary containing the test results from Locust.
            task_id (str): The ID of the task associated with these results.
        """
        task_logger = logger.bind(task_id=task_id)
        try:
            task_logger.info("Inserting locust results into database.")
            custom_metrics = locust_result.get("custom_metrics", {})
            locust_stats_list = locust_result.get("locust_stats", [])

            # Insert standard Locust statistics
            for stat in locust_stats_list:
                # Ensure the stat dictionary is not empty and has a task_id
                if stat and stat.get("task_id"):
                    task_result = TaskResult(**stat)
                    session.add(task_result)
                else:
                    task_logger.warning(f"Skipping invalid stat record: {stat}")

            # Insert custom token-based metrics if available
            if custom_metrics and task_id:
                # Create a single record for all custom token metrics
                custom_task_result = TaskResult(
                    task_id=task_id,
                    metric_type="token_metrics",
                    num_requests=0,  # These metrics don't have request counts in the same way
                    num_failures=0,
                    avg_latency=0,
                    min_latency=0,
                    max_latency=0,
                    median_latency=0,
                    p90_latency=0,
                    rps=0,
                    avg_content_length=0,
                    completion_tps=custom_metrics.get("completion_tps", 0.0),
                    total_tps=custom_metrics.get("total_tps", 0.0),
                    avg_total_tokens_per_req=custom_metrics.get(
                        "avg_total_tokens_per_req", 0.0
                    ),
                    avg_completion_tokens_per_req=custom_metrics.get(
                        "avg_completion_tokens_per_req", 0.0
                    ),
                )
                session.add(custom_task_result)

            session.commit()
            task_logger.info("Successfully inserted results.")
        except Exception as e:
            task_logger.exception(f"Failed to insert test results: {e}")
            session.rollback()
            raise
