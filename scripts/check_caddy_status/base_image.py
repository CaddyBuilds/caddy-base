"""Detects when the base image of one of our variants was republished after our last build.

Docker Official Images are rebuilt for base OS and Go toolchain fixes without a new
Caddy release, and the caddy-base image is rebuilt when its Alpine tag is. Rebuilding
on top of them picks those fixes up.
"""

from .config import CUSTOM_IMAGE, GHCR_IMAGE
from .docker_hub import get_docker_hub_pushed
from .ghcr import get_ghcr_created
from .image_ref import parse_image_ref
from .logger import log


def check_base_image_updates(variants, platforms):
    """Returns descriptions of variants whose base image is newer than our build (empty if none).

    Args:
        variants: ``[(our_tag, base_image_ref)]``, e.g. ``("2.11.7", "caddy:2.11.7")`` for the
            default image and ``("2.11.7-slim", "ghcr.io/caddybuilds/caddy-base:latest")`` for slim.
        platforms: the platforms we ship; pushes of other platforms are ignored.
    """
    stale = []
    unknown = []

    for our_tag, base_ref in variants:
        try:
            base = parse_image_ref(base_ref)
        except ValueError as e:
            log.warn(f"  Cannot check the base of '{our_tag}': {e}")
            unknown.append(our_tag)
            continue
        upstream = base_image_time(base, platforms)
        ours = _custom_build_time(our_tag, platforms)

        if upstream is None or ours is None:
            log.warn(f"  Could not compare '{our_tag}' with {base} (base: {upstream}, ours: {ours}), skipping.")
            unknown.append(our_tag)
            continue

        log.info(f"  {our_tag}: {base} pushed {upstream.isoformat()}, ours built {ours.isoformat()}")
        if upstream > ours:
            stale.append(f"{base} republished {upstream:%Y-%m-%d}")

    if stale:
        log.set_summary("Base Image", f"Updated upstream: {', '.join(stale)}")
    elif unknown:
        log.set_summary("Base Image", f"Unknown: {', '.join(unknown)}")
    else:
        log.set_summary("Base Image", "Up to date")

    return stale


def base_image_time(ref, platforms):
    """When a base image was last pushed (Docker Hub) or built (GHCR), or None.

    GHCR has no push time; the image config's ``created`` is the build time, and the
    caddy-base image is pushed by the run that builds it.
    """
    if ref.is_docker_hub:
        return get_docker_hub_pushed(ref.repository, ref.tag, platforms)
    if ref.registry == "ghcr.io":
        return get_ghcr_created(ref.repository, ref.tag)
    log.warn(f"  Cannot read push times from {ref.registry}, skipping {ref}")
    return None


def _custom_build_time(tag, platforms):
    """Returns when our image was built.

    GHCR is preferred because the image config's ``created`` is the build time. Docker Hub
    only knows the push time, which can postdate an upstream re-push that happened while
    our build was still running.
    """
    if GHCR_IMAGE:
        created = get_ghcr_created(GHCR_IMAGE, tag)
        if created:
            return created
    if CUSTOM_IMAGE:
        return get_docker_hub_pushed(CUSTOM_IMAGE, tag, platforms)
    return None
