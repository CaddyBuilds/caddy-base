import json
import os

import requests

from .http_client import TagCheckResult, request_with_retry
from .logger import log
from .platforms import platform_string
from .timeutil import parse_timestamp

INDEX_ACCEPT = (
    "application/vnd.oci.image.index.v1+json, "
    "application/vnd.docker.distribution.manifest.list.v2+json"
)
MANIFEST_ACCEPT = (
    "application/vnd.oci.image.manifest.v1+json, "
    "application/vnd.docker.distribution.manifest.v2+json"
)


_tokens = {}


def _get_pull_token(image_name):
    """Gets a GHCR pull token, cached per image for the run.

    Anonymous by default, which covers public packages. ``GHCR_TOKEN`` (a GitHub token with
    read access to the package, e.g. the workflow's ``GITHUB_TOKEN``) lets a repo check
    its own package while it is still private; ``GHCR_USER`` is the matching login.

    Returns:
        tuple: (token, error). (None, None) means the package is not visible to us.
    """
    if image_name in _tokens:
        return _tokens[image_name], None

    token_url = f"https://ghcr.io/token?scope=repository:{image_name}:pull"
    github_token = os.environ.get("GHCR_TOKEN", "")
    auth = (os.environ.get("GHCR_USER") or "token", github_token) if github_token else None
    try:
        token_resp = request_with_retry(token_url, timeout=30, auth=auth)
        if token_resp.status_code in (403, 404):
            return None, None
        if token_resp.status_code != 200:
            return None, f"GHCR token request failed: {token_resp.status_code}"
        token = token_resp.json().get("token")
        if not token:
            return None, "Empty token from GHCR"
        _tokens[image_name] = token
        return token, None
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        return None, f"GHCR token request failed: {e}"


def check_ghcr_tag(image_name, tag, platforms):
    """Checks if a tag exists on GHCR and returns which of the wanted platforms it has.

    Returns:
        tuple: (TagCheckResult, platforms_set_or_error_msg)
    """
    token, error = _get_pull_token(image_name)
    if not token:
        return (TagCheckResult.ERROR, error) if error else (TagCheckResult.NOT_FOUND, None)

    # Fetch manifest list
    manifest_url = f"https://ghcr.io/v2/{image_name}/manifests/{tag}"
    headers = {"Authorization": f"Bearer {token}", "Accept": INDEX_ACCEPT}
    try:
        resp = request_with_retry(manifest_url, headers=headers, timeout=30)
        if resp.status_code == 404:
            return TagCheckResult.NOT_FOUND, None
        if resp.status_code != 200:
            return TagCheckResult.ERROR, f"GHCR manifest status {resp.status_code}"

        found = set()
        for m in resp.json().get("manifests", []):
            p = m.get("platform", {})
            platform = platform_string(p.get("os"), p.get("architecture"), p.get("variant"))
            if platform in platforms:
                found.add(platform)

        return TagCheckResult.FOUND, found
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        return TagCheckResult.ERROR, f"GHCR manifest request failed: {e}"


def get_ghcr_created(image_name, tag):
    """Returns when a GHCR tag was built, from its image config, or None.

    Reads the first linux platform's config — all platforms are built in one run.
    Attestation manifests (platform "unknown") are skipped.
    """
    token, error = _get_pull_token(image_name)
    if not token:
        if error:
            log.warn(f"  GHCR build time lookup failed for '{image_name}:{tag}': {error}")
        return None

    base_url = f"https://ghcr.io/v2/{image_name}"
    auth = {"Authorization": f"Bearer {token}"}
    try:
        index_resp = request_with_retry(f"{base_url}/manifests/{tag}", headers={**auth, "Accept": INDEX_ACCEPT}, timeout=30)
        if index_resp.status_code != 200:
            return None
        digest = next(
            (m["digest"] for m in index_resp.json().get("manifests", []) if m.get("platform", {}).get("os") == "linux"),
            None,
        )
        if not digest:
            return None

        manifest_resp = request_with_retry(f"{base_url}/manifests/{digest}", headers={**auth, "Accept": MANIFEST_ACCEPT}, timeout=30)
        if manifest_resp.status_code != 200:
            return None
        config_digest = manifest_resp.json()["config"]["digest"]

        config_resp = request_with_retry(f"{base_url}/blobs/{config_digest}", headers=auth, timeout=30)
        if config_resp.status_code != 200:
            return None
        return parse_timestamp(config_resp.json().get("created"))
    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError) as e:
        log.warn(f"  GHCR build time lookup failed for '{image_name}:{tag}': {e}")
        return None
