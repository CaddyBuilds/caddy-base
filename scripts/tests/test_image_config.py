import json
import tempfile
import unittest
from pathlib import Path

from check_caddy_status.image_config import ImageConfigError, load_image_config


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
