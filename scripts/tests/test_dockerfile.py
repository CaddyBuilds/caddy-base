import tempfile
import unittest
from pathlib import Path

from check_caddy_status.dockerfile import DockerfileError, parse_xcaddy_modules


def _write(text):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".Dockerfile", delete=False, encoding="utf-8")
    tmp.write(text)
    tmp.close()
    return Path(tmp.name)


class ParseXcaddyModulesTest(unittest.TestCase):
    def test_multiline_with_flags(self):
        path = _write(
            "ARG CADDY_VERSION\n"
            "FROM caddy:${CADDY_VERSION}-builder AS builder\n"
            "# Build Caddy with the Cloudflare DNS, proxy IP trust and rate limit modules\n"
            "RUN xcaddy build \\\n"
            "    --with github.com/caddy-dns/cloudflare \\\n"
            "    --with github.com/WeidiDeng/caddy-cloudflare-ip \\\n"
            "    --with github.com/mholt/caddy-ratelimit\n"
            "\n"
            "FROM caddy:${CADDY_VERSION} AS default\n"
            "COPY --from=builder /usr/bin/caddy /usr/bin/caddy\n"
        )
        self.assertEqual(
            parse_xcaddy_modules(path),
            [
                {"module": "github.com/caddy-dns/cloudflare", "repo": "caddy-dns/cloudflare"},
                {"module": "github.com/WeidiDeng/caddy-cloudflare-ip", "repo": "WeidiDeng/caddy-cloudflare-ip"},
                {"module": "github.com/mholt/caddy-ratelimit", "repo": "mholt/caddy-ratelimit"},
            ],
        )

    def test_version_replacement_subpath_and_equals_form(self):
        path = _write(
            "RUN xcaddy build v2.11.0 --with=github.com/caddy-dns/bunny@v1.2.3 "
            "--with github.com/foo/bar/sub/pkg=github.com/me/bar@main "
            "--with gitlab.com/x/y\n"
        )
        self.assertEqual(
            parse_xcaddy_modules(path),
            [
                {"module": "github.com/caddy-dns/bunny", "repo": "caddy-dns/bunny"},
                {"module": "github.com/foo/bar/sub/pkg", "repo": "foo/bar"},
                {"module": "gitlab.com/x/y", "repo": None},
            ],
        )

    def test_env_prefixed_cross_compile_line(self):
        path = _write(
            "FROM --platform=$BUILDPLATFORM caddy:${CADDY_VERSION}-builder AS builder\n"
            "ARG TARGETOS TARGETARCH TARGETVARIANT\n"
            "RUN GOOS=$TARGETOS GOARCH=$TARGETARCH GOARM=${TARGETVARIANT#v} CGO_ENABLED=0 \\\n"
            "    xcaddy build \\\n"
            "    --with github.com/caddy-dns/namecheap\n"
        )
        self.assertEqual(parse_xcaddy_modules(path), [{"module": "github.com/caddy-dns/namecheap", "repo": "caddy-dns/namecheap"}])

    def test_ignores_other_run_lines(self):
        path = _write("RUN apk add --no-cache ca-certificates\nRUN xcaddy build --with github.com/a/b\n")
        self.assertEqual(parse_xcaddy_modules(path), [{"module": "github.com/a/b", "repo": "a/b"}])

    def test_no_modules_is_an_error(self):
        path = _write("FROM caddy:2\nRUN echo hi\n")
        with self.assertRaises(DockerfileError):
            parse_xcaddy_modules(path)

    def test_missing_file_is_an_error(self):
        with self.assertRaises(DockerfileError):
            parse_xcaddy_modules("/nonexistent/Dockerfile")


if __name__ == "__main__":
    unittest.main()
