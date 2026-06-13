from __future__ import annotations

from pathlib import Path
from typing import Optional

from privacybox.config.schema import PrivacyBoxConfig
from privacybox.config.loader import get_credentials_dir
from privacybox.llm.base import LLMProvider
from privacybox.utils.types import ComposeResult, PrivacyTier


OPENAI_SYSTEM_PROMPT = """You are a Docker Compose expert. Generate a complete docker-compose.yml based on user requirements.

Rules:
1. All ports bind to 127.0.0.1 unless user explicitly requests public access
2. Volumes mount to ./data/<service_name>/
3. No privileged mode
4. No docker.socket mounts
5. Use environment variables for secrets (referenced from .env file)
6. Include healthcheck where appropriate

Output format: Return a JSON object with:
- compose_yaml: the complete docker-compose.yml as a string
- metadata: object with name, description, ports fields

Be precise and production-ready.
"""


class OpenAIProvider(LLMProvider):
    def __init__(self, config: PrivacyBoxConfig):
        self.config = config
        self._provider_cfg = config.llm.providers.get("openai", {})

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_api_key(self) -> str:
        key_file = self._provider_cfg.get("api_key_file", "")
        if key_file:
            path = Path(key_file)
            if path.exists():
                return path.read_text().strip()
        return ""

    def _get_model(self) -> str:
        return self._provider_cfg.get("model", "gpt-4o")

    def is_available(self) -> bool:
        return bool(self._get_api_key())

    def generate_compose(
        self,
        user_input: str,
        privacy_tier: PrivacyTier,
        platform: str = "",
        template_hints: Optional[list[dict]] = None,
    ) -> ComposeResult:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("需要安装 openai 包: pip install privacybox[openai]")

        client = OpenAI(api_key=self._get_api_key())

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "generate_compose",
                    "description": "Generate docker-compose.yml from user requirements",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compose_yaml": {
                                "type": "string",
                                "description": "The complete docker-compose.yml content",
                            },
                            "metadata": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "ports": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                    },
                                },
                                "required": ["name", "description", "ports"],
                            },
                        },
                        "required": ["compose_yaml", "metadata"],
                    },
                },
            }
        ]

        messages = [
            {"role": "system", "content": OPENAI_SYSTEM_PROMPT},
            {"role": "user", "content": f"Privacy tier: T{int(privacy_tier)}\n\n{user_input}"},
        ]

        response = client.chat.completions.create(
            model=self._get_model(),
            messages=messages,
            tools=tools,
            tool_choice={"type": "function", "function": {"name": "generate_compose"}},
            temperature=0.2,
        )

        raw = response.choices[0].message.content or ""
        tool_calls = response.choices[0].message.tool_calls or []

        data = {}
        if tool_calls:
            import json
            data = json.loads(tool_calls[0].function.arguments)

        return ComposeResult(
            yaml=data.get("compose_yaml", ""),
            metadata=data.get("metadata", {}),
            provider_used="openai",
            raw_response=raw or str(data),
        )

    def validate_and_retry(
        self,
        previous_yaml: str,
        error_info: str,
        max_retries: int = 3,
    ) -> ComposeResult:
        from openai import OpenAI

        client = OpenAI(api_key=self._get_api_key())

        messages = [
            {"role": "system", "content": "Fix the following docker-compose.yml."},
            {
                "role": "user",
                "content": f"The YAML was invalid:\n\n{previous_yaml}\n\nError:\n{error_info}\n\nOutput ONLY the corrected YAML.",
            },
        ]

        response = client.chat.completions.create(
            model=self._get_model(),
            messages=messages,
            temperature=0.1,
        )

        raw = response.choices[0].message.content or ""
        return ComposeResult(
            yaml=raw,
            metadata={},
            provider_used="openai",
            raw_response=raw,
            retries=1,
        )

    def estimate_cost(self, input_chars: int) -> str:
        tokens = input_chars // 4
        cost = tokens * 0.00001
        return f"~${cost:.4f}"
