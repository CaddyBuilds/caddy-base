import json

import requests

from .http_client import TagCheckResult, request_with_retry
from .logger import log
from .platforms import platform_string
from .timeutil import parse_timestamp


def check_docker_hub_tag(image_name, tag):
    """Checks if a tag exists for a Docker Hub image.

    Returns:
        tuple: (TagCheckResult, data_or_error_msg)
    """
    url = f"https://hub.docker.com/v2/repositories/{image_name}/tags/{tag}"
    try:
        response = request_with_retry(url, timeout=45)
        if response.status_code == 200:
            return TagCheckResult.FOUND, response.json()
        elif response.status_code == 404:
            return TagCheckResult.NOT_FOUND, None
        else:
            msg = f"Unexpected status {response.status_code} for '{image_name}:{tag}'"
            log.error(msg)
            return TagCheckResult.ERROR, msg
    except requests.exceptions.RequestException as e:
        msg = f"Request failed for '{image_name}:{tag}': {e}"
        log.error(msg)
        return TagCheckResult.ERROR, msg
    except json.JSONDecodeError as e:
        msg = f"JSON decode error for '{image_name}:{tag}': {e}"
        log.error(msg)
        return TagCheckResult.ERROR, msg


def get_images_by_platform(tag_data, platforms):
    """Maps each wanted platform to its image entry from Docker Hub tag data."""
    images = {}
    if not tag_data or "images" not in tag_data or not isinstance(tag_data["images"], list):
        log.info("  Could not find valid 'images' list in Docker Hub tag data.")
        return images

    for img in tag_data["images"]:
        if not isinstance(img, dict):
            continue
        platform = platform_string(img.get("os"), img.get("architecture"), img.get("variant"))
        if platform in platforms:
            images[platform] = img

    return images


def get_platforms_from_tag_data(tag_data, platforms):
    """The wanted platforms that a Docker Hub tag API response actually has."""
    return set(get_images_by_platform(tag_data, platforms))


def get_docker_hub_pushed(image_name, tag, platforms):
    """Returns the most recent push among the tag's wanted platforms, or None.

    The tag-level ``last_updated`` also moves when platforms we don't ship (Windows,
    riscv64) are re-pushed, which would trigger needless rebuilds.
    """
    result, data = check_docker_hub_tag(image_name, tag)
    if result != TagCheckResult.FOUND:
        return None
    pushed = [parse_timestamp(img.get("last_pushed")) for img in get_images_by_platform(data, platforms).values()]
    pushed = [p for p in pushed if p]
    return max(pushed) if pushed else None
