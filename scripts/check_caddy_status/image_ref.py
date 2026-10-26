"""Splits an image reference such as ``alpine:3.23`` or ``ghcr.io/caddybuilds/caddy-base:latest``."""

from typing import NamedTuple

DOCKER_HUB = "docker.io"


class ImageRef(NamedTuple):
    registry: str  # ``docker.io`` for Docker Hub
    repository: str  # ``library/alpine``, ``caddybuilds/caddy-base``
    tag: str

    @property
    def is_docker_hub(self):
        return self.registry == DOCKER_HUB

    def __str__(self):
        name = self.repository.removeprefix("library/") if self.is_docker_hub else f"{self.registry}/{self.repository}"
        return f"{name}:{self.tag}"


def parse_image_ref(ref):
    """Normalises a reference the way Docker does: Docker Hub and ``library/`` are implied, ``latest`` is the default tag."""
    ref = ref.strip()
    if not ref:
        raise ValueError("Empty image reference")
    if "@" in ref:
        raise ValueError(f"Digest references are not supported, use a tag: {ref}")

    first, slash, rest = ref.partition("/")
    if slash and ("." in first or ":" in first or first == "localhost"):
        registry, path = first, rest
    else:
        registry, path = DOCKER_HUB, ref
    if registry == "index.docker.io":
        registry = DOCKER_HUB

    head, _, last = path.rpartition("/")
    name, colon, tag = last.partition(":")
    repository = f"{head}/{name}" if head else name
    if registry == DOCKER_HUB and "/" not in repository:
        repository = f"library/{repository}"
    if not name:
        raise ValueError(f"Malformed image reference: {ref}")
    return ImageRef(registry, repository, tag if colon else "latest")
