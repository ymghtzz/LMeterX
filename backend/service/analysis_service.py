"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import json
from typing import Dict, Optional

import requests
from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession

from model.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    GetAnalysisResponse,
    TaskAnalysis,
)
from model.task import Task, TaskResult
from service.system_service import get_ai_service_config_internal_svc
from service.task_service import get_task_result_svc
from utils.error_handler import ErrorMessages, ErrorResponse
from utils.logger import logger


async def analyze_task_svc(
    request: Request, task_id: str, analysis_request: AnalysisRequest
) -> AnalysisResponse:
    """
    Perform AI analysis on task results.

    Args:
        request: The incoming request.
        task_id: The task ID to analyze.
        analysis_request: The analysis request.

    Returns:
        AnalysisResponse: The analysis result.
    """
    try:
        db: AsyncSession = request.state.db

        # Check if task exists and get task info
        task_query = select(Task).where(Task.id == task_id)
        task_result = await db.execute(task_query)
        task = task_result.scalar_one_or_none()

        if not task:
            logger.warning(f"Analysis requested for non-existent task: {task_id}")
            return AnalysisResponse(
                task_id=task_id,
                analysis_report="",
                status="failed",
                error_message=ErrorMessages.TASK_NOT_FOUND,
                created_at="",
            )

        # Reuse get_task_result_svc to get task results
        task_results_response = await get_task_result_svc(request, task_id)

        # Check if results were successfully retrieved
        if (
            task_results_response.status != "success"
            or not task_results_response.results
        ):
            logger.warning(f"No results found for task {task_id}")
            return AnalysisResponse(
                task_id=task_id,
                analysis_report="",
                status="failed",
                error_message=ErrorMessages.TASK_NO_RESULTS,
                created_at="",
            )

        # Get AI service configuration from system config
        try:
            ai_config = await get_ai_service_config_internal_svc(request)
        except HTTPException as e:
            error_msg = (
                f"Failed to get AI service configuration for task {task_id}: {str(e)}"
            )
            logger.error(error_msg, exc_info=True)
            return AnalysisResponse(
                task_id=task_id,
                analysis_report="",
                status="failed",
                error_message=f"{ErrorMessages.MISSING_AI_CONFIG}. Please configure AI service in System Configuration.",
                created_at="",
            )

        # Prepare test configuration
        # Determine dataset_type based on test_data and chat_type
        if task.test_data == "default" and task.chat_type == 1:
            dataset_type = "Image-Text Dialogue Dataset"
        else:
            dataset_type = "Text conversation dataset"

        test_config = {
            "name": task.name,
            "model": task.model,
            "concurrent_users": task.concurrent_users,
            "duration": f"{task.duration}s",
            "stream_mode": task.stream_mode,
            # "test_data": task.test_data,
            # "chat_type": task.chat_type,
            "dataset_type": dataset_type,
        }

        # Prepare results data from the reused service response
        results_data = [result.model_dump() for result in task_results_response.results]

        # check results_data is not empty
        if len(results_data) <= 1:
            logger.warning(
                "Performance results are incomplete and cannot be accurately analyzed and summarized"
            )
            return AnalysisResponse(
                task_id=task_id,
                analysis_report="",
                status="failed",
                error_message="Performance results are incomplete!",
                created_at="",
            )

        # filter results_data
        # filtered_results_data = _filter_results_data(results_data)

        # extract key metrics for further analysis
        key_metrics = _extract_key_metrics(results_data)

        # Call AI service for analysis
        try:
            analysis_report = await _call_ai_service(
                ai_config.host,
                ai_config.model,
                ai_config.api_key,
                json.dumps(test_config, ensure_ascii=False, indent=2),
                json.dumps(key_metrics, ensure_ascii=False, indent=2),
                analysis_request.language or "en",
            )

            # Check if analysis already exists for this task
            existing_analysis_query = select(TaskAnalysis).where(
                TaskAnalysis.task_id == task_id
            )
            existing_analysis_result = await db.execute(existing_analysis_query)
            existing_analysis = existing_analysis_result.scalar_one_or_none()

            if existing_analysis:
                # Update existing analysis
                logger.debug(f"Updating existing analysis for task {task_id}")
                update_stmt = (
                    update(TaskAnalysis)
                    .where(TaskAnalysis.task_id == task_id)
                    .values(
                        eval_prompt=analysis_request.eval_prompt
                        or "AI analysis prompt",
                        analysis_report=analysis_report,
                        status="completed",
                        error_message=None,
                    )
                )
                await db.execute(update_stmt)
                await db.commit()

                # Refresh the existing analysis object
                await db.refresh(existing_analysis)
                analysis = existing_analysis
            else:
                # Create new analysis
                logger.debug(f"Creating new analysis for task {task_id}")
                analysis = TaskAnalysis(
                    task_id=task_id,
                    eval_prompt=analysis_request.eval_prompt or "AI analysis prompt",
                    analysis_report=analysis_report,
                    status="completed",
                )
                db.add(analysis)
                await db.commit()
                await db.refresh(analysis)

            return AnalysisResponse(
                task_id=task_id,
                analysis_report=analysis_report,
                status="completed",
                created_at=(
                    analysis.created_at.isoformat() if analysis.created_at else ""
                ),
            )

        except Exception as ai_error:
            # Handle AI service errors - only log error, don't update database
            error_message = f"AI analysis failed for task {task_id}: {str(ai_error)}"
            logger.error(error_message, exc_info=True)
            return AnalysisResponse(
                task_id=task_id,
                analysis_report="",
                status="failed",
                error_message="AI analysis failed. Please check the AI service configuration and try again.",
                created_at="",
            )

    except Exception as e:
        # Handle other exceptions - only log error, don't update database
        error_message = f"Analysis failed for task {task_id}: {str(e)}"
        logger.error(error_message, exc_info=True)
        return AnalysisResponse(
            task_id=task_id,
            analysis_report="",
            status="failed",
            error_message="Analysis failed due to internal error. Please try again later.",
            created_at="",
        )


