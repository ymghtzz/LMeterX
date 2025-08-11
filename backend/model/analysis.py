"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from typing import Optional, Union

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Text, func

from db.mysql import Base


class TaskAnalysis(Base):
    """
    SQLAlchemy model for storing AI analysis results of a task in the 'test_insights' table.
    """

    __tablename__ = "test_insights"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(40), nullable=False, unique=True)
    eval_prompt = Column(Text, nullable=False)
    analysis_report = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="completed")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AnalysisRequest(BaseModel):
    """
    Request model for AI analysis.

    Attributes:
        task_id: The task ID to analyze.
        language: The language for analysis prompt (en/zh).
    """

    eval_prompt: Optional[str] = Field(None, description="Custom evaluation prompt")
    language: Optional[str] = Field(
        "en", description="Language for analysis prompt (en/zh)"
    )


class AnalysisResponse(BaseModel):
    """
    Response model for AI analysis.

    Attributes:
        task_id: The task ID.
        analysis_report: The AI analysis content.
        status: The analysis status.
        error_message: Error message if analysis failed.
        created_at: The creation timestamp.
    """

    task_id: str
    analysis_report: str
    status: str
    error_message: Optional[str] = None
    created_at: str


class GetAnalysisResponse(BaseModel):
    """
    Response model for getting analysis results.

    Attributes:
        data: The analysis data.
        status: The status of the response.
        error: An error message if the request failed, otherwise None.
    """

    data: Optional[AnalysisResponse] = None
    status: str
    error: Union[str, None]
