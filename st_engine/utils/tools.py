"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import base64
import json
import os
import queue
import re
from functools import lru_cache
from typing import Dict, List, Tuple, Union

import tiktoken

from utils.logger import st_logger as logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SENSITIVE_KEYS = ["authorization"]


def mask_sensitive_data(data: Union[dict, list]) -> Union[dict, list]:
    """Masks sensitive information for safe logging.

    Args:
        data (Union[dict, list]): The data to mask.

    Returns:
        Union[dict, list]: The masked data.
    """

    if isinstance(data, dict):
        safe_dict = {}
        try:
            for key, value in data.items():
                if isinstance(key, str) and key.lower() in SENSITIVE_KEYS:
                    safe_dict[key] = "****"
                else:
                    safe_dict[key] = mask_sensitive_data(value)
        except Exception as e:
            logger.warning(f"Error masking sensitive data: {str(e)}")
            return data
        return safe_dict
    elif isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    else:
        return data


def mask_sensitive_command(command_list: list) -> list:
    """
    Masks sensitive command for safe logging.

    Args:
        command_list (list): The list of commands to mask.

    Returns:
        list: The masked command list.
    """
    if isinstance(command_list, list):
        safe_list = []
        try:
            for item in command_list:
                new_item = re.sub(
                    r'("Authorization"\s*:\s*").*?(")',
                    r"\1********\2",
                    item,
                    flags=re.IGNORECASE,
                )
                safe_list.append(new_item)
            return safe_list
        except Exception as e:
            logger.warning(f"Error masking sensitive command: {str(e)}")
            return command_list
    else:
        return command_list


def load_data(
    data_file: str, chat_type: int = 0, task_logger=None
) -> List[Tuple[str, Union[str, Dict]]]:
    """Load all stress test data.

    Args:
        data_file (str): Path to the JSONL file containing ids and prompts.
        chat_type (int): The chat type, 0 for text-only, 1 for multimodal (text and image).

    Returns:
        List[Tuple[str, Union[str, Dict]]]: A list of data, formatted as (id, prompt) or (id, {prompt, image_base64}).
    """
    logger = task_logger if task_logger else logger
    prompts = []
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    json_obj = json.loads(line.strip())

                    if "id" in json_obj and "prompt" in json_obj:
                        if chat_type == 1:  # Multimodal chat
                            prompt = json_obj["prompt"]
                            prompt_text = ""
                            image_path = None
                            if isinstance(prompt, list) and len(prompt) > 0:
                                prompt_text = prompt[0]
                            elif isinstance(prompt, str):
                                prompt_text = prompt

                            if "image_path" in json_obj:
                                if isinstance(json_obj["image_path"], list):
                                    image_path = json_obj["image_path"][0]
                                elif isinstance(json_obj["image_path"], str):
                                    image_path = json_obj["image_path"]
                            if image_path:
                                image_base64 = encode_image(image_path)
                                prompts.append(
                                    (
                                        json_obj["id"],
                                        {
                                            "prompt": prompt_text,
                                            "image_base64": image_base64,
                                        },
                                    )
                                )
                            else:
                                prompts.append((json_obj["id"], prompt_text))
                        else:  # Text-only chat
                            prompt = json_obj["prompt"]
                            if isinstance(prompt, list) and len(prompt) > 0:
                                # Take the first element from the prompts list
                                prompts.append((json_obj["id"], prompt[0]))
                            elif isinstance(prompt, str):
                                prompts.append((json_obj["id"], prompt))
                            else:
                                logger.warning(f"Invalid prompt format: {line}")
                except json.JSONDecodeError:
                    logger.error(f"Error parsing line: {line}")
    except Exception as e:
        logger.error(f"Error loading prompts: {str(e)}")

    return prompts


def init_prompt_queue(
    chat_type: int = 0,
    data_file: str = os.path.join(BASE_DIR, "data", "prompts", "0.jsonl"),
    task_logger=None,
) -> queue.Queue:
    """Initializes the test data queue based on the chat type.

    Args:
        chat_type (int): The chat type, 0 for text-only, 1 for multimodal.
        data_file (str, optional): The path to the data file. If None, it's automatically selected based on chat_type.
        task_logger: An optional task-specific logger instance.

    Returns:
        queue.Queue: A queue containing the data.
    """
    logger = task_logger if task_logger else logger
    if chat_type == 0:
        data_file = os.path.join(BASE_DIR, "data", "prompts", "0.jsonl")
    else:
        data_file = os.path.join(BASE_DIR, "data", "prompts", "1.jsonl")

    # logger.info(f"Initializing data queue for chat_type={chat_type}")

    if not os.path.exists(data_file):
        logger.error(f"Data file not found: {data_file}")
        raise ValueError(f"Data file not found: {data_file}")

    q: queue.Queue[Tuple[str, Union[str, Dict]]] = queue.Queue()

    try:
        prompts = load_data(data_file, chat_type, logger)
        if not prompts:
            logger.error("No prompts were loaded from the data file")
            raise ValueError("No prompts were loaded from the data file")

        for prompt_id, prompt_data in prompts:
            try:
                q.put_nowait((prompt_id, prompt_data))
            except queue.Full:
                logger.error("Queue is full, cannot add more items")
                raise RuntimeError("Queue is full, cannot add more items")
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred while adding an item to the queue: {str(e)}"
                )
                raise RuntimeError(
                    f"An unexpected error occurred while adding an item to the queue: {str(e)}"
                )

        # logger.info(f"Successfully initialized queue with {q.qsize()} prompts")
        return q

    except Exception as e:
        logger.error(f"Failed to initialize prompt queue: {str(e)}")
        raise RuntimeError(f"Failed to initialize prompt queue: {str(e)}")


