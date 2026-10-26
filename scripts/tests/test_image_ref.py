import unittest

from check_caddy_status.image_ref import ImageRef, parse_image_ref


class ParseImageRefTest(unittest.TestCase):
    def test_docker_hub_forms(self):
        self.assertEqual(parse_image_ref("alpine:3.23"), ImageRef("docker.io", "library/alpine", "3.23"))
        self.assertEqual(parse_image_ref("alpine"), ImageRef("docker.io", "library/alpine", "latest"))
        self.assertEqual(parse_image_ref("caddy:2.11.7-alpine"), ImageRef("docker.io", "library/caddy", "2.11.7-alpine"))
        self.assertEqual(parse_image_ref("library/caddy:2"), ImageRef("docker.io", "library/caddy", "2"))
        self.assertEqual(parse_image_ref("docker.io/library/caddy:2"), ImageRef("docker.io", "library/caddy", "2"))
        self.assertEqual(parse_image_ref("index.docker.io/caddybuilds/caddy-bunny"), ImageRef("docker.io", "caddybuilds/caddy-bunny", "latest"))
        self.assertEqual(parse_image_ref("caddybuilds/caddy-bunny:slim"), ImageRef("docker.io", "caddybuilds/caddy-bunny", "slim"))

    def test_other_registries(self):
        self.assertEqual(parse_image_ref("ghcr.io/caddybuilds/caddy-base:latest"), ImageRef("ghcr.io", "caddybuilds/caddy-base", "latest"))
        self.assertEqual(parse_image_ref("ghcr.io/caddybuilds/caddy-base"), ImageRef("ghcr.io", "caddybuilds/caddy-base", "latest"))
        self.assertEqual(parse_image_ref("localhost:5000/base:1"), ImageRef("localhost:5000", "base", "1"))

    def test_str(self):
        self.assertEqual(str(parse_image_ref("alpine:3.23")), "alpine:3.23")
        self.assertEqual(str(parse_image_ref("ghcr.io/caddybuilds/caddy-base")), "ghcr.io/caddybuilds/caddy-base:latest")
        self.assertTrue(parse_image_ref("alpine").is_docker_hub)
        self.assertFalse(parse_image_ref("ghcr.io/a/b").is_docker_hub)

    def test_invalid(self):
        for bad in ("", "alpine@sha256:abc", "ghcr.io/a/:tag"):
            with self.assertRaises(ValueError, msg=bad):
                parse_image_ref(bad)


if __name__ == "__main__":
    unittest.main()
