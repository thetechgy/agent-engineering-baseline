"""Grade storage coverage from the submitted unit without executing its contents."""

import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat

METRIC = "podman_postgres_storage"
IMAGE_VOLUME = PurePosixPath("/var/lib/postgresql")
DEFAULT_PGDATA = IMAGE_VOLUME / "18/docker"
IMAGE = re.compile(r"(?:docker\.io/(?:library/)?)?postgres:18(?:\.\d+)?(?:-[a-z0-9.-]+)?(?:@sha256:[0-9a-f]{64})?")
VOLUME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*")


def absolute_path(value):
    path = PurePosixPath(value)
    if path.root != "/" or ".." in path.parts or "%" in value or "$" in value:
        raise ValueError("dynamic path")
    return path


def mount_outcome(source, options):
    bind = source.startswith(("/", "."))
    if source.startswith("/"):
        absolute_path(source)
    elif bind and ("%" in source or "$" in source):
        raise ValueError("dynamic bind source")
    elif not bind and source.endswith(".volume"):
        return "unsupported", "unresolved_quadlet_volume"

    if "O" in options:
        if bind and options == ["O"]:
            return "failed", "data_directory_on_ephemeral_overlay"
        return "unsupported", "unresolved_overlay_options"

    if "ro" in options or not (bind or VOLUME.fullmatch(source)):
        return "failed", "data_directory_on_non_writable_or_anonymous_mount"
    return "passed", "persistent_mount_covers_data_directory"


def grade(text):
    section = None
    seen_container = False
    fields = {}
    # The task asks for a self-contained unit. These directives can introduce
    # another source of configuration that this file alone cannot resolve.
    unresolved = {"EnvironmentFile", "EnvironmentHost", "PodmanArgs", "GlobalArgs",
                  "Exec", "Entrypoint", "Rootfs", "Secret", "VolumesFrom", "Mount",
                  "Tmpfs", "Include"}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            if section == "Container":
                seen_container = True
            continue
        key, separator, value = line.partition("=")
        if not separator or line.endswith("\\"):
            return "unsupported", "unit_syntax"
        key = key.strip()
        if section == "Container":
            if key in unresolved:
                return "unsupported", "unresolved_container_settings"
            fields.setdefault(key, []).append(value.strip())
        elif (section == "Service" and key.startswith(("Exec", "Bind", "TemporaryFileSystem"))
              or key == "Include"):
            return "unsupported", "unresolved_service_settings"
    if not seen_container:
        return "invalid", "missing_container_section"
    images = fields.get("Image", [])
    if len(images) != 1 or not IMAGE.fullmatch(images[0]):
        return "unsupported", "unrecognized_postgres_image"

    image_volume = fields.get("ImageVolume", [""])[-1].lower()
    if image_volume not in ("", "anonymous", "bind", "tmpfs", "ignore"):
        return "unsupported", "unresolved_image_volume_mode"

    try:
        pgdata = DEFAULT_PGDATA
        for value in fields.get("Environment", []):
            if not value:
                pgdata = DEFAULT_PGDATA
            for assignment in shlex.split(value):
                key, separator, path = assignment.partition("=")
                if key == "PGDATA":
                    if not separator:
                        raise ValueError("inherited PGDATA")
                    pgdata = absolute_path(path)
        mounts = {}
        for value in fields.get("Volume", []):
            if not value:
                mounts.clear()
                continue
            pieces = shlex.split(value)
            if len(pieces) != 1:
                raise ValueError("ambiguous volume")
            parts = pieces[0].split(":")
            if len(parts) == 1:
                source, destination, options = "", parts[0], ""
            elif len(parts) <= 3:
                source, destination, *option = parts
                options = option[0] if option else ""
            else:
                raise ValueError("ambiguous volume")
            target = absolute_path(destination)
            if target in mounts:
                raise ValueError("duplicate mount")
            mounts[target] = mount_outcome(source, options.split(","))
    except ValueError:
        return "unsupported", "unresolved_storage_settings"

    covering = sorted((target for target in mounts if pgdata.is_relative_to(target)),
                      key=lambda target: len(target.parts))
    if not covering:
        return "failed", "data_directory_outside_persistent_mount"
    effective = covering[-1]
    # An image volume survives an explicit ancestor mount. The explicit
    # mount wins if it replaces that destination or covers a deeper path.
    if (image_volume != "ignore" and pgdata.is_relative_to(IMAGE_VOLUME)
            and effective in IMAGE_VOLUME.parents):
        return "failed", "data_directory_on_implicit_image_volume"
    return mounts[effective]


def submission(path):
    # The verifier reads a bounded regular file and never follows a candidate link.
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                return "invalid", "submission_file_type"
            raw = stream.read(65537)
        if len(raw) > 65536:
            return "invalid", "submission_size"
        return grade(raw.decode())
    except FileNotFoundError:
        return "invalid", "missing_submission"
    except (OSError, UnicodeError):
        return "invalid", "unreadable_submission"


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value) + "\n")
    temporary.replace(path)


def main():
    entry = json.loads(Path("/tests/entry.json").read_text())
    outcome, reason = submission(Path("/workspace/output/postgres.container"))
    measured = outcome in {"passed", "failed"}
    score = float(outcome == "passed")
    metrics = {METRIC: score} if measured else {}
    details = {"outcome": {"classification": outcome,
                           "code": "evaluated" if measured else reason, "reason": reason}}
    log = Path(os.environ.get("HARBOR_REWARD_JSON", "/logs/verifier/reward.json")).parent
    write_json(log / "custom_reward.json", {
        "entry_id": entry["id"], "details": details, "custom_metrics": metrics,
    })
    write_json(log / "reward.json", {"overall": score, **metrics})
    (log / "reward.txt").write_text(str(score) + "\n")
    write_json(log / "skill_evaluator_reward.json", {
        "entry_id": entry["id"], "has_skill": entry["has_skill"],
        "overall": score, "evaluation_status": "complete" if measured else "failed",
        "details": details, "custom_metrics": metrics,
    })


if __name__ == "__main__":
    main()
