"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class UploadedFileInfo(BaseModel):
    """
    Represents the metadata for a single uploaded file.

    Attributes:
        originalname: The original name of the uploaded file.
        path: The path where the file is stored on the server.
        size: The size of the file in bytes.
    """

    originalname: str
    path: str
    size: int


class UploadFileRsp(BaseModel):
    """
    Defines the response structure after a file upload operation.

    Attributes:
        message: A message indicating the result of the upload.
        task_id: The identifier for the associated task.
        files: A list of `UploadedFileInfo` objects for each uploaded file.
        cert_config: An optional dictionary for certificate configuration.
        test_data: An optional string for test data file path.
    """

    message: str
    task_id: str
    files: List[UploadedFileInfo]
    cert_config: Optional[dict] = None
    test_data: Optional[str] = None


class UploadFileReq(BaseModel):
    """
    Defines the request structure for a file upload.

    Attributes:
        type: The type of upload, defaults to "cert".
        cert_type: The specific type of certificate, if applicable.
        task_id: The identifier for the task to which the files are being uploaded.
    """

    type: str = Field(default="cert")
    cert_type: Optional[str]
    task_id: str
