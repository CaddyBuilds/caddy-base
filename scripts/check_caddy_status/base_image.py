"""Detects when the official Caddy image was republished after our last build.

Docker Official Images are rebuilt for base OS and Go toolchain fixes without a new
Caddy release. Rebuilding on top of them picks those fixes up.
"""

from .config import CUSTOM_IMAGE, GHCR_IMAGE, OFFICIAL_CADDY_IMAGE
from .docker_hub import get_docker_hub_pushed
from .ghcr import get_ghcr_created
from .logger import log


def check_base_image_updates(docker_tag, variant_suffixes, platforms):
    """Returns descriptions of variants whose official image is newer than our build (empty if none).

    Args:
        docker_tag: Caddy version without the ``v`` prefix.
        variant_suffixes: our tag suffixes that are built FROM ``library/caddy`` (e.g. ``["", "-alpine"]``).
        platforms: the platforms we ship; pushes of other platforms are ignored.
    """
    stale = []
    unknown = []

    for suffix in variant_suffixes:
        tag = f"{docker_tag}{suffix}"
        official = get_docker_hub_pushed(OFFICIAL_CADDY_IMAGE, tag, platforms)
        ours = _custom_build_time(tag, platforms)

        if official is None or ours is None:
            log.warn(f"  Could not compare '{tag}' (official: {official}, ours: {ours}), skipping.")
            unknown.append(tag)
            continue

        log.info(f"  {tag}: official pushed {official.isoformat()}, ours built {ours.isoformat()}")
        if official > ours:
            stale.append(f"{OFFICIAL_CADDY_IMAGE.removeprefix('library/')}:{tag} republished {official:%Y-%m-%d}")

    if stale:
        log.set_summary("Base Image", f"Updated upstream: {', '.join(stale)}")
    elif unknown:
        log.set_summary("Base Image", f"Unknown: {', '.join(unknown)}")
    else:
        log.set_summary("Base Image", "Up to date")

    return stale


def _custom_build_time(tag, platforms):
    """Returns when our image was built.

    GHCR is preferred because the image config's ``created`` is the build time. Docker Hub
    only knows the push time, which can postdate an upstream re-push that happened while
    our (long, emulated) build was still running.
    """
    if GHCR_IMAGE:
        created = get_ghcr_created(GHCR_IMAGE, tag)
        if created:
            return created
    if CUSTOM_IMAGE:
        return get_docker_hub_pushed(CUSTOM_IMAGE, tag, platforms)
    return None
