# Security Policy

## Supported versions

| What | Supported |
|---|---|
| Reusable workflows and scripts | The latest `v1.x` release, which the floating `v1` tag points to |
| `ghcr.io/caddybuilds/caddy-base` image | `latest` and `alpine3.23` (the pinned Alpine release), rebuilt daily when Alpine is republished |

Image repos should call the workflows at `@v1` to receive fixes without changing anything.

## Image vulnerabilities

The caddy-base image is Alpine plus the packages the official `caddy` image installs. OS
fixes arrive when Alpine republishes the pinned tag; we don't pin or patch package versions.
For vulnerabilities in the Caddy images built on it, see each image repo's security policy,
for example [caddy-cloudflare](https://github.com/CaddyBuilds/caddy-cloudflare/security/policy).

## Reporting a vulnerability

- **In Alpine or one of its packages:** report it to [Alpine](https://security.alpinelinux.org/).
- **In this repository** (the workflows, the check script, or the `Dockerfile`): report it
  privately with **Report a vulnerability** on the
  [Security tab](https://github.com/CaddyBuilds/caddy-base/security). Please don't open a
  public issue.
