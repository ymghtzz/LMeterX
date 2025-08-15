"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import mimetypes
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import File, Form, HTTPException, Request, UploadFile
from starlette.responses import JSONResponse
from werkzeug.utils import secure_filename

from model.upload import UploadedFileInfo, UploadFileRsp
from utils.be_config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
    MAX_FILENAME_LENGTH,
    MAX_TASK_ID_LENGTH,
    UPLOAD_FOLDER,
)
from utils.error_handler import ErrorMessages, ErrorResponse
from utils.logger import logger
from utils.security import (
    safe_join,
    validate_file_extension,
    validate_file_size,
    validate_filename,
    validate_mime_type,
    validate_task_id,
    validate_upload_path,
)

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
    try:
        # Validate task_id
        validated_task_id = validate_task_id(task_id)

        # Create safe upload directory path using safe_join
        task_upload_dir = safe_join(UPLOAD_FOLDER, validated_task_id)

        # Validate upload path
        validate_upload_path(task_upload_dir, UPLOAD_FOLDER)

        os.makedirs(task_upload_dir, exist_ok=True)

        uploaded_files_info = []
        for file in files:
            if file and file.filename:
                # Validate filename
                validated_filename = validate_filename(file.filename)

                # Validate file extension
                validate_file_extension(validated_filename, ALLOWED_EXTENSIONS["cert"])

                # Read file content for validation
                file_content = await file.read()

                # Validate file size
                validate_file_size(len(file_content))

                # Validate MIME type
                validate_mime_type(file_content, validated_filename, "cert")

                # Reset file pointer for subsequent operations
                await file.seek(0)

                filename = secure_filename(validated_filename)
                # Use safe_join for final file path
                absolute_file_path = safe_join(task_upload_dir, filename)

                # Additional safety check for the final path
                validate_upload_path(absolute_file_path, UPLOAD_FOLDER)

                with open(absolute_file_path, "wb") as f:
                    f.write(file_content)

                file_info = {
                    "originalname": filename,
                    "path": absolute_file_path,  # Keep absolute path for file info
                    "size": os.path.getsize(absolute_file_path),
                }
                uploaded_files_info.append(file_info)
                logger.info(
                    f"Certificate file uploaded successfully, type: {cert_type}"
                )

        # Retrieve existing config for the task, if any.
        existing_config = get_task_cert_config(validated_task_id)
        # Determine the new config based on the uploaded files - use absolute paths
        uploaded_files_with_absolute_paths = []
        for file_info in uploaded_files_info:
            uploaded_files_with_absolute_paths.append(
                {
                    "originalname": file_info["originalname"],
                    "path": file_info["path"],  # Use absolute path for config
                    "size": file_info["size"],
                }
            )

        cert_config = determine_cert_config(
            uploaded_files_with_absolute_paths, cert_type, existing_config
        )
        # Save the updated configuration.
        save_task_cert_config(validated_task_id, cert_config)

        return uploaded_files_info, cert_config
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing certificate files: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_dataset_files(task_id: str, files: List[UploadFile]):
    """
    Processes uploaded dataset files, saves them, and returns file information.

    Args:
        task_id: The ID of the task.
        files: The list of uploaded files.

    Returns:
        A tuple containing the list of uploaded file info and the file path.
    """
    try:
        # Validate task_id
        validated_task_id = validate_task_id(task_id)

        # Create safe upload directory path using safe_join
        task_upload_dir = safe_join(UPLOAD_FOLDER, validated_task_id)

        # Validate upload path
        validate_upload_path(task_upload_dir, UPLOAD_FOLDER)

        os.makedirs(task_upload_dir, exist_ok=True)

        uploaded_files_info = []
        file_path = None

        for file in files:
            if file and file.filename:
                # Validate filename
                validated_filename = validate_filename(file.filename)

                # Validate file extension
                validate_file_extension(
                    validated_filename, ALLOWED_EXTENSIONS["dataset"]
                )

                # Read file content for validation
                file_content = await file.read()

                # Validate file size
                validate_file_size(len(file_content))

                # Validate MIME type
                validate_mime_type(file_content, validated_filename, "dataset")

                # Reset file pointer for subsequent operations
                await file.seek(0)

                filename = secure_filename(validated_filename)
                # Use safe_join for final file path
                absolute_file_path = safe_join(task_upload_dir, filename)

                # Additional safety check for the final path
                validate_upload_path(absolute_file_path, UPLOAD_FOLDER)

                with open(absolute_file_path, "wb") as f:
                    f.write(file_content)

                file_info = {
                    "originalname": filename,
                    "path": absolute_file_path,  # Keep absolute path for file info
                    "size": os.path.getsize(absolute_file_path),
                }
                uploaded_files_info.append(file_info)
                file_path = absolute_file_path  # Use absolute path for test_data
                logger.info(f"Dataset file uploaded successfully: {filename}")

        return uploaded_files_info, file_path
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing dataset files: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def upload_file_svc(
    request: Request,
    task_id: Optional[str],
    file_type: Optional[str],
    cert_type: Optional[str],
    files: List[UploadFile],
):
    """
    Main service function for handling file uploads.

    It validates the request, generates a task ID if not provided, and routes
    the processing to the appropriate handler based on the file type.
    """
    if files and files[0].filename:
        logger.info(f"Uploading file: {files[0].filename}")

    if not files or not files[0].filename:
        return ErrorResponse.bad_request(ErrorMessages.NO_FILES_PROVIDED)

    # Generate a new task_id if one is not provided.
    effective_task_id = str(uuid.uuid4())

    # Validate task_id if provided
    if task_id:
        try:
            effective_task_id = validate_task_id(task_id)
            # logger.info(f"Validated task_id: {effective_task_id}")
        except ValueError as e:
            logger.error(f"Task ID validation failed: {e}")
            return ErrorResponse.bad_request(str(e))

    if not file_type:
        file_type = "dataset"

    if file_type == "cert":
        # logger.info(f"Processing certificate files for task: {effective_task_id}")
        uploaded_files, cert_config = await process_cert_files(
            effective_task_id, files, cert_type
        )
        return UploadFileRsp(
            message="Files uploaded successfully",
            task_id=effective_task_id,
            files=[UploadedFileInfo(**f) for f in uploaded_files],
            cert_config=cert_config,
        )

    if file_type == "dataset":
        # logger.info(f"Processing dataset files for task: {effective_task_id}")
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
    # e.g., if file_type == "dataset": ...

    return ErrorResponse.bad_request(
        f"{ErrorMessages.UNSupported_FILE_TYPE}: {file_type}"
    )