async def get_analysis_svc(request: Request, task_id: str) -> GetAnalysisResponse:
    """
    Get analysis result for a task.

    Args:
        request: The incoming request.
        task_id: The task ID.

    Returns:
        GetAnalysisResponse: The analysis result.
    """
    try:
        db: AsyncSession = request.state.db

        # Check if analysis exists
        analysis_query = select(TaskAnalysis).where(TaskAnalysis.task_id == task_id)
        analysis_result = await db.execute(analysis_query)
        analysis = analysis_result.scalar_one_or_none()

        if not analysis:
            # logger.warning(f"Analysis not found for task: {task_id}")
            return GetAnalysisResponse(
                data=None,
                status="not_found",
                error="Analysis not found for this task",
            )

        return GetAnalysisResponse(
            data=AnalysisResponse(
                task_id=str(analysis.task_id) if analysis.task_id is not None else "",
                analysis_report=(
                    str(analysis.analysis_report)
                    if analysis.analysis_report is not None
                    else ""
                ),
                status=str(analysis.status) if analysis.status is not None else "",
                error_message=(
                    str(analysis.error_message)
                    if analysis.error_message is not None
                    else None
                ),
                created_at=(
                    analysis.created_at.isoformat() if analysis.created_at else ""
                ),
            ),
            status="success",
            error=None,
        )

    except Exception as e:
        error_msg = f"Failed to retrieve analysis for task {task_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return GetAnalysisResponse(
            data=None,
            status="error",
            error="Failed to retrieve analysis result",
        )


