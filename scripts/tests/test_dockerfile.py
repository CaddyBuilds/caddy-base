import tempfile
import unittest
from pathlib import Path

from check_caddy_status.dockerfile import DockerfileError, Stage, parse_stages, parse_xcaddy_modules


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

    def test_comment_line_inside_continued_run(self):
        path = _write(
            "RUN xcaddy build \\\n"
            "    # the DNS provider\n"
            "    --with github.com/caddy-dns/bunny \\\n"
            "    --with github.com/mholt/caddy-ratelimit\n"
        )
        self.assertEqual([m["repo"] for m in parse_xcaddy_modules(path)], ["caddy-dns/bunny", "mholt/caddy-ratelimit"])

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


class ParseStagesTest(unittest.TestCase):
    IMAGE_REPO = (
        "ARG CADDY_VERSION\n"
        "FROM --platform=$BUILDPLATFORM caddy:${CADDY_VERSION}-builder AS builder\n"
        "ARG TARGETOS TARGETARCH TARGETVARIANT\n"
        "RUN GOARM=${TARGETVARIANT#v} xcaddy build --with github.com/caddy-dns/bunny\n"
        "\n"
        "# Default image\n"
        "FROM caddy:${CADDY_VERSION} AS default\n"
        "COPY --from=builder /usr/bin/caddy /usr/bin/caddy\n"
        "\n"
        "FROM ghcr.io/caddybuilds/caddy-base:latest as slim\n"
        "COPY --from=builder /usr/bin/caddy /usr/bin/caddy\n"
        "RUN setcap cap_net_bind_service=+ep /usr/bin/caddy\n"
    )

    def test_named_stages_with_build_arg(self):
        stages = parse_stages(_write(self.IMAGE_REPO), {"CADDY_VERSION": "2.11.7"})
        self.assertEqual(
            stages,
            [
                Stage("builder", "caddy:2.11.7-builder"),
                Stage("default", "caddy:2.11.7"),
                Stage("slim", "ghcr.io/caddybuilds/caddy-base:latest"),
            ],
        )

    def test_undefined_arg_expands_to_nothing(self):
        self.assertEqual(parse_stages(_write(self.IMAGE_REPO))[1].image, "caddy:")

    def test_arg_default_and_override(self):
        text = "ARG ALPINE=3.23\nARG OTHER\nFROM alpine:$ALPINE\nFROM alpine:${ALPINE} AS second\n"
        self.assertEqual(parse_stages(_write(text)), [Stage(None, "alpine:3.23"), Stage("second", "alpine:3.23")])
        self.assertEqual(parse_stages(_write(text), {"ALPINE": "3.22"})[0].image, "alpine:3.22")

    def test_plain_base_dockerfile(self):
        self.assertEqual(parse_stages(_write("# comment\nFROM alpine:3.23\nRUN apk add --no-cache libcap\n"))[0], Stage(None, "alpine:3.23"))

    def test_no_from_is_an_error(self):
        with self.assertRaises(DockerfileError):
            parse_stages(_write("RUN echo hi\n"))

    def test_missing_file_is_an_error(self):
        with self.assertRaises(DockerfileError):
            parse_stages("/nonexistent/Dockerfile")


if __name__ == "__main__":
    unittest.main()
