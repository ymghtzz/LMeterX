"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from typing import Any, Dict, Optional, Union

from fastapi import HTTPException
from starlette.responses import JSONResponse


class ErrorResponse:
    """Error response handler"""

    @staticmethod
    def create(
        status_code: int,
        error: str,
        details: Optional[Union[str, Dict[str, Any]]] = None,
        code: Optional[str] = None,
    ) -> JSONResponse:
        """
        Create a standard error response

        Args:
            status_code: HTTP status code
            error: Error message
            details: Detailed error information (optional)
            code: Error code (optional)

        Returns:
            JSONResponse: Standardized error response
        """
        response_content: Dict[str, Any] = {"status": "error", "error": error}

        if details:
            response_content["details"] = details

        if code:
            response_content["code"] = code

        return JSONResponse(status_code=status_code, content=response_content)

    @staticmethod
    def bad_request(
        error: str,
        details: Optional[Union[str, Dict[str, Any]]] = None,
        code: Optional[str] = None,
    ) -> JSONResponse:
        """400 Bad Request"""
        return ErrorResponse.create(400, error, details, code)

    @staticmethod
    def not_found(
        error: str,
        details: Optional[Union[str, Dict[str, Any]]] = None,
        code: Optional[str] = None,
    ) -> JSONResponse:
        """404 Not Found"""
        return ErrorResponse.create(404, error, details, code)

    @staticmethod
    def internal_server_error(
        error: str = "Internal server error",
        details: Optional[Union[str, Dict[str, Any]]] = None,
        code: Optional[str] = None,
    ) -> JSONResponse:
        """500 Internal Server Error"""
        return ErrorResponse.create(500, error, details, code)

    @staticmethod
    def unauthorized(
        error: str = "Unauthorized",
        details: Optional[Union[str, Dict[str, Any]]] = None,
        code: Optional[str] = None,
    ) -> JSONResponse:
        """401 Unauthorized"""
        return ErrorResponse.create(401, error, details, code)

    @staticmethod
    def forbidden(
        error: str = "Forbidden",
        details: Optional[Union[str, Dict[str, Any]]] = None,
        code: Optional[str] = None,
    ) -> JSONResponse:
        """403 Forbidden"""
        return ErrorResponse.create(403, error, details, code)

    @staticmethod
    def conflict(
        error: str,
        details: Optional[Union[str, Dict[str, Any]]] = None,
        code: Optional[str] = None,
    ) -> JSONResponse:
        """409 Conflict"""
        return ErrorResponse.create(409, error, details, code)


class SuccessResponse:
    """Standard success response format"""

    @staticmethod
    def create(
        data: Any = None, message: Optional[str] = None, status_code: int = 200
    ) -> JSONResponse:
        """
        Create a standard success response

        Args:
            data: Response data
            message: Success message
            status_code: HTTP status code

        Returns:
            JSONResponse: Standardized success response
        """
        response_content: Dict[str, Any] = {"status": "success"}

        if data is not None:
            response_content["data"] = data

        if message:
            response_content["message"] = message

        return JSONResponse(status_code=status_code, content=response_content)


class ErrorMessages:
    """Common error messages"""

    # General errors
    TASK_ID_MISSING = "Task ID is missing"
    TASK_ID_EMPTY = "Task ID cannot be empty"
    TASK_NOT_FOUND = "Task not found"
    SERVICE_NAME_EMPTY = "Service name cannot be empty"
    FILE_NOT_FOUND = "File not found"
    INVALID_FILE_TYPE = "Invalid file type"
    UNSupported_FILE_TYPE = "Unsupported file type"
    NO_FILES_PROVIDED = "No files were included in the request"
    INTERNAL_SERVER_ERROR = "Internal server error"
    DATABASE_ERROR = "Database operation failed"
    VALIDATION_ERROR = "Validation failed"

    # File related errors
    FILE_UPLOAD_FAILED = "File upload failed"
    FILE_READ_FAILED = "Failed to read file"
    LOG_FILE_NOT_FOUND = "Log file not found"
    LOG_FILE_READ_FAILED = "Failed to read log file"

    # Task related errors
    TASK_CREATION_FAILED = "Failed to create task"
    TASK_UPDATE_FAILED = "Failed to update task"
    TASK_DELETION_FAILED = "Failed to delete task"
    TASK_STOP_FAILED = "Failed to stop task"
    TASK_NO_RESULTS = "No results found for this task"
    ANALYSIS_NOT_FOUND = "Analysis not found for this task"

    # Configuration related errors
    CONFIG_NOT_FOUND = "Configuration not found"
    CONFIG_ALREADY_EXISTS = "Configuration key already exists"
    INVALID_CONFIG = "Invalid configuration"
    MISSING_AI_CONFIG = "Missing AI service configuration"

    # Authentication related errors
    UNAUTHORIZED = "Unauthorized access"
    INVALID_CREDENTIALS = "Invalid credentials"
    TOKEN_EXPIRED = "Token expired"  # nosec
    INSUFFICIENT_PERMISSIONS = "Insufficient permissions"
