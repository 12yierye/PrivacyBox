from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from privacybox.utils.types import ComposeResult, PrivacyTier


class LLMProvider(ABC):
    """LLM provider abstraction — one implementation per model family."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and reachable."""
        ...

    @abstractmethod
    def generate_compose(
        self,
        user_input: str,
        privacy_tier: PrivacyTier,
        platform: str = "",
        template_hints: Optional[list[dict]] = None,
    ) -> ComposeResult:
        """Generate a docker-compose YAML from natural language."""
        ...

    @abstractmethod
    def validate_and_retry(
        self,
        previous_yaml: str,
        error_info: str,
        max_retries: int = 3,
    ) -> ComposeResult:
        """Retry with error feedback when YAML validation fails."""
        ...

    @abstractmethod
    def estimate_cost(self, input_chars: int) -> str:
        """Return a human-readable cost estimate for this request."""
        ...
