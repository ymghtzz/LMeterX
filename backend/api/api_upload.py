"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

from typing import List, Optional

from fastapi import APIRouter, File, Request, UploadFile

from model.upload import UploadFileRsp
from service.upload_service import upload_file_svc

# Create an API router for file upload endpoints
router = APIRouter()


@router.post("", response_model=UploadFileRsp)
async def upload_file(
    request: Request,
    type: str = "cert",
    cert_type: str = "cert_file",
    task_id: Optional[str] = None,
    file: List[UploadFile] = File(..., description="The file(s) to upload"),
):
    """
    Upload one or more files.

    This endpoint handles file uploads and can be used for different purposes
    based on the 'type' parameter. For example, it can be used to upload
    certificates or files related to a specific task.

    Args:
        type (str): The type of upload (e.g., "cert"). Defaults to "cert".
        cert_type (str): The specific type of certificate. Defaults to "cert_file".
        task_id (str, optional): The ID of the task to associate the upload with. Defaults to None.
        file (List[UploadFile]): A list of files to be uploaded.

    Returns:
        UploadFileRsp: A response object confirming the file upload.
    """
    return await upload_file_svc(request, file, type, cert_type, task_id)
