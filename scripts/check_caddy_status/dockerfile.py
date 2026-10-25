"""Reads the module list from the Dockerfile's ``xcaddy build`` command.

The Dockerfile is the single source of truth for which modules an image contains, so
forks only edit the ``--with`` lines and the daily check follows.
"""

import re
import shlex

_WITH_RE = re.compile(r"^--with(?:=(.+))?$")


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


def _run_commands(text):
    """Yields each RUN instruction's shell text with line continuations joined."""
    joined = re.sub(r"\\\s*\n", " ", text)
    for line in joined.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("RUN "):
            yield stripped[4:]


def _tokens(command):
    try:
        return shlex.split(command, comments=True)
    except ValueError:
        return command.split()


def _module_entry(spec):
    module = spec.split("=", 1)[0].split("@", 1)[0].strip()
    parts = module.split("/")
    repo = f"{parts[1]}/{parts[2]}" if parts[0] == "github.com" and len(parts) >= 3 else None
    return {"module": module, "repo": repo}
