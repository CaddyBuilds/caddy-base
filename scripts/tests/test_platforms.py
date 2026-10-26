import unittest

from check_caddy_status.docker_hub import get_platforms_from_tag_data
from check_caddy_status.platforms import DEFAULT_PLATFORMS, OFFICIAL_PLATFORMS, platform_string


class PlatformStringTest(unittest.TestCase):
    def test_canonical_forms(self):
        self.assertEqual(platform_string("linux", "amd64"), "linux/amd64")
        self.assertEqual(platform_string("linux", "arm64", "v8"), "linux/arm64")
        self.assertEqual(platform_string("linux", "arm", "v7"), "linux/arm/v7")
        self.assertEqual(platform_string("linux", "arm", "v6"), "linux/arm/v6")
        self.assertEqual(platform_string("linux", "riscv64", None), "linux/riscv64")

    def test_non_linux_is_ignored(self):
        self.assertIsNone(platform_string("windows", "amd64"))
        self.assertIsNone(platform_string("unknown", "unknown"))
        self.assertIsNone(platform_string("linux", None))

    def test_defaults_are_official(self):
        self.assertTrue(set(DEFAULT_PLATFORMS) <= set(OFFICIAL_PLATFORMS))
        self.assertEqual(len(set(OFFICIAL_PLATFORMS)), len(OFFICIAL_PLATFORMS))


class DockerHubPlatformsTest(unittest.TestCase):
    TAG_DATA = {
        "images": [
            {"os": "linux", "architecture": "amd64", "variant": None},
            {"os": "linux", "architecture": "arm64", "variant": "v8"},
            {"os": "linux", "architecture": "arm", "variant": "v7"},
            {"os": "linux", "architecture": "arm", "variant": "v6"},
            {"os": "linux", "architecture": "riscv64", "variant": None},
            {"os": "unknown", "architecture": "unknown", "variant": None},
            "garbage",
        ]
    }

    def test_only_wanted_platforms_are_reported(self):
        wanted = {"linux/amd64", "linux/arm64", "linux/arm/v7", "linux/s390x"}
        self.assertEqual(get_platforms_from_tag_data(self.TAG_DATA, wanted), {"linux/amd64", "linux/arm64", "linux/arm/v7"})

    def test_arm_v6_and_riscv64(self):
        wanted = {"linux/arm/v6", "linux/riscv64"}
        self.assertEqual(get_platforms_from_tag_data(self.TAG_DATA, wanted), wanted)

    def test_bad_data(self):
        self.assertEqual(get_platforms_from_tag_data(None, {"linux/amd64"}), set())
        self.assertEqual(get_platforms_from_tag_data({"images": "x"}, {"linux/amd64"}), set())


if __name__ == "__main__":
    unittest.main()
