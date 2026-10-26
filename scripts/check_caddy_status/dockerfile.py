"""Reads what the checks need from a Dockerfile: the ``xcaddy build`` module list and the
base image of every ``FROM`` stage.

The Dockerfile is the single source of truth for both, so forks only edit it and the
daily check follows.
"""

import re
import shlex
from typing import NamedTuple

_WITH_RE = re.compile(r"^--with(?:=(.+))?$")
_INSTRUCTION_RE = re.compile(r"^([A-Za-z]+)\s+(.*)$")
_VAR_RE = re.compile(r"\$\{(\w+)(?:[:#%/^,+-][^}]*)?\}|\$(\w+)")


class Stage(NamedTuple):
    name: str  # None for an unnamed stage
    image: str  # base image reference with $ARG references expanded


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


def parse_stages(path, build_args=None):
    """Returns the ``FROM`` instructions as ``[Stage(name, image)]``.

    ``$ARG`` references in the image are expanded from the Dockerfile's own ``ARG NAME=default``
    lines, overridden by ``build_args``; an undefined ARG expands to nothing, as in Docker.
    Flags such as ``--platform`` are dropped.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise DockerfileError(f"Cannot read Dockerfile '{path}': {e}") from e

    args = {}
    stages = []
    for keyword, rest in _instructions(text):
        if keyword == "ARG":
            for token in rest.split():
                name, has_default, default = token.partition("=")
                if has_default or name not in args:
                    args[name] = default
        elif keyword == "FROM":
            tokens = [t for t in rest.split() if not t.startswith("--")]
            if not tokens:
                raise DockerfileError(f"Malformed FROM in '{path}': {rest}")
            name = tokens[2] if len(tokens) >= 3 and tokens[1].upper() == "AS" else None
            stages.append(Stage(name, _expand(tokens[0], {**args, **(build_args or {})})))

    if not stages:
        raise DockerfileError(f"No FROM instruction found in '{path}'")
    return stages


def _expand(text, values):
    return _VAR_RE.sub(lambda m: values.get(m.group(1) or m.group(2), ""), text)


def _instructions(text):
    """Yields ``(KEYWORD, rest)`` for each instruction with line continuations joined.

    Dockerfile comment lines are dropped first (they may sit inside a continued RUN).
    """
    without_comments = re.sub(r"(?m)^\s*#.*\n?", "", text)
    joined = re.sub(r"\\\s*\n", " ", without_comments)
    for line in joined.splitlines():
        m = _INSTRUCTION_RE.match(line.strip())
        if m:
            yield m.group(1).upper(), m.group(2).strip()


def _run_commands(text):
    """Yields each RUN instruction's shell text.

    Shell comment handling is off in the tokenizer: ``#`` is common inside parameter
    expansions such as ``${TARGETVARIANT#v}``.
    """
    for keyword, rest in _instructions(text):
        if keyword == "RUN":
            yield rest


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
