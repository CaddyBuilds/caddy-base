import unittest
from datetime import datetime, timezone
from unittest import mock

from check_caddy_status import base_image
from check_caddy_status.base_image import check_base_image_updates

PLATFORMS = {"linux/amd64", "linux/arm64"}
OLD = datetime(2026, 10, 20, tzinfo=timezone.utc)
NEW = datetime(2026, 10, 25, tzinfo=timezone.utc)
NEWER = datetime(2026, 10, 26, tzinfo=timezone.utc)


def _patch(hub, ghcr):
    """hub/ghcr map ``repository:tag`` to a time (or None)."""
    return mock.patch.multiple(
        base_image,
        GHCR_IMAGE="o/caddy-x",
        CUSTOM_IMAGE="",
        get_docker_hub_pushed=mock.Mock(side_effect=lambda repo, tag, platforms: hub.get(f"{repo}:{tag}")),
        get_ghcr_created=mock.Mock(side_effect=lambda repo, tag: ghcr.get(f"{repo}:{tag}")),
    )


class CheckBaseImageUpdatesTest(unittest.TestCase):
    VARIANTS = [
        ("2.11.7", "caddy:2.11.7"),
        ("2.11.7-alpine", "caddy:2.11.7-alpine"),
        ("2.11.7-slim", "ghcr.io/caddybuilds/caddy-base:latest"),
    ]

    def test_up_to_date(self):
        hub = {"library/caddy:2.11.7": OLD, "library/caddy:2.11.7-alpine": OLD}
        ghcr = {"o/caddy-x:2.11.7": NEW, "o/caddy-x:2.11.7-alpine": NEW, "o/caddy-x:2.11.7-slim": NEW, "caddybuilds/caddy-base:latest": OLD}
        with _patch(hub, ghcr):
            self.assertEqual(check_base_image_updates(self.VARIANTS, PLATFORMS), [])

    def test_slim_base_on_ghcr_republished(self):
        hub = {"library/caddy:2.11.7": OLD, "library/caddy:2.11.7-alpine": OLD}
        ghcr = {"o/caddy-x:2.11.7": NEW, "o/caddy-x:2.11.7-alpine": NEW, "o/caddy-x:2.11.7-slim": NEW, "caddybuilds/caddy-base:latest": NEWER}
        with _patch(hub, ghcr):
            self.assertEqual(check_base_image_updates(self.VARIANTS, PLATFORMS), ["ghcr.io/caddybuilds/caddy-base:latest republished 2026-10-26"])

    def test_official_image_republished_only_affects_default(self):
        hub = {"library/caddy:2.11.7": NEWER, "library/caddy:2.11.7-alpine": NEWER}
        ghcr = {"o/caddy-x:2.11.7": NEW, "o/caddy-x:2.11.7-alpine": NEW, "o/caddy-x:2.11.7-slim": NEW, "caddybuilds/caddy-base:latest": OLD}
        with _patch(hub, ghcr):
            self.assertEqual(
                check_base_image_updates(self.VARIANTS, PLATFORMS),
                ["caddy:2.11.7 republished 2026-10-26", "caddy:2.11.7-alpine republished 2026-10-26"],
            )

    def test_unknown_times_are_skipped(self):
        with _patch({}, {}):
            self.assertEqual(check_base_image_updates(self.VARIANTS, PLATFORMS), [])

    def test_docker_hub_fallback_for_our_build_time(self):
        hub = {"library/caddy:2.11.7": NEWER, "me/caddy-x:2.11.7": NEW}
        with _patch(hub, {}), mock.patch.object(base_image, "CUSTOM_IMAGE", "me/caddy-x"):
            self.assertEqual(check_base_image_updates([("2.11.7", "caddy:2.11.7")], PLATFORMS), ["caddy:2.11.7 republished 2026-10-26"])

    def test_unsupported_registry_and_bad_ref(self):
        with _patch({}, {"o/caddy-x:2.11.7-slim": NEW}):
            self.assertEqual(check_base_image_updates([("2.11.7-slim", "quay.io/x/y:1"), ("2.11.7", "bad@sha256:0")], PLATFORMS), [])


if __name__ == "__main__":
    unittest.main()
