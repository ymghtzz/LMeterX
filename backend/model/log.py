"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from pydantic import BaseModel


class LogContentResponse(BaseModel):
    """
    Represents the response model for log content.

    Attributes:
        content: The content of the log file as a string.
        file_size: The size of the log file in bytes.
    """

    content: str
    file_size: int
