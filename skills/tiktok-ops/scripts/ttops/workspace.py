"""Workspace: the non-secret control plane binding one ad account to its assets.

Credentials never live here. ``workspace.json`` is safe to commit to a private
project repo; the token lives in the environment only.
"""

from __future__ import annotations

import hashlib
import json
import os

WORKSPACE_FILE = "workspace.json"
STATE_DIR = ".ttops"
SCHEMA_VERSION = "ttops.workspace/v1"


class WorkspaceError(Exception):
    pass


def _skill_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def discover(start=None, explicit=None):
    """Find workspace.json: explicit flag > TTOPS_WORKSPACE > nearest ancestor."""
    if explicit:
        path = os.path.abspath(explicit)
        if os.path.isdir(path):
            path = os.path.join(path, WORKSPACE_FILE)
        if not os.path.exists(path):
            raise WorkspaceError(f"No workspace at {path}")
        return path

    env = os.environ.get("TTOPS_WORKSPACE")
    if env:
        return discover(explicit=env)

    cur = os.path.abspath(start or os.getcwd())
    while True:
        candidate = os.path.join(cur, WORKSPACE_FILE)
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            raise WorkspaceError(
                "No workspace.json found in this directory or any parent. "
                "Copy specs/example-workspace.json into your project directory "
                "(NOT into the skill directory) and fill it in."
            )
        cur = parent


class Workspace:
    def __init__(self, path, data):
        self.path = path
        self.root = os.path.dirname(path)
        self.data = data

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, start=None, explicit=None):
        path = discover(start, explicit)
        skill_root = _skill_root()
        if os.path.commonpath([os.path.abspath(path), skill_root]) == skill_root:
            raise WorkspaceError(
                "Refusing a workspace inside the skill directory. Launch state and "
                "generated files belong in a per-account project directory, so an "
                "updated skill never carries someone's live account bindings."
            )
        with open(path) as fh:
            data = json.load(fh)
        ws = cls(path, data)
        ws.validate()
        return ws

    # -- validation --------------------------------------------------------

    def validate(self):
        d = self.data
        errors = []
        if d.get("schema") != SCHEMA_VERSION:
            errors.append(f"schema must be {SCHEMA_VERSION!r}, got {d.get('schema')!r}")
        if not isinstance(d.get("profiles"), dict) or not d["profiles"]:
            errors.append("profiles must be a non-empty object")
        for name, prof in (d.get("profiles") or {}).items():
            for field in ("advertiser_id", "currency", "timezone"):
                if not prof.get(field):
                    errors.append(f"profiles.{name}.{field} is required")
            if not isinstance(prof.get("advertiser_id"), str):
                errors.append(
                    f"profiles.{name}.advertiser_id must be a STRING "
                    "(v1.3 changed it from number; an int fails in confusing ways)"
                )
            blocked = set(d.get("blocked_advertiser_ids") or [])
            if prof.get("advertiser_id") in blocked:
                errors.append(f"profiles.{name}.advertiser_id is in blocked_advertiser_ids")
        if errors:
            raise WorkspaceError("Invalid workspace:\n  - " + "\n  - ".join(errors))
        return True

    # -- accessors ---------------------------------------------------------

    def profile(self, name=None):
        profiles = self.data["profiles"]
        if name is None:
            if len(profiles) == 1:
                name = next(iter(profiles))
            else:
                default = self.data.get("default_profile")
                if not default:
                    raise WorkspaceError(
                        f"Workspace has {len(profiles)} profiles and no default_profile. "
                        f"Pass --profile <one of: {', '.join(sorted(profiles))}>"
                    )
                name = default
        if name not in profiles:
            raise WorkspaceError(
                f"No profile {name!r}. Available: {', '.join(sorted(profiles))}"
            )
        prof = dict(profiles[name])
        prof["_name"] = name
        if prof["advertiser_id"] in set(self.data.get("blocked_advertiser_ids") or []):
            raise WorkspaceError(f"advertiser_id for profile {name!r} is blocked in this workspace")
        return prof

    def state_dir(self, create=True):
        path = os.path.join(self.root, STATE_DIR)
        if create:
            os.makedirs(path, exist_ok=True)
        real = os.path.realpath(path)
        if not real.startswith(os.path.realpath(self.root)):
            raise WorkspaceError("State directory escapes the workspace root")
        return path

    def fingerprint(self):
        blob = json.dumps(self.data, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj):
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()
