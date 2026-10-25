# caddy-base

Shared build and release automation for the [CaddyBuilds](https://github.com/CaddyBuilds) Docker images:
[caddy-cloudflare](https://github.com/CaddyBuilds/caddy-cloudflare),
[caddy-bunny](https://github.com/CaddyBuilds/caddy-bunny),
[caddy-namecheap](https://github.com/CaddyBuilds/caddy-namecheap).

Each image repo keeps what makes it different: its `Dockerfile` (the module list), a small
`caddy-image.json`, its README and example Caddyfiles. Everything about *how* an image is
checked, built, tagged, verified and released lives here and is pulled in as reusable
workflows, so a fix lands in every repo on its next run.

## What is here

| Path | Purpose |
|---|---|
| `.github/workflows/build-image.yml` | Reusable: multi-platform build, push to GHCR and Docker Hub, verify, GitHub Release, failure issue |
| `.github/workflows/check-release.yml` | Reusable: daily check for new Caddy releases, module commits and republished official images; dispatches a build |
| `scripts/check_caddy_status/` | The checker. Reads the image repo's `Dockerfile` and `caddy-image.json`, tracks module commits in `module-versions.json` |
| `examples/` | A complete image repo skeleton: `Dockerfile`, `caddy-image.json`, the two caller workflows |

## Using it in an image repo

An image repo needs four files besides its README.

**`Dockerfile`**, complete and buildable on its own. The checker reads the modules from the
`xcaddy build` line, so this is the only place they are listed. Name the final stage
`default`; a `slim` stage is optional.

```dockerfile
ARG CADDY_VERSION
FROM --platform=$BUILDPLATFORM caddy:${CADDY_VERSION}-builder AS builder
ARG TARGETOS TARGETARCH TARGETVARIANT
RUN GOOS=$TARGETOS GOARCH=$TARGETARCH GOARM=${TARGETVARIANT#v} CGO_ENABLED=0 XCADDY_PRINT_VERSION=0 \
    xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM caddy:${CADDY_VERSION} AS default
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
```

The builder stage runs on the build host and cross-compiles, so the Go build is never
emulated; only the final `COPY` stage runs per platform. See [`examples/Dockerfile`](examples/Dockerfile).

**`caddy-image.json`**, the values the workflows cannot derive:

```json
{
  "title": "Caddy Cloudflare",
  "description": "Caddy with Cloudflare DNS module",
  "verify_module": "dns.providers.cloudflare",
  "alpine_alias": true,
  "slim": false,
  "create_release": true
}
```

| Key | Required | Default | Meaning |
|---|---|---|---|
| `title` | yes | | `org.opencontainers.image.title` |
| `description` | yes | | `org.opencontainers.image.description`, also used in release notes |
| `verify_module` | yes | | Module ID that must appear in `caddy list-modules` after the build |
| `alpine_alias` | no | `true` | Also push `X.Y.Z-alpine`, `X.Y-alpine`, `X-alpine` and `alpine` as aliases of the default image |
| `slim` | no | `false` | Also build the Dockerfile's `slim` stage and push `X.Y.Z-slim`, `X.Y-slim`, `X-slim`, `slim` |
| `create_release` | no | `true` | Create a GitHub Release per Caddy version and append rebuild notes to it |

**Two caller workflows**, copied from [`examples/.github/workflows/`](examples/.github/workflows/):

```yaml
jobs:
  build:
    uses: CaddyBuilds/caddy-base/.github/workflows/build-image.yml@v1
    with:
      caddy_version: ${{ github.event.inputs.build_version || github.event.client_payload.caddy_version }}
      build_reason: ${{ github.event.client_payload.build_reason || 'manual' }}
      build_details: ${{ github.event.client_payload.build_details || '' }}
    secrets: inherit
```

```yaml
jobs:
  check:
    uses: CaddyBuilds/caddy-base/.github/workflows/check-release.yml@v1
    secrets: inherit
```

Image names come from the repository name (`ghcr.io/<owner>/<repo>`), so a fork of any
image repo builds and publishes its own image without changing anything here.
Docker Hub is used when `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets exist;
`DOCKERHUB_REPOSITORY_NAME` (secret or variable) overrides the Docker Hub repository.

## How the check decides to build

1. Fetch the latest Caddy release and confirm the official image has every required platform.
2. If our image for that version is missing a platform on GHCR, build (`new_caddy_version`).
3. Compare each module's latest commit with `module-versions.json`; on change, build (`module_update`) and commit the new state.
4. Compare the official image's push time with our build time; if upstream republished, build (`base_image_update`).

The reason and details are passed to the build and recorded in the image labels
(`caddy-build.reason`, `caddy-build.details`, `caddy-build.base-workflow`) and the release notes.

## Versioning

Tags follow semver. `v1` is a floating tag that always points at the latest `v1.x.y`; image
repos pin `@v1` and pick up fixes automatically. A breaking change to inputs, the config
schema or the Dockerfile contract gets a new major and a one-line change in each caller.

The check workflow checks out this repo at the exact commit of the workflow being run, so
the Python package always matches the workflow version the caller selected.

## Development

```sh
cd scripts
python -m unittest discover -s tests -t . -v

# dry run against an image repo checkout
cd /path/to/caddy-cloudflare
PYTHONPATH=/path/to/caddy-base/scripts GITHUB_REPOSITORY=owner/repo \
  python -m check_caddy_status --dry-run
```

## License

MIT, see [LICENSE](LICENSE).
