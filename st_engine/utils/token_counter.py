"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import hashlib
import logging
import threading
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, Optional, Union

try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore

try:
    from transformers import AutoTokenizer
except ImportError:
    AutoTokenizer = None  # type: ignore

logger = logging.getLogger(__name__)


TOKENIZER_CACHE_SIZE = 16  # Cache size for tokenizer instances
DEFAULT_TOKEN_RATIO = 4  # Estimate: 1 token ≈ 4 bytes UTF-8


class TokenCounter(ABC):
    """Abstract interface: Unify different model token counting methods"""

    @abstractmethod
    def encode(self, text: str) -> list[int]:
        pass

    def count_tokens(self, text: str) -> int:
        if not text or not text.strip():
            return 0
        try:
            return len(self.encode(text))
        except Exception as e:
            logger.warning(f"Tokenization failed: {e}, falling back to estimation")
            return max(
                1, len(text.encode("utf-8", errors="ignore")) // DEFAULT_TOKEN_RATIO
            )


class TikTokenCounter(TokenCounter):
    def __init__(self, model_name: str):
        if tiktoken is None:
            raise ValueError("tiktoken not installed. Please run: pip install tiktoken")
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def encode(self, text: str) -> list[int]:
        return self.encoding.encode(text)


class TransformersTokenCounter(TokenCounter):
    def __init__(self, model_name: str):
        if AutoTokenizer is None:
            raise ValueError(
                "transformers not installed. Please run: pip install transformers"
            )
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )

    def encode(self, text: str) -> list[int]:
        return self.tokenizer.encode(text, add_special_tokens=False)


class RuleBasedTokenCounter(TokenCounter):
    """Lightweight rule-based estimation, for fallback"""

    def encode(self, text: str) -> list[int]:
        # Simple tokenization (English space + Chinese characters)
        import re

        tokens = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        return list(range(len(tokens)))  # Only return length

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        # More reasonable mixed estimation
        utf8_len = len(text.encode("utf-8"))
        chinese_chars = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
        other_chars = len(text) - chinese_chars
        # Chinese: 2~3 bytes per token, English: 4 bytes per token
        est_tokens = (chinese_chars * 1.5) + (other_chars / 4)
        return int(max(1, round(est_tokens)))


# === Global Tokenizer factory (thread-safe + LRU cache)===


@lru_cache(maxsize=TOKENIZER_CACHE_SIZE)
def get_token_counter(model_name: str) -> TokenCounter:
    """
    Get the token counter for the corresponding model, priority:
    1. transformers (Llama/Qwen/Other HuggingFace models)
    2. tiktoken (GPT series or other models) - default
    3. Rule-based fallback - only when tiktoken fails
    """
    model_lower = model_name.lower().strip()

    try:
        # Check if the model is a HuggingFace model (Llama/Qwen etc.)
        # Extended matching patterns, including more possible model name formats
        huggingface_patterns = [
            "llama",
            "qwen",
            "baichuan",
            "chatglm",
            "models--qwen",
            "models--llama",
            "models--baichuan",
            "models--chatglm",
            "--qwen--",
            "--llama--",
            "--baichuan--",
            "--chatglm--",
        ]

        if AutoTokenizer is not None and any(
            pattern in model_lower for pattern in huggingface_patterns
        ):
            try:
                logger.debug(f"Using transformers tokenizer for model: {model_name}")
                return TransformersTokenCounter(model_name)
            except Exception as e:
                logger.info(f"Falling back from transformers tokenizer due to: {e}")

        # Use tiktoken (for GPT series or other models)
        if tiktoken:
            try:
                logger.debug(f"Using tiktoken for model: {model_name}")
                return TikTokenCounter(model_name)
            except Exception as e:
                logger.info(
                    f"TikToken failed for '{model_name}': {e}, falling back to rule-based"
                )

        # Use RuleBasedTokenCounter
        logger.debug(f"Using rule-based token counter for model: {model_name}")
        return RuleBasedTokenCounter()

    except Exception as e:
        logger.warning(f"Failed to initialize tokenizer: {e}, using rule-based")
        return RuleBasedTokenCounter()


# === Core function: Efficient token counting (without caching the text itself!)===


def count_tokens(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    """
    High-performance token counting function, for streaming stress testing.

    ⚠️ Note: Do not cache the token results of long texts! This will cause memory explosion.
    We only cache tokenizer instances.

    Args:
        text (str): Input text
        model_name (str): Model name (determines tokenizer type)

    Returns:
        int: Number of tokens
    """
    if not text or not text.strip():
        return 0

    try:
        counter = get_token_counter(model_name)
        return counter.count_tokens(text)
    except Exception as e:
        logger.warning(
            f"Token counting failed for model '{model_name}': {e}, using fallback"
        )
        # Final fallback
        utf8_bytes = len(text.encode("utf-8", errors="ignore"))
        return max(1, utf8_bytes // DEFAULT_TOKEN_RATIO)
