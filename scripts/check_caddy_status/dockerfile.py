"""Reads what the daily check needs from the Dockerfile: the ``xcaddy build`` module list
and the slim stage's base image.

The Dockerfile is the single source of truth for both, so forks only edit it and the
daily check follows.
"""

import re
import shlex

_WITH_RE = re.compile(r"^--with(?:=(.+))?$")
_SLIM_FROM_RE = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)\s+AS\s+slim\s*$", re.IGNORECASE | re.MULTILINE)
_GHCR_REF_RE = re.compile(r"^ghcr\.io/([^:\s]+):([^:\s]+)$")


class DockerfileError(ValueError):
    pass


def parse_xcaddy_modules(path):
    """Returns the modules passed to ``xcaddy build`` as ``[{"module": ..., "repo": ...}]``.

    ``repo`` is the GitHub ``owner/name`` whose commits are tracked, or None when the module
    is not hosted on github.com (version suffixes and ``=replacement`` are stripped first).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise DockerfileError(f"Cannot read Dockerfile '{path}': {e}") from e

    modules = []
    for command in _run_commands(text):
        tokens = _tokens(command)
        if "xcaddy" not in tokens or "build" not in tokens:
            continue
        i = 0
        while i < len(tokens):
            m = _WITH_RE.match(tokens[i])
            if m:
                value = m.group(1)
                if value is None:
                    i += 1
                    value = tokens[i] if i < len(tokens) else ""
                if value:
                    modules.append(_module_entry(value))
            i += 1

    if not modules:
        raise DockerfileError(f"No 'xcaddy build --with ...' modules found in '{path}'")
    return modules


def parse_slim_base(path):
    """Returns the slim stage's base as ``(repository, tag)`` on GHCR, e.g.
    ``("caddybuilds/caddy-base", "latest")``.

    The base-image check reads its build time from GHCR, so the stage must be
    ``FROM ghcr.io/<owner>/<name>:<tag> AS slim``.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise DockerfileError(f"Cannot read Dockerfile '{path}': {e}") from e

    m = _SLIM_FROM_RE.search(text)
    if not m:
        raise DockerfileError(f"slim is enabled but '{path}' has no 'AS slim' stage")
    ref = _GHCR_REF_RE.match(m.group(1))
    if not ref:
        raise DockerfileError(f"The slim stage in '{path}' must be FROM ghcr.io/<owner>/<name>:<tag>, got {m.group(1)}")
    return ref.group(1), ref.group(2)


def _run_commands(text):
    """Yields each RUN instruction's shell text with line continuations joined.

    Dockerfile comment lines are dropped first (they may sit inside a continued RUN).
    Shell comment handling is off in the tokenizer: ``#`` is common inside parameter
    expansions such as ``${TARGETVARIANT#v}``.
    """
    without_comments = re.sub(r"(?m)^\s*#.*\n?", "", text)
    joined = re.sub(r"\\\s*\n", " ", without_comments)
    for line in joined.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("RUN "):
            yield stripped[4:]


def _tokens(command):
    try:
        return shlex.split(command, comments=False)
    except ValueError:
        return command.split()


def _module_entry(spec):
    module = spec.split("=", 1)[0].split("@", 1)[0].strip()
    parts = module.split("/")
    repo = f"{parts[1]}/{parts[2]}" if parts[0] == "github.com" and len(parts) >= 3 else None
    return {"module": module, "repo": repo}