async def _call_ai_service(
    host: str,
    model: str,
    api_key: str,
    test_config: str,
    results: str,
    language: str = "en",
) -> str:
    """
    Call AI service for analysis.

    Args:
        host: The AI service host URL.
        model: The AI model name.
        api_key: The API key for authentication.
        test_config: The test configuration data.
        results: The test results data.
        language: The language for analysis prompt (en/zh).

    Returns:
        str: The analysis content.

    Raises:
        Exception: If the AI service call fails.
    """
    url = f"{host}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    from utils.prompt import get_analysis_prompt

    prompt_template = get_analysis_prompt(language)
    prompt = prompt_template.format(test_config=test_config, results=results)

    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
    }

    logger.debug(f"Calling AI service: {url}")
    logger.debug(f"AI service request headers: {headers}")
    logger.debug(f"AI service request data: {json.dumps(data, ensure_ascii=False)}")
    logger.debug(f"AI service request prompt: {prompt}")
    try:
        response = requests.post(
            url, headers=headers, data=json.dumps(data), timeout=120
        )
        response.raise_for_status()

        response_data = response.json()
        if "choices" in response_data and len(response_data["choices"]) > 0:
            content = response_data["choices"][0]["message"]["content"]
            return content
        else:
            error_msg = "Invalid response format from AI service - missing content"
            logger.error(f"AI service error: {error_msg}")
            logger.error(f"AI service response: {response_data}")
            raise Exception(error_msg)

    except requests.exceptions.Timeout as e:
        error_msg = f"AI service request timeout: {str(e)}"
        logger.error(f"AI service timeout error: {error_msg}")
        raise Exception(error_msg)
    except requests.exceptions.ConnectionError as e:
        error_msg = f"AI service connection error: {str(e)}"
        logger.error(f"AI service connection error: {error_msg}")
        raise Exception(error_msg)
    except requests.exceptions.RequestException as e:
        error_msg = f"AI service request failed: {str(e)}"
        logger.error(f"AI service request error: {error_msg}")
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"AI service call failed: {str(e)}"
        logger.error(f"AI service general error: {error_msg}")
        raise Exception(error_msg)


def _filter_results_data(results_data: list) -> list:
    """
    Filter results_data to remove unnecessary information and keep only key metrics.

    Args:
        results_data: The original results data list

    Returns:
        list: The filtered results data list
    """
    # define the metric_type to keep
    valid_metric_types = {
        "Time_to_first_reasoning_token",
        "Time_to_first_output_token",
        "Total_time",
        "token_metrics",
        "chat_completions",
        "custom_api",
        "failure",
    }

    # define the common fields to remove
    common_fields_to_remove = {"avg_content_length", "created_at", "id", "task_id"}

    # define the time related fields to remove
    time_related_fields_to_remove = {
        "total_tps",
        "completion_tps",
        "avg_total_tokens_per_req",
        "avg_completion_tokens_per_req",
    }

    # define the token_metrics fields to remove
    token_metrics_fields_to_remove = {
        "rps",
        "request_count",
        "failure_count",
        "percentile_90_response_time",
        "min_response_time",
        "median_response_time",
        "max_response_time",
        "avg_response_time",
    }

    filtered_data = []

    for item in results_data:
        metric_type = item.get("metric_type", "")

        # keep the specified metric_type
        if metric_type not in valid_metric_types:
            continue

        # create the filtered item
        filtered_item = {}

        for key, value in item.items():
            # skip the common fields to remove
            if key in common_fields_to_remove:
                continue

            # remove the time related fields for time related metrics
            if metric_type in {
                "Time_to_first_reasoning_token",
                "Time_to_first_output_token",
                "Total_time",
                "chat_completions",
                "custom_api",
            }:
                if key in time_related_fields_to_remove:
                    continue

            # remove the time related fields for token_metrics
            if metric_type == "token_metrics":
                if key in token_metrics_fields_to_remove:
                    continue

            # keep other fields
            filtered_item[key] = value

        if filtered_item:  # only add the filtered item if it is not empty
            filtered_data.append(filtered_item)

    return filtered_data


