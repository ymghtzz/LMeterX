"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func

from db.mysql import Base


class Pagination(BaseModel):
    """
    Defines the pagination metadata for paginated responses.

    Attributes:
        total: The total number of items across all pages.
        page: The current page number.
        page_size: The number of items per page.
        total_pages: The total number of pages.
    """

    total: int = 0
    page: int = 0
    page_size: int = 0
    total_pages: int = 0


class TaskResponse(BaseModel):
    """
    Standard response model for a list of tasks with pagination.

    Attributes:
        data: A list of task data.
        pagination: Pagination metadata.
        status: The status of the response (e.g., "success").
    """

    data: List[Dict]
    pagination: Pagination
    status: str


class TaskStatusRsp(BaseModel):
    """
    Response model for querying the status of a task.

    Attributes:
        data: A list of status-related data points.
        timestamp: The timestamp of the status check.
        status: The overall status of the response.
    """

    data: List[Dict]
    timestamp: int
    status: str


class TaskCreateRsp(BaseModel):
    """
    Response model for a task creation request.

    Attributes:
        task_id: The unique identifier for the created task.
        status: The initial status of the task.
        message: A message indicating the result of the creation request.
    """

    task_id: str
    status: str
    message: str


class HeaderItem(BaseModel):
    """
    Represents a single HTTP header item for a request.

    Attributes:
        key: The header name.
        value: The header value.
        fixed: A boolean indicating if the header is fixed (not used currently).
    """

    key: str
    value: str
    fixed: bool = True


class CookieItem(BaseModel):
    """
    Represents a single HTTP cookie item for a request.

    Attributes:
        key: The cookie name.
        value: The cookie value.
    """

    key: str
    value: str


class CertConfig(BaseModel):
    """
    Configuration for SSL/TLS certificates.

    Attributes:
        cert_file: Path to the SSL certificate file.
        key_file: Path to the SSL private key file.
    """

    cert_file: Optional[str] = Field(None, description="Path to the certificate file")
    key_file: Optional[str] = Field(None, description="Path to the private key file")


class TaskStopReq(BaseModel):
    """
    Request model to stop a running task.

    Attributes:
        task_id: The ID of the task to be stopped.
    """

    task_id: str


class TaskCreateReq(BaseModel):
    """
    Request model for creating a new performance testing task.
    """

    temp_task_id: str
    name: str = Field(..., description="Name of the task")
    target_host: str = Field(..., description="Target model API host")
    api_path: str = Field(default="/chat/completions", description="API path to test")
    model: Optional[str] = Field(default="", description="Name of the model to test")
    duration: int = Field(
        default=300, ge=1, description="Duration of the test in seconds"
    )
    concurrent_users: int = Field(..., ge=1, description="Number of concurrent users")
    spawn_rate: int = Field(ge=1, description="Number of users to spawn per second")
    chat_type: Optional[int] = Field(
        default=0, ge=0, description="Type of chat interaction"
    )
    stream_mode: bool = Field(
        default=True, description="Whether to use streaming response"
    )
    headers: List[HeaderItem] = Field(
        default_factory=list, description="List of request headers"
    )
    cookies: List[CookieItem] = Field(
        default_factory=list, description="List of request cookies"
    )
    cert_config: Optional[CertConfig] = Field(
        default=None, description="Certificate configuration"
    )
    system_prompt: Optional[str] = Field(
        default="", description="System prompt for the model"
    )
    request_payload: Optional[str] = Field(
        default="", description="Custom request payload for non-chat APIs (JSON string)"
    )
    field_mapping: Optional[Dict[str, str]] = Field(
        default=None, description="Field mapping configuration for custom APIs"
    )
    test_data: Optional[str] = Field(
        default="", description="Custom test data in JSONL format or file path"
    )


class TaskResultItem(BaseModel):
    """
    Represents a single data point of a task's performance results.
    """

    avg_content_length: float
    avg_response_time: float
    created_at: str
    failure_count: int
    id: int
    max_response_time: float
    median_response_time: float
    metric_type: str
    min_response_time: float
    percentile_90_response_time: float
    request_count: int
    rps: float
    task_id: str
    total_tps: float
    completion_tps: float
    avg_total_tokens_per_req: float
    avg_completion_tokens_per_req: float


class TaskResultRsp(BaseModel):
    """
    Response model for task performance results.

    Attributes:
        results: A list of `TaskResultItem` objects.
        status: The status of the response.
        error: An error message if the request failed, otherwise None.
    """

    results: List[TaskResultItem]
    status: str
    error: Union[str, None]


class ModelTaskInfo(BaseModel):
    """
    Model information for performance comparison.

    Attributes:
        model_name: The name of the model.
        concurrent_users: The number of concurrent users.
        task_id: The task ID.
        task_name: The task name.
        created_at: The creation timestamp.
    """

    model_name: str
    concurrent_users: int
    task_id: str
    task_name: str
    created_at: str


class ComparisonRequest(BaseModel):
    """
    Request model for performance comparison.

    Attributes:
        selected_tasks: List of task IDs to compare.
    """

    selected_tasks: List[str] = Field(
        ..., min_length=2, max_length=10, description="Task IDs to compare"
    )


