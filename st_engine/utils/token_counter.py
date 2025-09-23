"""
Author: Charm
Copyright (c) 2025, All Rights Reserved.
"""

import logging
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, List, Optional

tiktoken: Optional[Any] = None

try:
    import tiktoken
except ImportError:
    pass

logger = logging.getLogger(__name__)


TOKENIZER_CACHE_SIZE = 16  # Cache size for tokenizer instances
DEFAULT_TOKEN_RATIO_EN = 4  # Estimate: 1 token ≈ 4 bytes UTF-8
DEFAULT_TOKEN_RATIO_CN = 3  # Estimate: 1 token ≈ 3 bytes UTF-8


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
            return self._fallback_token_estimate(text)

    def _fallback_token_estimate(self, text: str) -> int:
        """Fallback: Based on UTF-8 bytes + mixed estimation of English and Chinese"""
        if not text:
            return 0
        utf8_bytes = len(text.encode("utf-8", errors="ignore"))
        chinese_chars = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
        # Chinese characters are estimated to be 3 bytes/token, others are estimated to be 4 bytes/token
        est_tokens = chinese_chars + max(
            0, (utf8_bytes - chinese_chars * 3) // DEFAULT_TOKEN_RATIO_EN
        )
        return max(1, int(est_tokens))


class TikTokenCounter(TokenCounter):
    """TikTokenCounter: Use tiktoken for token counting"""

    def __init__(self, model_name: str):
        if tiktoken is None:
            raise ValueError("tiktoken not installed. Please run: pip install tiktoken")
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

    def encode(self, text: str) -> list[int]:
        return self.encoding.encode(text)


class RuleBasedTokenCounter(TokenCounter):
    """
    Lightweight rule-based token counter (for fallback when tiktoken fails)
    Do not implement precise encode, only provide reasonable estimation of count_tokens.
    """

    # Precompiled regex for performance

    _TOKENIZER_REGEX = re.compile(r"[\w]+|[^\w\s]", re.UNICODE)

    def encode(self, text: str) -> List[int]:
        """
        Rule-based does not provide real token IDs, only for interface compatibility.
        Returning an empty list or throwing NotImplementedError is more reasonable, but for compatibility, a simple implementation is retained.
        """
        # Return virtual token IDs (only length is meaningful)
        tokens = self._tokenize(text)
        return list(range(len(tokens)))

    def count_tokens(self, text: str) -> int:
        """Efficient token estimation based on rules"""
        if not text or not text.strip():
            return 0

        tokens = self._tokenize(text)
        return len(tokens)

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: English by space/punctuation, Chinese by characters, support emoji"""
        # Method 1: Basic tokenization (word + punctuation)
        basic_tokens = self._TOKENIZER_REGEX.findall(text)

        # Method 2: Character-by-character processing of Chinese characters and emoji (closer to real tokenizer behavior)
        refined_tokens = []
        for token in basic_tokens:
            # If it is pure Chinese or emoji, split into single characters
            if all(self._is_cjk_or_emoji(char) for char in token):
                refined_tokens.extend(list(token))
            else:
                refined_tokens.append(token)
        return refined_tokens

    @staticmethod
    def _is_cjk_or_emoji(char: str) -> bool:
        """Determine if it is a CJK character or emoji"""
        if len(char) != 1:
            return False
        cp = ord(char)
        # CJK Unified Ideographs
        if 0x4E00 <= cp <= 0x9FFF:
            return True
        # Emoji range (simplified)
        if (
            (0x1F600 <= cp <= 0x1F64F)  # emoticons
            or (0x1F300 <= cp <= 0x1F5FF)  # symbols & pictographs
            or (0x1F680 <= cp <= 0x1F6FF)  # transport & map
            or (0x1F1E0 <= cp <= 0x1F1FF)  # flags (iOS)
            or (0x2600 <= cp <= 0x26FF)  # misc symbols
        ):
            return True
        return False

    def _fallback_token_estimate(self, text: str) -> int:
        """Reuse parent class fallback logic"""
        return super()._fallback_token_estimate(text)


# === Global Tokenizer factory (thread-safe + LRU cache)===
@lru_cache(maxsize=TOKENIZER_CACHE_SIZE)
def get_token_counter(model_name: str) -> TokenCounter:
    """
    Get the token counter for the corresponding model.
    """
    try:
        # Use tiktoken
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
        chinese_chars = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
        est_tokens = chinese_chars + max(
            0, (utf8_bytes - chinese_chars * 3) // DEFAULT_TOKEN_RATIO_EN
        )
        return max(1, int(est_tokens))