def _extract_key_metrics(results_data: list) -> dict:
    """
    Extract key metrics from results_data according to specific rules.

    Args:
        results_data: The filtered results data list

    Returns:
        dict: A dictionary containing the extracted key metrics
    """
    extracted_metrics = {}

    # Initialize metrics with default values
    extracted_metrics = {
        "First_token_latency(s)": "N/A",
        "Total_time(s)": "N/A",
        "RPS(req/s)": "N/A",
        "Completion_tps(tokens/s)": "N/A",
        "Total_tps(tokens/s)": "N/A",
        "Avg_completion_tokens(tokens/req)": "N/A",
        "Avg_total_tokens(tokens/req)": "N/A",
        "Failure_request": "N/A",
    }

    # Track values for different metric types
    first_reasoning_time = None
    first_output_time = None
    total_time = None
    token_metrics_data = None
    rps_total_time = None
    rps_first_output = None
    failure_request_count = 0
    failure_chat_count = 0
    failure_custom_count = 0

    for item in results_data:
        metric_type = item.get("metric_type", "")

        # Extract First_token_latency
        if metric_type == "Time_to_first_reasoning_token":
            if "avg_response_time" in item:
                first_reasoning_time = item["avg_response_time"]
        elif metric_type == "Time_to_first_output_token":
            if "avg_response_time" in item:
                first_output_time = item["avg_response_time"]

        # Extract Total_time
        if metric_type == "Total_time":
            if "avg_response_time" in item:
                total_time = item["avg_response_time"]
            if "rps" in item:
                rps_total_time = item["rps"]

        # Extract token_metrics related data
        if metric_type == "token_metrics":
            token_metrics_data = item

        # Extract RPS from Time_to_first_output_token
        if metric_type == "Time_to_first_output_token":
            if "rps" in item:
                rps_first_output = item["rps"]

        # Extract failure counts
        if metric_type == "failure":
            if "request_count" in item:
                failure_request_count += item["request_count"]
        elif metric_type == "chat_completions":
            if "failure_count" in item:
                failure_chat_count += item["failure_count"]
        elif metric_type == "custom_api":
            if "failure_count" in item:
                failure_custom_count += item["failure_count"]

    # Set First_token_latency (convert ms to seconds, round to 2 decimals)
    if first_reasoning_time is not None:
        extracted_metrics["First_token_latency(s)"] = round(
            first_reasoning_time / 1000, 2
        )
    elif first_output_time is not None:
        extracted_metrics["First_token_latency(s)"] = round(first_output_time / 1000, 2)

    # Set Total_time (convert ms to seconds, round to 2 decimals)
    if total_time is not None:
        extracted_metrics["Total_time(s)"] = round(total_time / 1000, 2)

    # Set token_metrics related fields
    if token_metrics_data:
        if "completion_tps" in token_metrics_data:
            extracted_metrics["Completion_tps(tokens/s)"] = token_metrics_data[
                "completion_tps"
            ]
        if "total_tps" in token_metrics_data:
            extracted_metrics["Total_tps(tokens/s)"] = token_metrics_data["total_tps"]
        if "avg_completion_tokens_per_req" in token_metrics_data:
            extracted_metrics["Avg_completion_tokens(tokens/req)"] = token_metrics_data[
                "avg_completion_tokens_per_req"
            ]
        if "avg_total_tokens_per_req" in token_metrics_data:
            extracted_metrics["Avg_total_tokens(tokens/req)"] = token_metrics_data[
                "avg_total_tokens_per_req"
            ]

    # Set RPS
    if rps_total_time is not None:
        extracted_metrics["RPS(req/s)"] = rps_total_time
    elif rps_first_output is not None:
        extracted_metrics["RPS(req/s)"] = rps_first_output

    # Set failure_request (sum of all failure counts)
    total_failures = failure_request_count + failure_chat_count + failure_custom_count
    extracted_metrics["Failure_request"] = str(total_failures)
    return extracted_metrics
