"""Platform lists shared by the checker, the build workflow and the caddy-base image.

Platform strings use Docker's canonical form: ``linux/arm/v7`` keeps its variant,
``linux/arm64`` drops the implied ``v8``.
"""

# Every linux platform the official caddy image publishes. An image repo may ship any
# non-empty subset; the caddy-base image ships all of them so a slim stage has a base
# on every platform a fork can pick.
OFFICIAL_PLATFORMS = (
    "linux/amd64",
    "linux/arm64",
    "linux/arm/v6",
    "linux/arm/v7",
    "linux/ppc64le",
    "linux/riscv64",
    "linux/s390x",
)

# What an image repo ships unless its config lists ``platforms``.
DEFAULT_PLATFORMS = (
    "linux/amd64",
    "linux/arm64",
    "linux/arm/v7",
    "linux/ppc64le",
    "linux/s390x",
)


def platform_string(os_name, arch, variant=None):
    """Canonical ``os/arch[/variant]`` for a registry platform descriptor, or None when not linux."""
    if os_name != "linux" or not arch:
        return None
    if arch == "arm" and variant:
        return f"{os_name}/{arch}/{variant}"
    return f"{os_name}/{arch}"
