from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from privacybox.utils.types import TemplateDef, TemplateParam


class TemplateRegistry:
    """Manages built-in and user-installed templates."""

    def __init__(self):
        self._builtins_dir = Path(__file__).parent / "builtins"
        self._cache: dict[str, TemplateDef] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        if not self._builtins_dir.exists():
            return
        for f in sorted(self._builtins_dir.glob("*.yaml")):
            try:
                t = self._parse_template(f)
                if t:
                    self._cache[t.name] = t
            except Exception:
                pass

    def _parse_template(self, path: Path) -> Optional[TemplateDef]:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if not data or "name" not in data:
            return None

        params = []
        for p in data.get("params", []):
            params.append(TemplateParam(
                name=p.get("name", ""),
                type=p.get("type", "string"),
                label=p.get("label", p.get("name", "")),
                hint=p.get("hint", ""),
                default=p.get("default"),
                required=p.get("required", False),
                advanced=p.get("advanced", False),
                auto_generate=p.get("auto_generate", False),
                min_value=p.get("min"),
                max_value=p.get("max"),
            ))

        import yaml as yaml_lib
        compose_str = yaml_lib.dump(data.get("compose", {}), default_flow_style=False, allow_unicode=True)

        return TemplateDef(
            name=data["name"],
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            categories=data.get("categories", []),
            author=data.get("author", "PrivacyBox Team"),
            params=params,
            compose_template=compose_str,
        )

    def list_all(self) -> list[TemplateDef]:
        return list(self._cache.values())

    def get(self, name: str) -> Optional[TemplateDef]:
        return self._cache.get(name)

    def match(self, query: str) -> Optional[TemplateDef]:
        """Find best matching template by name/description keywords."""
        query_lower = query.lower()
        best = None
        best_score = 0

        for t in self._cache.values():
            score = 0
            if t.name.lower() in query_lower:
                score += 10
            for kw in t.name.lower().split():
                if kw in query_lower:
                    score += 5
            for cat in t.categories:
                if cat.lower() in query_lower:
                    score += 3
            desc_words = t.description.lower().split()
            for w in desc_words:
                if len(w) > 3 and w in query_lower:
                    score += 1

            if score > best_score:
                best_score = score
                best = t

        if best_score >= 5:
            return best
        return None
