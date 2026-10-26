import unittest
from datetime import datetime, timezone
from unittest import mock

from check_caddy_status import check_base_image
from check_caddy_status.check_base_image import CheckError, decide
from check_caddy_status.http_client import TagCheckResult
from check_caddy_status.image_ref import parse_image_ref

BASE = parse_image_ref("alpine:3.23")
PLATFORMS = {"linux/amd64", "linux/arm64"}
HUB_DATA = {"images": [{"os": "linux", "architecture": "amd64"}, {"os": "linux", "architecture": "arm64", "variant": "v8"}]}
T1 = datetime(2026, 10, 20, tzinfo=timezone.utc)
T2 = datetime(2026, 10, 25, tzinfo=timezone.utc)


def _patch(**overrides):
    defaults = {
        "check_docker_hub_tag": mock.Mock(return_value=(TagCheckResult.FOUND, HUB_DATA)),
        "check_ghcr_tag": mock.Mock(return_value=(TagCheckResult.FOUND, set(PLATFORMS))),
        "get_docker_hub_pushed": mock.Mock(return_value=T1),
        "get_ghcr_created": mock.Mock(return_value=T2),
    }
    defaults.update(overrides)
    return mock.patch.multiple(check_base_image, **defaults)


class DecideTest(unittest.TestCase):
    def test_up_to_date(self):
        with _patch():
            self.assertEqual(decide(BASE, "o/caddy-base", "latest", PLATFORMS), ("none", ""))

    def test_upstream_republished(self):
        with _patch(get_docker_hub_pushed=mock.Mock(return_value=datetime(2026, 10, 26, tzinfo=timezone.utc))):
            reason, details = decide(BASE, "o/caddy-base", "latest", PLATFORMS)
        self.assertEqual(reason, "base_image_update")
        self.assertEqual(details, "alpine:3.23 republished 2026-10-26")

    def test_our_image_missing(self):
        with _patch(check_ghcr_tag=mock.Mock(return_value=(TagCheckResult.NOT_FOUND, None))):
            self.assertEqual(decide(BASE, "o/caddy-base", "latest", PLATFORMS)[0], "new_image")

    def test_our_image_incomplete(self):
        with _patch(check_ghcr_tag=mock.Mock(return_value=(TagCheckResult.FOUND, {"linux/amd64"}))):
            self.assertEqual(decide(BASE, "o/caddy-base", "latest", PLATFORMS), ("incomplete_image", "missing linux/arm64"))

    def test_upstream_lacks_platform(self):
        with _patch(), self.assertRaisesRegex(CheckError, "linux/s390x"):
            decide(BASE, "o/caddy-base", "latest", PLATFORMS | {"linux/s390x"})

    def test_upstream_missing(self):
        with _patch(check_docker_hub_tag=mock.Mock(return_value=(TagCheckResult.NOT_FOUND, None))), self.assertRaises(CheckError):
            decide(BASE, "o/caddy-base", "latest", PLATFORMS)

    def test_ghcr_error(self):
        with _patch(check_ghcr_tag=mock.Mock(return_value=(TagCheckResult.ERROR, "boom"))), self.assertRaisesRegex(CheckError, "boom"):
            decide(BASE, "o/caddy-base", "latest", PLATFORMS)

    def test_unknown_times(self):
        with _patch(get_ghcr_created=mock.Mock(return_value=None)), self.assertRaises(CheckError):
            decide(BASE, "o/caddy-base", "latest", PLATFORMS)


if __name__ == "__main__":
    unittest.main()
