"""
Data masking utilities for sensitive information.
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import re
from typing import Any, Dict, List, Optional, Union

from utils.logger import logger

SENSITIVE_KEYS = [
    "api_key",
    "api_key",
    "token",
    "password",
    "secret",
    "key",
    "authorization",
    "auth",
    "credential",
    "private_key",
    "access_key",
    "secret_key",
]


def mask_sensitive_data(data: Union[dict, list]) -> Union[dict, list]:
    """
    Mask sensitive information for safe logging and API responses.

    Args:
        data: The data to mask.

    Returns:
        The masked data.
    """
    if isinstance(data, dict):
        safe_dict: Dict[Any, Any] = {}
        try:
            for key, value in data.items():
                if isinstance(key, str) and _is_sensitive_key(key):
                    safe_dict[key] = "****"
                else:
                    safe_dict[key] = mask_sensitive_data(value)
        except Exception as e:
            logger.warning(f"Error masking sensitive data: {str(e)}")
            return data
        return safe_dict
    elif isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    else:
        return data


def _is_sensitive_key(key: str) -> bool:
    """
    Check if the key is a sensitive key.

    Args:
        key: The key to check.

    Returns:
        True if the key is a sensitive key, False otherwise.
    """
    key_lower = key.lower()
    return any(sensitive_key in key_lower for sensitive_key in SENSITIVE_KEYS)


def mask_config_value(config_key: str, config_value: str) -> str:
    """
    Mask sensitive configuration values.

    Args:
        config_key: The configuration key.
        config_value: The configuration value.

    Returns:
        The masked configuration value.
    """
    if _is_sensitive_key(config_key):
        # For sensitive configurations, only show the first 4 and last 4 characters, with asterisks in between
        if len(config_value) <= 8:
            return "****"
        else:
            return config_value[:4] + "*" * 4 + config_value[-4:]
    return config_value


def mask_api_key(api_key: str) -> str:
    """
    Mask sensitive API keys.

    Args:
        api_key: The API key.

    Returns:
        The masked API key.
    """
    if not api_key:
        return ""

    # If the API key is in Bearer token format, keep the Bearer prefix
    if api_key.startswith("Bearer "):
        token_part = api_key[7:]  # Remove the "Bearer " prefix
        if len(token_part) <= 8:
            return "Bearer ****"
        else:
            return "Bearer " + token_part[:4] + "*" * 4 + token_part[-4:]

    # Handle normal API keys
    if len(api_key) <= 8:
        return "****"
    else:
        return api_key[:4] + "*" * 4


async def extract_task_metrics(
    db, task_id: str, task: Optional[object] = None
) -> Optional[Dict]:
    """
    Extract key metrics from TaskResult for a single task.
    Used by both single task analysis and task comparison.

    Args:
        db: Database session
        task_id: Task ID to extract metrics for
        task: Optional Task object (if already fetched)

    Returns:
        Dictionary containing extracted metrics or None if task not found/no results
    """
    try:
        from sqlalchemy import select

        from model.task import Task, TaskResult

        # Get task info if not provided
        if not task:
            task_query = select(Task).where(Task.id == task_id)
            task_result = await db.execute(task_query)
            task = task_result.scalar_one_or_none()

        if not task:
            return None

        # Determine dataset_type based on test_data and chat_type
        if hasattr(task, "test_data") and hasattr(task, "chat_type"):
            if task.test_data == "default" and task.chat_type == 1:
                dataset_type = "Image-Text Dialogue Dataset"
            else:
                dataset_type = "Text conversation dataset"
        else:
            dataset_type = "Text conversation dataset"

        # Get TTFT metrics - first try Time_to_first_reasoning_token, then Time_to_first_output_token
        ttft_reasoning_query = (
            select(TaskResult)
            .where(
                TaskResult.task_id == task_id,
                TaskResult.metric_type == "Time_to_first_reasoning_token",
            )
            .order_by(TaskResult.created_at.desc())
            .limit(1)
        )
        ttft_reasoning_result = await db.execute(ttft_reasoning_query)
        ttft_reasoning_data = ttft_reasoning_result.scalar_one_or_none()

        ttft_output_query = (
            select(TaskResult)
            .where(
                TaskResult.task_id == task_id,
                TaskResult.metric_type == "Time_to_first_output_token",
            )
            .order_by(TaskResult.created_at.desc())
            .limit(1)
        )
        ttft_output_result = await db.execute(ttft_output_query)
        ttft_output_data = ttft_output_result.scalar_one_or_none()

        # Get Total_time metrics
        total_time_query = (
            select(TaskResult)
            .where(
                TaskResult.task_id == task_id,
                TaskResult.metric_type == "Total_time",
            )
            .order_by(TaskResult.created_at.desc())
            .limit(1)
        )
        total_time_result = await db.execute(total_time_query)
        total_time_data = total_time_result.scalar_one_or_none()

        # Get token metrics
        token_query = (
            select(TaskResult)
            .where(
                TaskResult.task_id == task_id,
                TaskResult.metric_type == "token_metrics",
            )
            .order_by(TaskResult.created_at.desc())
            .limit(1)
        )
        token_result = await db.execute(token_query)
        token_data = token_result.scalar_one_or_none()

        # Initialize default values
        first_token_latency = 0.0
        total_time = 0.0
        rps = 0.0
        total_tps = 0.0
        completion_tps = 0.0
        avg_total_tokens_per_req = 0.0
        avg_completion_tokens_per_req = 0.0

        # Extract first_token_latency - prioritize Time_to_first_reasoning_token, then Time_to_first_output_token
        # Convert from ms to seconds
        if ttft_reasoning_data and ttft_reasoning_data.avg_latency:
            first_token_latency = ttft_reasoning_data.avg_latency / 1000.0
        elif ttft_output_data and ttft_output_data.avg_latency:
            first_token_latency = ttft_output_data.avg_latency / 1000.0

        # Extract total_time from Total_time metric
        # Convert from ms to seconds
        if total_time_data and total_time_data.avg_latency:
            total_time = total_time_data.avg_latency / 1000.0

        # Extract RPS data - prioritize Total_time, then Time_to_first_output_token
        if total_time_data and total_time_data.rps:
            rps = total_time_data.rps
        elif ttft_output_data and ttft_output_data.rps:
            rps = ttft_output_data.rps

        # Extract token metrics data
        if token_data:
            total_tps = token_data.total_tps or 0.0
            completion_tps = token_data.completion_tps or 0.0
            avg_total_tokens_per_req = token_data.avg_total_tokens_per_req or 0.0
            avg_completion_tokens_per_req = (
                token_data.avg_completion_tokens_per_req or 0.0
            )

        return {
            "task_id": task_id,
            "task_name": getattr(task, "name", f"Task {task_id}"),
            "model_name": getattr(task, "model", ""),
            "concurrent_users": getattr(task, "concurrent_users", 0),
            "duration": f"{getattr(task, 'duration', 0)}s",
            "stream_mode": str(getattr(task, "stream_mode", False)).lower() == "true",
            "dataset_type": dataset_type,
            "first_token_latency": first_token_latency,
            "total_time": total_time,
            "total_tps": total_tps,
            "completion_tps": completion_tps,
            "avg_total_tokens_per_req": avg_total_tokens_per_req,
            "avg_completion_tokens_per_req": avg_completion_tokens_per_req,
            "rps": rps,
        }

    except Exception as e:
        logger.error(
            f"Failed to extract metrics for task {task_id}: {str(e)}",
            exc_info=True,
        )
        return None


async def extract_multiple_task_metrics(db, task_ids: List[str]) -> List[Dict]:
    """
    Extract key metrics for multiple tasks.
    Used by task comparison functionality.

    Args:
        db: Database session
        task_ids: List of task IDs to extract metrics for

    Returns:
        List of dictionaries containing extracted metrics
    """
    from sqlalchemy import select

    from model.task import Task

    metrics_list = []

    # Get all tasks in one query for efficiency
    task_query = select(Task).where(Task.id.in_(task_ids))
    task_result = await db.execute(task_query)
    tasks = {task.id: task for task in task_result.scalars().all()}

    for task_id in task_ids:
        task = tasks.get(task_id)
        if task:
            metrics = await extract_task_metrics(db, task_id, task)
            if metrics:
                metrics_list.append(metrics)

    return metrics_list
