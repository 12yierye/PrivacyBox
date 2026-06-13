from __future__ import annotations

from typing import Optional

from jinja2 import Template

from privacybox.utils.types import TemplateDef


def render_template(
    tpl: TemplateDef,
    params: dict[str, str],
) -> str:
    """Render a template with the given parameters using Jinja2."""
    env_vars = {}
    for k, v in params.items():
        if isinstance(v, str):
            env_vars[k] = v
        else:
            env_vars[k] = str(v)

    jinja_tpl = Template(tpl.compose_template)
    rendered = jinja_tpl.render(**env_vars)

    from privacybox.config.loader import get_data_dir
    data_dir = get_data_dir()

    name = params.get("name", tpl.name)
    rendered = rendered.replace("./data/", str(data_dir / ""))
    rendered = rendered.replace("${name}", name)

    return rendered


def validate_yaml(yaml_str: str) -> tuple[bool, str]:
    """Validate that a string is valid docker-compose YAML."""
    import yaml as yaml_lib
    try:
        data = yaml_lib.safe_load(yaml_str)
        if not data or "services" not in data:
            return False, "缺少 'services' 字段"
        for svc_name, svc_config in data["services"].items():
            if not isinstance(svc_config, dict):
                return False, f"服务 '{svc_name}' 配置格式错误"
            image = svc_config.get("image", "")
            if not image:
                return False, f"服务 '{svc_name}' 缺少 image"
            if svc_config.get("privileged", False):
                return False, f"服务 '{svc_name}' 使用了 privileged 模式（禁止）"
            volumes = svc_config.get("volumes", [])
            for v in volumes:
                if isinstance(v, str) and "/var/run/docker.sock" in v:
                    return False, f"服务 '{svc_name}' 挂载了 docker.sock（禁止）"
        return True, ""
    except yaml_lib.YAMLError as e:
        return False, f"YAML 语法错误: {e}"
