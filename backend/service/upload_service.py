"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import File, Form, Request, UploadFile
from starlette.responses import JSONResponse
from werkzeug.utils import secure_filename

from model.upload import UploadedFileInfo, UploadFileRsp
from utils.be_config import UPLOAD_FOLDER
from utils.logger import logger

# Ensure the global upload folder exists.
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Define allowed file extensions for different upload types.
ALLOWED_EXTENSIONS = {
    "cert": {"crt", "pem", "key"},
    "dataset": {"json", "csv", "txt", "jsonl"},
}

# In-memory dictionary to store certificate configurations per task.
_task_cert_configs: Dict[str, Dict[str, str]] = {}


def save_task_cert_config(task_id: str, config: Dict[str, str]):
    """Saves the certificate configuration for a specific task."""
    _task_cert_configs[task_id] = config


def get_task_cert_config(task_id: str) -> Dict[str, str]:
    """Retrieves the certificate configuration for a specific task."""
    return _task_cert_configs.get(task_id, {"cert_file": "", "key_file": ""})


def determine_cert_config(
    files: List[Dict[str, Any]],
    cert_type: Optional[str] = None,
    existing_config: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Determines the certificate configuration based on uploaded files and specified type.
    It preserves existing configurations if not overridden.

    Args:
        files: A list of dictionaries, each representing an uploaded file.
        cert_type: The type of certificate ('combined', 'cert_file', 'key_file').
        existing_config: The existing certificate configuration for the task.

    Returns:
        An updated dictionary with 'cert_file' and 'key_file' paths.
    """
    config = existing_config if existing_config else {"cert_file": "", "key_file": ""}

    if not files:
        return config

    if cert_type == "combined":
        # A combined file (e.g., PEM) overrides both cert and key.
        config["cert_file"] = files[0]["path"]
        config["key_file"] = ""
    elif cert_type == "cert_file":
        # Updates only the certificate file, preserving the key file.
        config["cert_file"] = files[0]["path"]
    elif cert_type == "key_file":
        # Updates only the key file, preserving the certificate file.
        config["key_file"] = files[0]["path"]
    else:
        logger.warning(f"Certificate type not specified or invalid: {cert_type}")

    return config


def allowed_file(filename: str, file_type: str) -> bool:
    """Checks if the file extension is allowed for the given file type."""
    return "." in filename and filename.rsplit(".", 1)[
        1
    ].lower() in ALLOWED_EXTENSIONS.get(file_type, set())


async def process_cert_files(
    task_id: str, files: List[UploadFile], cert_type: Optional[str]
):
    """
    Processes uploaded certificate and key files, saves them, and determines the configuration.

    Args:
        task_id: The ID of the task.
        files: The list of uploaded files.
        cert_type: The type of certificate being uploaded.

    Returns:
        A tuple containing the list of uploaded file info and the certificate configuration.
    """
    task_upload_dir = os.path.join(UPLOAD_FOLDER, task_id)
    os.makedirs(task_upload_dir, exist_ok=True)

    uploaded_files_info = []
    for file in files:
        if file and file.filename and allowed_file(file.filename, "cert"):
            filename = secure_filename(file.filename)
            file_path = os.path.join(task_upload_dir, filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())

            file_info = {
                "originalname": filename,
                "path": file_path,
                "size": os.path.getsize(file_path),
            }
            uploaded_files_info.append(file_info)
            logger.info(f"Certificate file uploaded successfully, type: {cert_type}")

    # Retrieve existing config for the task, if any.
    existing_config = get_task_cert_config(task_id)
    # Determine the new config based on the uploaded files.
    cert_config = determine_cert_config(uploaded_files_info, cert_type, existing_config)
    # Save the updated configuration.
    save_task_cert_config(task_id, cert_config)

    return uploaded_files_info, cert_config


async def process_dataset_files(task_id: str, files: List[UploadFile]):
    """
    Processes uploaded dataset files, saves them, and returns file information.

    Args:
        task_id: The ID of the task.
        files: The list of uploaded files.

    Returns:
        A tuple containing the list of uploaded file info and the file path.
    """
    task_upload_dir = os.path.join(UPLOAD_FOLDER, task_id)
    os.makedirs(task_upload_dir, exist_ok=True)

    uploaded_files_info = []
    file_path = None

    for file in files:
        if file and file.filename and allowed_file(file.filename, "dataset"):
            filename = secure_filename(file.filename)
            file_path = os.path.join(task_upload_dir, filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())

            file_info = {
                "originalname": filename,
                "path": file_path,
                "size": os.path.getsize(file_path),
            }
            uploaded_files_info.append(file_info)
            logger.info(f"Dataset file uploaded successfully: {filename}")

    return uploaded_files_info, file_path


async def upload_file_svc(
    request: Request,
    files: List[UploadFile] = File(..., description="The files to upload"),
    type: str = Form("cert"),
    cert_type: Optional[str] = Form(None),
    task_id: Optional[str] = Form(None),
):
    """
    Main service function for handling file uploads.

    It validates the request, generates a task ID if not provided, and routes
    the processing to the appropriate handler based on the file type.
    """

    if not files or not files[0].filename:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error": "No files were included in the request",
            },
        )

    # Generate a new task_id if one is not provided.
    effective_task_id = task_id if task_id else str(uuid.uuid4())

    if type == "cert":
        uploaded_files, cert_config = await process_cert_files(
            effective_task_id, files, cert_type
        )
        return UploadFileRsp(
            message="Files uploaded successfully",
            task_id=effective_task_id,
            files=[UploadedFileInfo(**f) for f in uploaded_files],
            cert_config=cert_config,
        )

    if type == "dataset":
        uploaded_files, file_path = await process_dataset_files(
            effective_task_id, files
        )
        return UploadFileRsp(
            message="Dataset files uploaded successfully",
            task_id=effective_task_id,
            files=[UploadedFileInfo(**f) for f in uploaded_files],
            test_data=file_path,  # Return the file path for backend processing
        )

    # In the future, it could handle other file types here.
    # e.g., if type == "dataset": ...

    return JSONResponse(
        status_code=400,
        content={"status": "error", "error": f"Unsupported file type: {type}"},
    )
