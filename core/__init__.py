import os

import yaml
from dotenv import load_dotenv


def load_config_env(
    env_var_name="CONFIG",
    default_config="config.yaml",
    template_config="config.template.yaml",
    max_depth=3,
):
    load_dotenv()
    config_path = os.environ.get(env_var_name, default_config)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Missing '{config_path}' and template '{template_config}'."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    extra_config = {}

    def recurse(prefix, obj, depth):
        if depth == 0 or not isinstance(obj, dict):
            value = str(obj)
            # if environ has the key, skip
            if prefix in os.environ:
                value = os.environ[prefix]
            else:
                os.environ[prefix] = value
            extra_config[prefix] = value
            return
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            recurse(key, v, depth - 1)

    recurse("", data, max_depth)
    return extra_config


extra_config = load_config_env()
