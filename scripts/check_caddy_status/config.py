"""Environment-derived settings shared by every image repo.

Repo-specific values (title, modules, variants, platforms) come from the image config file
and the Dockerfile, loaded at runtime — see ``image_config`` and ``dockerfile``.
"""

import os

# GitHub
GITHUB_REPO = "caddyserver/caddy"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Derive image names from GITHUB_REPOSITORY (e.g. "CaddyBuilds/caddy-cloudflare")
# This makes the script work for any fork without configuration.
_github_repository = os.environ.get("GITHUB_REPOSITORY", "").lower()

# Docker Hub — override with DOCKERHUB_REPOSITORY_NAME if set, else fall back to repo
OFFICIAL_CADDY_IMAGE = "library/caddy"
CUSTOM_IMAGE = os.environ.get("DOCKERHUB_REPOSITORY_NAME", "") or _github_repository

# GHCR — always matches the GitHub repo
GHCR_IMAGE = os.environ.get("GHCR_IMAGE", "") or _github_repository

# HTTP retry settings
MAX_RETRIES = 3
BACKOFF_BASE = 2