def encode_image(image_path):
    """Encodes an image file into a base64 string.

    Args:
        image_path (str): The path to the image file to encode.

    Returns:
        str: The base64 encoded image string.
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


@lru_cache(maxsize=128)
def get_tokenizer(model_name):
    """Gets the tokenizer for a specified model, using LRU cache to reduce creation overhead.

    Args:
        model_name (str): The name of the model to get the tokenizer for.

    Returns:
        tiktoken.Encoding: The tokenizer for the specified model.
    """
    try:
        # Get the appropriate encoder based on the model name
        if "gpt-4" in model_name:
            return tiktoken.encoding_for_model("gpt-4")
        elif "gpt-3.5" in model_name:
            return tiktoken.encoding_for_model("gpt-3.5-turbo")
        elif "claude" in model_name:
            # Claude uses tokenization similar to GPT-4
            return tiktoken.encoding_for_model("gpt-4")
        else:
            # Default to cl100k_base encoder
            # return tiktoken.get_encoding("cl100k_base")
            return tiktoken.encoding_for_model("gpt-3.5-turbo")
    except Exception as e:
        # If getting the tokenizer fails, return None, and a simple estimation will be used later
        logger.warning(f"Failed to get tokenizer: {str(e)}, will use simple estimation")
        return None


def count_tokens(text, model_name="gpt-3.5-turbo"):
    """Calculates the number of tokens in a text.

    Args:
        text (str): The text to calculate the number of tokens for.
        model_name (str): The name of the model to use for tokenization.

    Returns:
        int: The number of tokens in the text.
    """
    try:
        # Try to use the standard tokenizer
        tokenizer = get_tokenizer(model_name)
        if tokenizer:
            return len(tokenizer.encode(text))
        else:
            return len(text) // 4
    except Exception as e:
        # Use simple estimation on error
        logger.warning(
            f"Standard token counting failed: {str(e)}, using simple estimation"
        )
        return len(text) // 4


def calculate_custom_metrics(task_id, global_task_queue, exc_time):
    """Calculates custom performance metrics."""
    task_logger = logger.bind(task_id=task_id)
    custom_metrics_result = {
        "reqs_num": 0,
        "req_throughput": 0,
        "completion_tps": 0,
        "total_tps": 0,
        "avg_total_tokens_per_req": 0,
        "avg_completion_tokens_per_req": 0,
    }

    completion_tokens_list = []
    while not global_task_queue["completion_tokens_queue"].empty():
        try:
            element = global_task_queue["completion_tokens_queue"].get_nowait()
            completion_tokens_list.append(element)
        except queue.Empty:
            break
    completion_tokens = sum(completion_tokens_list)

    custom_metrics_result["reqs_num"] = len(completion_tokens_list)

    all_tokens_list = []
    while not global_task_queue["all_tokens_queue"].empty():
        try:
            element = global_task_queue["all_tokens_queue"].get_nowait()
            all_tokens_list.append(element)
        except queue.Empty:
            break
    all_tokens = sum(all_tokens_list)

    if exc_time is not None and exc_time > 0:
        custom_metrics_result["completion_tps"] = completion_tokens / exc_time
        custom_metrics_result["total_tps"] = all_tokens / exc_time
        custom_metrics_result["req_throughput"] = (
            custom_metrics_result["reqs_num"] / exc_time
        )
    else:
        task_logger.warning(
            f"Invalid test execution time ({exc_time}s), throughput-related metrics will be set to 0."
        )

    if len(all_tokens_list) > 0:
        custom_metrics_result["avg_total_tokens_per_req"] = sum(all_tokens_list) / len(
            all_tokens_list
        )

    if len(completion_tokens_list) > 0:
        custom_metrics_result["avg_completion_tokens_per_req"] = sum(
            completion_tokens_list
        ) / len(completion_tokens_list)

    task_logger.info(f"custom_metrics_result: {custom_metrics_result}")
    return custom_metrics_result


def get_locust_stats(task_id, environment_stats) -> list:
    """Gets and formats Locust statistics for database use."""
    task_logger = logger.bind(task_id=task_id)
    all_metrics_list = []
    try:
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for name, endpoint in environment_stats.entries.items():
            raw_params = {
                "task_id": task_id,
                "metric_type": endpoint.name,
                "num_requests": endpoint.num_requests,
                "num_failures": endpoint.num_failures,
                "avg_latency": endpoint.avg_response_time,
                "min_latency": endpoint.min_response_time,
                "max_latency": endpoint.max_response_time,
                "median_latency": endpoint.median_response_time,
                "p90_latency": endpoint.get_response_time_percentile(0.9),
                "avg_content_length": endpoint.avg_content_length,
                "rps": endpoint.total_rps,
                "created_at": current_time,
            }
            all_metrics_list.append(raw_params)

        task_logger.info(
            f"List of performance metrics collected by Locust: {all_metrics_list}"
        )
    except Exception as e:
        task_logger.error(f"Failed to get Locust statistics results: {str(e)}")
        raise RuntimeError(f"Failed to get Locust statistics results: {str(e)}")
    return all_metrics_list
