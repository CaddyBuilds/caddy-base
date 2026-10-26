"""Decides whether the caddy-base image must be rebuilt.

Run from the caddy-base repo root by ``build-base-image.yml``::

    python -m check_caddy_status.check_base_image --dockerfile Dockerfile [--dry-run]

The image is rebuilt when it is missing from GHCR or lacks a platform, or when the Alpine
tag the Dockerfile pins was republished after our last build. Always printed, so the
build job can use them: ``BASE_TAG`` (``3.23``, for the ``alpine3.23`` alias) and
``PLATFORMS``; the decision goes to ``NEEDS_BUILD``, ``BUILD_REASON`` and ``BUILD_DETAILS``.
"""

import argparse
import os
import sys

from .docker_hub import check_docker_hub_tag, get_docker_hub_pushed, get_platforms_from_tag_data
from .dockerfile import DockerfileError, parse_stages
from .ghcr import check_ghcr_tag, get_ghcr_created
from .http_client import TagCheckResult
from .image_ref import parse_image_ref
from .logger import log, set_action_output
from .platforms import OFFICIAL_PLATFORMS


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check whether the caddy-base image needs a rebuild")
    parser.add_argument("--dockerfile", default="Dockerfile", help="The base image's Dockerfile")
    parser.add_argument("--image", default=os.environ.get("GITHUB_REPOSITORY", "").lower(), help="GHCR image name (owner/name)")
    parser.add_argument("--tag", default="latest", help="Tag to compare (default: latest)")
    parser.add_argument("--dry-run", action="store_true", help="Print outputs instead of writing GITHUB_OUTPUT")
    args = parser.parse_args(argv)

    if not args.image:
        log.error("Configuration error: set --image or GITHUB_REPOSITORY.")
        return 1
    try:
        base = parse_image_ref(parse_stages(args.dockerfile)[0].image)
    except (DockerfileError, ValueError) as e:
        log.error(f"Configuration error: {e}")
        return 1
    if not base.is_docker_hub:
        log.error(f"Configuration error: the base image must come from Docker Hub, got {base}")
        return 1

    platforms = set(OFFICIAL_PLATFORMS)
    log.info(f"Base image: {base}")
    log.info(f"Our image: ghcr.io/{args.image}:{args.tag}")
    log.info(f"Platforms: {', '.join(OFFICIAL_PLATFORMS)}")
    set_action_output("BASE_TAG", base.tag, args.dry_run)
    set_action_output("PLATFORMS", ",".join(OFFICIAL_PLATFORMS), args.dry_run)

    try:
        reason, details = decide(base, args.image, args.tag, platforms)
    except CheckError as e:
        log.error(str(e))
        log.set_summary("Build Decision", f"Error: {e}")
        log.print_summary()
        return 1

    needs_build = reason != "none"
    log.set_summary("Build Decision", f"{'Yes' if needs_build else 'No'} (reason: {reason})")
    set_action_output("NEEDS_BUILD", "true" if needs_build else "false", args.dry_run)
    set_action_output("BUILD_REASON", reason, args.dry_run)
    set_action_output("BUILD_DETAILS", details, args.dry_run)
    log.print_summary()
    return 0


class CheckError(Exception):
    pass


def decide(base, image, tag, platforms):
    """Returns ``(reason, details)``; reason is ``none`` when no rebuild is needed.

    Raises CheckError when the upstream tag cannot provide every platform or a registry
    cannot be read: a silent "no" would hide a broken pipeline.
    """
    log.info(f"\nStep 1: Checking '{base}' on Docker Hub...")
    result, data = check_docker_hub_tag(base.repository, base.tag)
    if result != TagCheckResult.FOUND:
        raise CheckError(f"{base} not found on Docker Hub" if result == TagCheckResult.NOT_FOUND else f"Docker Hub check failed: {data}")
    missing = platforms - get_platforms_from_tag_data(data, platforms)
    if missing:
        raise CheckError(f"{base} lacks platforms we ship: {', '.join(sorted(missing))}")
    log.info("  Upstream has every platform we ship.")
    log.set_summary("Upstream", "Ready (all platforms)")

    log.info(f"\nStep 2: Checking 'ghcr.io/{image}:{tag}'...")
    result, found = check_ghcr_tag(image, tag, platforms)
    if result == TagCheckResult.ERROR:
        raise CheckError(f"GHCR check failed: {found}")
    if result == TagCheckResult.NOT_FOUND:
        log.info("  Not published yet.")
        log.set_summary("Our Image", "Not found")
        return "new_image", f"ghcr.io/{image}:{tag} not published yet"
    missing = platforms - found
    if missing:
        log.info(f"  Missing platforms: {missing}")
        log.set_summary("Our Image", f"Missing: {missing}")
        return "incomplete_image", f"missing {', '.join(sorted(missing))}"
    log.info("  Complete.")
    log.set_summary("Our Image", "Complete")

    log.info(f"\nStep 3: Comparing '{base}' push time with our build time...")
    upstream = get_docker_hub_pushed(base.repository, base.tag, platforms)
    ours = get_ghcr_created(image, tag)
    if upstream is None or ours is None:
        raise CheckError(f"Could not compare build times (upstream: {upstream}, ours: {ours})")
    log.info(f"  upstream pushed {upstream.isoformat()}, ours built {ours.isoformat()}")
    if upstream > ours:
        log.set_summary("Base Image", f"Republished {upstream:%Y-%m-%d}")
        return "base_image_update", f"{base} republished {upstream:%Y-%m-%d}"
    log.set_summary("Base Image", "Up to date")
    return "none", ""


if __name__ == "__main__":
    sys.exit(main())
