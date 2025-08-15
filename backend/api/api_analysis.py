"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from model.analysis import AnalysisRequest, AnalysisResponse, GetAnalysisResponse
from service.analysis_service import analyze_task_svc, get_analysis_svc
from utils.logger import logger

# Create an API router for analysis-related endpoints
router = APIRouter()


@router.post("/{task_id}", response_model=AnalysisResponse)
async def analyze_task(
    request: Request, task_id: str, analysis_request: AnalysisRequest
):
    """
    Perform AI analysis on task results.

    Args:
        request: The incoming request.
        task_id: The task ID to analyze (from URL path).
        analysis_request: The analysis request (optional eval_prompt).

    Returns:
        AnalysisResponse: The analysis result.

    Raises:
        HTTPException: If the task doesn't exist or analysis fails.
    """

    return await analyze_task_svc(request, task_id, analysis_request)


@router.get("/{task_id}", response_model=GetAnalysisResponse)
async def get_analysis(request: Request, task_id: str):
    """
    Get analysis result for a task.

    Args:
        request: The incoming request.
        task_id: The task ID.

    Returns:
        GetAnalysisResponse: The analysis result.
    """
    return await get_analysis_svc(request, task_id)