class ComparisonMetrics(BaseModel):
    """
    Comparison metrics for a single task.

    Attributes:
        task_id: The task ID.
        model_name: The model name.
        concurrent_users: The number of concurrent users.
        task_name: The task name.
        ttft: Time to first token (min_latency).
        total_tps: Total tokens per second.
        completion_tps: Completion tokens per second.
        avg_total_tpr: Average total tokens per request.
        avg_completion_tpr: Average completion tokens per request.
        avg_response_time: Average response time.
        rps: Requests per second.
    """

    task_id: str
    model_name: str
    concurrent_users: int
    task_name: str
    ttft: float
    total_tps: float
    completion_tps: float
    avg_total_tpr: float
    avg_completion_tpr: float
    avg_response_time: float
    rps: float


class ComparisonResponse(BaseModel):
    """
    Response model for performance comparison.

    Attributes:
        data: List of comparison metrics.
        status: The status of the response.
        error: An error message if the request failed, otherwise None.
    """

    data: List[ComparisonMetrics]
    status: str
    error: Union[str, None]


class ModelTasksResponse(BaseModel):
    """
    Response model for getting available model tasks for comparison.

    Attributes:
        data: List of model task information.
        status: The status of the response.
        error: An error message if the request failed, otherwise None.
    """

    data: List[ModelTaskInfo]
    status: str
    error: Union[str, None]


class Task(Base):
    """
    SQLAlchemy model representing a task in the 'tasks' table.
    """

    __tablename__ = "tasks"
    id = Column(String(40), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False)
    target_host = Column(String(255), nullable=False)
    model = Column(String(100), nullable=True)
    system_prompt = Column(Text, nullable=True)
    stream_mode = Column(String(20), nullable=False)
    concurrent_users = Column(Integer, nullable=False)
    spawn_rate = Column(Integer, nullable=False)
    duration = Column(Integer, nullable=False)
    chat_type = Column(Integer, nullable=True)
    log_file = Column(Text, nullable=True)
    result_file = Column(Text, nullable=True)
    cert_file = Column(String(255), nullable=True)
    key_file = Column(String(255), nullable=True)
    headers = Column(Text, nullable=True)
    cookies = Column(Text, nullable=True)
    api_path = Column(String(255), nullable=True)
    request_payload = Column(Text, nullable=True)
    field_mapping = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    test_data = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TaskResult(Base):
    """
    SQLAlchemy model for storing performance results of a task in the 'task_results' table.
    """

    __tablename__ = "task_results"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(40), nullable=False)
    metric_type = Column(String(36), nullable=False)
    num_requests = Column(Integer, nullable=False)
    num_failures = Column(Integer, nullable=False)
    avg_latency = Column(Float, nullable=False)
    min_latency = Column(Float, nullable=False)
    max_latency = Column(Float, nullable=False)
    median_latency = Column(Float, nullable=False)
    p90_latency = Column(Float, nullable=False)
    rps = Column(Float, nullable=False)
    avg_content_length = Column(Float, nullable=False)
    total_tps = Column(Float, nullable=True, default=0.0)
    completion_tps = Column(Float, nullable=True, default=0.0)
    avg_total_tokens_per_req = Column(Float, nullable=True, default=0.0)
    avg_completion_tokens_per_req = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_task_result_item(self) -> TaskResultItem:
        """Converts the SQLAlchemy model instance to a Pydantic TaskResultItem."""
        return TaskResultItem(
            id=int(self.id) if self.id is not None else 0,
            task_id=str(self.task_id) if self.task_id is not None else "",
            metric_type=str(self.metric_type) if self.metric_type is not None else "",
            request_count=(
                int(self.num_requests) if self.num_requests is not None else 0
            ),
            failure_count=(
                int(self.num_failures) if self.num_failures is not None else 0
            ),
            avg_response_time=(
                float(self.avg_latency) if self.avg_latency is not None else 0.0
            ),
            min_response_time=(
                float(self.min_latency) if self.min_latency is not None else 0.0
            ),
            max_response_time=(
                float(self.max_latency) if self.max_latency is not None else 0.0
            ),
            median_response_time=(
                float(self.median_latency) if self.median_latency is not None else 0.0
            ),
            percentile_90_response_time=(
                float(self.p90_latency) if self.p90_latency is not None else 0.0
            ),
            rps=float(self.rps) if self.rps is not None else 0.0,
            avg_content_length=(
                float(self.avg_content_length)
                if self.avg_content_length is not None
                else 0.0
            ),
            created_at=self.created_at.isoformat() if self.created_at else "",
            total_tps=float(self.total_tps) if self.total_tps is not None else 0.0,
            completion_tps=(
                float(self.completion_tps) if self.completion_tps is not None else 0.0
            ),
            avg_total_tokens_per_req=(
                float(self.avg_total_tokens_per_req)
                if self.avg_total_tokens_per_req is not None
                else 0.0
            ),
            avg_completion_tokens_per_req=(
                float(self.avg_completion_tokens_per_req)
                if self.avg_completion_tokens_per_req is not None
                else 0.0
            ),
        )
