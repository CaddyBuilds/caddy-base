"""Loads the per-repo image config (``caddy-image.json``).

The file holds what differs between image repos and is read by both the check script
and the build workflow, so there is one place to change it. The build workflow runs this
module as a script to turn the file into ``key=value`` lines for ``$GITHUB_OUTPUT``::

    python3 -m check_caddy_status.image_config caddy-image.json
"""

import argparse
import json
import sys
from dataclasses import dataclass

from .platforms import DEFAULT_PLATFORMS, OFFICIAL_PLATFORMS

REQUIRED_KEYS = ("title", "description", "verify_module")
FLAG_DEFAULTS = {"alpine_alias": True, "slim": False, "create_release": True}
OPTIONAL_KEYS = tuple(FLAG_DEFAULTS) + ("platforms",)


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
    platforms: tuple = DEFAULT_PLATFORMS

    @property
    def official_variant_suffixes(self):
        """Tag suffixes of ours that are built FROM the official image (base-image check).

        The -alpine tags are aliases of the default image, so they share its base. A -slim
        variant is built from a different base and is tracked separately.
        """
        return [""] + (["-alpine"] if self.alpine_alias else [])

    def as_outputs(self):
        """The config as ``key=value`` lines in the shape ``$GITHUB_OUTPUT`` expects."""
        lines = []
        for key in REQUIRED_KEYS:
            lines.append(f"{key}={' '.join(getattr(self, key).split())}")
        for key in FLAG_DEFAULTS:
            lines.append(f"{key}={'true' if getattr(self, key) else 'false'}")
        lines.append(f"platforms={','.join(self.platforms)}")
        return lines


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

    unknown = set(data) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS)
    if unknown:
        raise ImageConfigError(f"Image config '{path}' has unknown keys: {', '.join(sorted(unknown))}")

    values = {**FLAG_DEFAULTS, **data}
    for key in FLAG_DEFAULTS:
        if not isinstance(values[key], bool):
            raise ImageConfigError(f"Image config '{path}': '{key}' must be true or false")

    platforms = _validate_platforms(data.get("platforms", list(DEFAULT_PLATFORMS)), path)

    return ImageConfig(**{k: values[k] for k in REQUIRED_KEYS + tuple(FLAG_DEFAULTS)}, platforms=platforms)


def _validate_platforms(value, path):
    """Returns the platforms as a tuple in config order; they must be a non-empty subset of the official set."""
    if not isinstance(value, list) or not value or not all(isinstance(p, str) for p in value):
        raise ImageConfigError(f"Image config '{path}': 'platforms' must be a non-empty list of strings")
    unknown = [p for p in value if p not in OFFICIAL_PLATFORMS]
    if unknown:
        raise ImageConfigError(
            f"Image config '{path}': the official caddy image does not publish {', '.join(unknown)}. "
            f"Allowed: {', '.join(OFFICIAL_PLATFORMS)}"
        )
    if len(set(value)) != len(value):
        raise ImageConfigError(f"Image config '{path}': 'platforms' has duplicates")
    return tuple(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate an image config and print it as key=value lines")
    parser.add_argument("config", help="Path of caddy-image.json")
    args = parser.parse_args(argv)
    try:
        config = load_image_config(args.config)
    except ImageConfigError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    print("\n".join(config.as_outputs()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
