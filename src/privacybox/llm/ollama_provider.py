from __future__ import annotations

from typing import Optional

import yaml

from privacybox.config.schema import PrivacyBoxConfig
from privacybox.config.loader import get_credentials_dir
from privacybox.llm.base import LLMProvider
from privacybox.utils.types import ComposeResult, PrivacyTier


OLLAMA_SYSTEM_PROMPT = """You are a Docker Compose expert. Generate a valid docker-compose.yml based on the user's request.

Rules:
- All ports use 127.0.0.1 binding (localhost only)
- Volumes mount to ./data/<service_name>/
- No privileged mode
- No docker.socket mounts
- Output ONLY valid YAML, no explanations
- Include metadata comment block at the end:
# METADATA
# name: <service-name>
# description: <one-line description>
# ports: <comma-separated list of exposed ports>
"""


class OllamaProvider(LLMProvider):
    def __init__(self, config: PrivacyBoxConfig):
        self.config = config
        self._provider_cfg = config.llm.providers.get("ollama", {})

    @property
    def provider_name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            import httpx
            endpoint = self._get_endpoint()
            resp = httpx.get(f"{endpoint}/api/tags", timeout=5)
            return resp.is_success
        except Exception:
            return False

    def _get_endpoint(self) -> str:
        return self._provider_cfg.get("endpoint", "http://localhost:11434")

    def _get_model(self) -> str:
        return self._provider_cfg.get("model", "llama3")

    def generate_compose(
        self,
        user_input: str,
        privacy_tier: PrivacyTier,
        platform: str = "",
        template_hints: Optional[list[dict]] = None,
    ) -> ComposeResult:
        import httpx

        prompt = f"{OLLAMA_SYSTEM_PROMPT}\n\nUser request: {user_input}\nPrivacy tier: T{int(privacy_tier)}"

        if template_hints:
            hints_str = "\n".join(
                f"- {h.get('name', 'unknown')}: {h.get('description', '')}"
                for h in template_hints
            )
            prompt += f"\n\nRelevant templates:\n{hints_str}"

        endpoint = self._get_endpoint()
        model = self._get_model()

        response = httpx.post(
            f"{endpoint}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        raw = data.get("response", "")

        yaml_str = self._extract_yaml(raw)
        metadata = self._extract_metadata(raw)

        return ComposeResult(
            yaml=yaml_str,
            metadata=metadata,
            provider_used="ollama",
            raw_response=raw,
        )

    def validate_and_retry(
        self,
        previous_yaml: str,
        error_info: str,
        max_retries: int = 3,
    ) -> ComposeResult:
        import httpx

        prompt = (
            f"The previous docker-compose.yml was invalid:\n\n{previous_yaml}\n\n"
            f"Error: {error_info}\n\n"
            f"Please fix and output a corrected version. ONLY valid YAML."
        )

        endpoint = self._get_endpoint()
        model = self._get_model()

        response = httpx.post(
            f"{endpoint}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        raw = data.get("response", "")

        return ComposeResult(
            yaml=self._extract_yaml(raw),
            metadata=self._extract_metadata(raw),
            provider_used="ollama",
            raw_response=raw,
            retries=1,
        )

    def estimate_cost(self, input_chars: int) -> str:
        return "免费（本地推理）"

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
