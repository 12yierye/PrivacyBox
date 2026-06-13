from __future__ import annotations

from pathlib import Path
from typing import Optional

from privacybox.config.schema import PrivacyBoxConfig
from privacybox.llm.base import LLMProvider
from privacybox.utils.types import ComposeResult, PrivacyTier


CLAUDE_SYSTEM_PROMPT = """You are a Docker Compose expert. Your task is to generate production-ready docker-compose.yml files.

Think step by step:
1. Identify the main service and its dependencies
2. Choose appropriate base images with version tags
3. Configure networking respecting privacy constraints
4. Set up volumes for persistent data
5. Add health checks for critical services

Output format:
- Return ONLY a complete docker-compose.yml (valid YAML)
- End with a comment block:
# METADATA
# name: <service-name>
# description: <one-line description>
# ports: <comma-separated ports>

Security rules (never override):
- Bind ports to 127.0.0.1 by default
- Never use privileged mode
- Never mount docker.socket
- Mount volumes under ./data/<service_name>/
"""


class ClaudeProvider(LLMProvider):
    def __init__(self, config: PrivacyBoxConfig):
        self.config = config
        self._provider_cfg = config.llm.providers.get("claude", {})

    @property
    def provider_name(self) -> str:
        return "claude"

    def _get_api_key(self) -> str:
        key_file = self._provider_cfg.get("api_key_file", "")
        if key_file:
            path = Path(key_file)
            if path.exists():
                return path.read_text().strip()
        return ""

    def _get_model(self) -> str:
        return self._provider_cfg.get("model", "claude-sonnet-4-20250514")

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
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError("需要安装 anthropic 包: pip install privacybox[claude]")

        client = Anthropic(api_key=self._get_api_key())

        prompt = f"""User request: {user_input}
Privacy level: T{int(privacy_tier)} (1=isolated 2=localhost 3=VPN 4=LAN 5=public)
Platform: {platform or 'linux'}

Generate a complete docker-compose.yml. Think step by step, then output the YAML."""

        response = client.messages.create(
            model=self._get_model(),
            max_tokens=4000,
            system=CLAUDE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        raw = response.content[0].text if response.content else ""

        yaml_str = self._extract_yaml(raw)
        metadata = self._extract_metadata(raw)

        return ComposeResult(
            yaml=yaml_str,
            metadata=metadata,
            provider_used="claude",
            raw_response=raw,
        )

    def validate_and_retry(
        self,
        previous_yaml: str,
        error_info: str,
        max_retries: int = 3,
    ) -> ComposeResult:
        from anthropic import Anthropic

        client = Anthropic(api_key=self._get_api_key())

        response = client.messages.create(
            model=self._get_model(),
            max_tokens=4000,
            system="Fix the following docker-compose.yml. Output ONLY corrected YAML.",
            messages=[
                {
                    "role": "user",
                    "content": f"Invalid YAML:\n\n{previous_yaml}\n\nError:\n{error_info}",
                }
            ],
            temperature=0.1,
        )

        raw = response.content[0].text if response.content else ""

        return ComposeResult(
            yaml=raw,
            metadata={},
            provider_used="claude",
            raw_response=raw,
            retries=1,
        )

    def estimate_cost(self, input_chars: int) -> str:
        tokens = input_chars // 4
        cost = tokens * 0.000015
        return f"~${cost:.4f}"

    def _extract_yaml(self, text: str) -> str:
        lines = text.split("\n")
        yaml_lines = []
        in_yaml = False
        for line in lines:
            if line.strip().startswith("version:"):
                in_yaml = True
            if in_yaml:
                if line.strip().startswith("# METADATA"):
                    break
                yaml_lines.append(line)
        if yaml_lines:
            return "\n".join(yaml_lines)
        return text

    def _extract_metadata(self, text: str) -> dict:
        meta = {}
        for line in text.split("\n"):
            if line.strip().startswith("# METADATA"):
                continue
            if line.strip().startswith("# "):
                key_value = line.strip("# ").strip()
                if ": " in key_value:
                    key, value = key_value.split(": ", 1)
                    meta[key.strip()] = value.strip()
        return meta
