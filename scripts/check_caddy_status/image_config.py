"""Loads the per-repo image config (``caddy-image.json``).

The file holds what differs between image repos and is read by both the check script
and the build workflow, so there is one place to change it.
"""

import json
from dataclasses import dataclass

REQUIRED_KEYS = ("title", "description", "verify_module")
DEFAULTS = {"alpine_alias": True, "slim": False, "create_release": True}


class ImageConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ImageConfig:
    title: str
    description: str
    verify_module: str
    alpine_alias: bool = True
    slim: bool = False
    create_release: bool = True

    @property
    def official_variant_suffixes(self):
        """Tag suffixes of ours that are built FROM the official image (base-image check).

        The -alpine tags are aliases of the default image, so they share its base. A -slim
        variant is built from a different base and is tracked separately.
        """
        return [""] + (["-alpine"] if self.alpine_alias else [])


def load_image_config(path):
    """Reads and validates the config file. Raises ImageConfigError on problems."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise ImageConfigError(f"Cannot read image config '{path}': {e}") from e
    except json.JSONDecodeError as e:
        raise ImageConfigError(f"Image config '{path}' is not valid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ImageConfigError(f"Image config '{path}' must be a JSON object")

    missing = [k for k in REQUIRED_KEYS if not str(data.get(k, "")).strip()]
    if missing:
        raise ImageConfigError(f"Image config '{path}' is missing required keys: {', '.join(missing)}")

    unknown = set(data) - set(REQUIRED_KEYS) - set(DEFAULTS)
    if unknown:
        raise ImageConfigError(f"Image config '{path}' has unknown keys: {', '.join(sorted(unknown))}")

    values = {**DEFAULTS, **data}
    for key in DEFAULTS:
        if not isinstance(values[key], bool):
            raise ImageConfigError(f"Image config '{path}': '{key}' must be true or false")

    return ImageConfig(**{k: values[k] for k in REQUIRED_KEYS + tuple(DEFAULTS)})
