import json
from datetime import datetime, timezone

from .github_api import get_latest_commit
from .logger import log


def load_module_versions(path):
    """Loads the module version tracking file. Returns empty state if missing/invalid."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("modules"):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"last_checked": "", "modules": {}}


def save_module_versions(state, path, dry_run=False):
    """Saves the module version tracking file."""
    if dry_run:
        log.info(f"  [DRY-RUN] Would save module versions to {path}")
        return

    state["last_checked"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        log.info(f"  Saved module versions to {path}")
    except OSError as e:
        log.error(f"Failed to save module versions: {e}")


def check_module_updates(modules, versions_file):
    """Checks if any tracked modules have new commits.

    Args:
        modules: ``[{"module": ..., "repo": ...}]`` as parsed from the Dockerfile.
        versions_file: path of the tracking JSON file.

    Returns:
        tuple: (modules_changed, details, updated_state)
        details is a list of human-readable change descriptions, used in release notes.
        First run (empty state) records SHAs and triggers a build.
    """
    stored = load_module_versions(versions_file)
    is_first_run = not stored.get("modules")
    updated_state = {"last_checked": "", "modules": {}}
    changed_modules = []

    for mod in modules:
        module_name = mod["module"]
        repo = mod["repo"]
        log.info(f"  Checking module: {module_name}")

        if not repo:
            log.warn(f"  {module_name} is not hosted on github.com, cannot track its commits")
            continue

        current_sha, subject = get_latest_commit(repo)
        if not current_sha:
            log.warn(f"  Could not fetch SHA for {repo}, skipping")
            # Preserve existing entry
            if module_name in stored.get("modules", {}):
                updated_state["modules"][module_name] = stored["modules"][module_name]
            continue

        stored_sha = stored.get("modules", {}).get(module_name, {}).get("last_commit_sha", "")

        updated_state["modules"][module_name] = {
            "repo": repo,
            "last_commit_sha": current_sha,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }

        if is_first_run:
            log.info(f"    First run — recorded SHA: {current_sha[:12]}")
        elif stored_sha and current_sha != stored_sha:
            changed_modules.append(f"{repo} {stored_sha[:7]}..{current_sha[:7]} ({subject})" if subject else f"{repo} {stored_sha[:7]}..{current_sha[:7]}")
            log.info(f"    CHANGED: {stored_sha[:12]} -> {current_sha[:12]}")
        elif not stored_sha:
            # Module added to the Dockerfile since the last run: the image lacks it.
            changed_modules.append(f"{repo} added ({current_sha[:7]})")
            log.info(f"    NEW module — recorded SHA: {current_sha[:12]}")
        else:
            log.info(f"    Unchanged: {current_sha[:12]}")

    if is_first_run:
        log.info("  First run — recorded SHAs, triggering build to ensure image is fresh")
        return True, ["first run, module versions recorded"], updated_state

    return len(changed_modules) > 0, changed_modules, updated_state
