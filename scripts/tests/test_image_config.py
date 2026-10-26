import json
import tempfile
import unittest
from pathlib import Path

from check_caddy_status.image_config import ImageConfigError, load_image_config, main
from check_caddy_status.platforms import DEFAULT_PLATFORMS, OFFICIAL_PLATFORMS


def _write(data):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    tmp.write(data if isinstance(data, str) else json.dumps(data))
    tmp.close()
    return Path(tmp.name)


MINIMAL = {"title": "Caddy Bunny", "description": "Caddy with Bunny DNS module", "verify_module": "dns.providers.bunny"}


class LoadImageConfigTest(unittest.TestCase):
    def test_defaults(self):
        cfg = load_image_config(_write(MINIMAL))
        self.assertEqual(cfg.title, "Caddy Bunny")
        self.assertTrue(cfg.alpine_alias)
        self.assertFalse(cfg.slim)
        self.assertTrue(cfg.create_release)
        self.assertEqual(cfg.official_variant_suffixes, ["", "-alpine"])
        self.assertEqual(cfg.platforms, DEFAULT_PLATFORMS)

    def test_platforms_subset_keeps_config_order(self):
        cfg = load_image_config(_write({**MINIMAL, "platforms": ["linux/arm64", "linux/amd64"]}))
        self.assertEqual(cfg.platforms, ("linux/arm64", "linux/amd64"))

    def test_platforms_may_be_the_whole_official_set(self):
        cfg = load_image_config(_write({**MINIMAL, "platforms": list(OFFICIAL_PLATFORMS)}))
        self.assertEqual(cfg.platforms, OFFICIAL_PLATFORMS)

    def test_platforms_empty(self):
        with self.assertRaisesRegex(ImageConfigError, "non-empty"):
            load_image_config(_write({**MINIMAL, "platforms": []}))

    def test_platforms_not_a_list(self):
        with self.assertRaises(ImageConfigError):
            load_image_config(_write({**MINIMAL, "platforms": "linux/amd64"}))

    def test_platforms_unknown(self):
        with self.assertRaisesRegex(ImageConfigError, "windows/amd64"):
            load_image_config(_write({**MINIMAL, "platforms": ["linux/amd64", "windows/amd64"]}))

    def test_platforms_duplicate(self):
        with self.assertRaisesRegex(ImageConfigError, "duplicates"):
            load_image_config(_write({**MINIMAL, "platforms": ["linux/amd64", "linux/amd64"]}))

    def test_outputs(self):
        cfg = load_image_config(_write({**MINIMAL, "title": "Caddy  Bunny ", "slim": True, "platforms": ["linux/amd64", "linux/arm64"]}))
        self.assertEqual(
            cfg.as_outputs(),
            [
                "title=Caddy Bunny",
                "description=Caddy with Bunny DNS module",
                "verify_module=dns.providers.bunny",
                "alpine_alias=true",
                "slim=true",
                "create_release=true",
                "platforms=linux/amd64,linux/arm64",
            ],
        )

    def test_cli(self):
        import contextlib
        import io

        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(main([str(_write(MINIMAL))]), 0)
            self.assertEqual(main([str(_write({**MINIMAL, "platforms": []}))]), 1)
        self.assertIn("platforms=" + ",".join(DEFAULT_PLATFORMS), out.getvalue())
        self.assertTrue(err.getvalue().startswith("::error::"))

    def test_overrides(self):
        cfg = load_image_config(_write({**MINIMAL, "alpine_alias": False, "slim": True}))
        self.assertEqual(cfg.official_variant_suffixes, [""])
        self.assertTrue(cfg.slim)

    def test_missing_required(self):
        with self.assertRaises(ImageConfigError):
            load_image_config(_write({"title": "x"}))

    def test_unknown_key(self):
        with self.assertRaises(ImageConfigError):
            load_image_config(_write({**MINIMAL, "modules": []}))

    def test_non_bool_flag(self):
        with self.assertRaises(ImageConfigError):
            load_image_config(_write({**MINIMAL, "slim": "yes"}))

    def test_invalid_json(self):
        with self.assertRaises(ImageConfigError):
            load_image_config(_write("{not json"))

    def test_missing_file(self):
        with self.assertRaises(ImageConfigError):
            load_image_config("/nonexistent/caddy-image.json")


if __name__ == "__main__":
    unittest.main()
