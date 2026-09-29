"""Workspace manifest: non-secret routing for one MCC/agency setup.

workspace.json lives in a project directory outside the skill store. Credentials never enter it.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
from dataclasses import dataclass
from typing import Any

SCHEMA = "googleops.workspace/v1"
FORBIDDEN_ROOTS = (".claude/skills", ".codex/skills")
DIGITS = re.compile(r"^[0-9]{10}$")
MERCHANT = re.compile(r"^[0-9]{6,12}$")
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


class WorkspaceError(Exception):
    pass


@dataclass
class Workspace:
    path: pathlib.Path
    data: dict[str, Any]

    @property
    def root(self) -> pathlib.Path:
        return self.path.parent

    @property
    def state_dir(self) -> pathlib.Path:
        rel = self.data["defaults"].get("state_dir", ".googleops")
        target = (self.root / rel).resolve()
        if self.root.resolve() not in target.parents and target != self.root.resolve():
            raise WorkspaceError(f"state_dir escapes the project: {target}")
        return target

    @property
    def api_version(self) -> str:
        return self.data["api_version"]

    def profile(self, name: str | None) -> tuple[str, dict[str, Any]]:
        chosen = name or self.data["defaults"]["profile"]
        try:
            return chosen, self.data["profiles"][chosen]
        except KeyError as exc:
            raise WorkspaceError(f"unknown profile: {chosen}") from exc

    def blocked(self, customer_id: str) -> bool:
        return customer_id in set(self.data.get("blocked_customers", []))


def _digits(value: Any, label: str) -> str:
    text = str(value).replace("-", "")
    if not DIGITS.match(text):
        raise WorkspaceError(f"{label} must be a 10-digit customer id (hyphens optional): {value!r}")
    return text


def validate_workspace(data: Any) -> None:
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise WorkspaceError(f"workspace schema must be {SCHEMA}")
    if not re.match(r"^v[0-9]+$", str(data.get("api_version", ""))):
        raise WorkspaceError("api_version must look like v25")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise WorkspaceError("profiles must be a non-empty object")
    for name, prof in profiles.items():
        if not NAME.match(name):
            raise WorkspaceError(f"bad profile name: {name}")
        for key in ("login_customer_id", "customer_id", "currency", "timezone", "budget_cap_major"):
            if key not in prof:
                raise WorkspaceError(f"profile {name}: missing {key}")
        _digits(prof["login_customer_id"], f"profile {name}.login_customer_id")
        _digits(prof["customer_id"], f"profile {name}.customer_id")
        if not re.match(r"^[A-Z]{3}$", str(prof["currency"])):
            raise WorkspaceError(f"profile {name}: currency must be ISO 4217")
        if not isinstance(prof["budget_cap_major"], (int, float)) or prof["budget_cap_major"] <= 0:
            raise WorkspaceError(f"profile {name}: budget_cap_major must be a positive number")
        if "merchant_id" in prof and not MERCHANT.match(str(prof["merchant_id"])):
            raise WorkspaceError(f"profile {name}: merchant_id must be numeric")
        for alias, cid in (prof.get("conversion_actions") or {}).items():
            if not NAME.match(alias) or not str(cid).isdigit():
                raise WorkspaceError(f"profile {name}: conversion_actions.{alias} must map to a numeric id")
    defaults = data.get("defaults")
    if not isinstance(defaults, dict) or defaults.get("profile") not in profiles:
        raise WorkspaceError("defaults.profile must name an existing profile")
    if defaults.get("auth", "oauth") not in ("oauth", "service_account"):
        raise WorkspaceError("defaults.auth must be oauth or service_account")
    for cid in data.get("blocked_customers", []):
        _digits(cid, "blocked_customers entry")


def workspace_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value).expanduser().resolve()
    return path / "workspace.json" if path.is_dir() else path


def discover_workspace(start: pathlib.Path | None = None) -> pathlib.Path | None:
    here = (start or pathlib.Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        probe = candidate / "workspace.json"
        if probe.is_file():
            return probe
    env = os.environ.get("GOOGLEOPS_WORKSPACE")
    return workspace_path(env) if env else None


def load_workspace(value: str | None) -> Workspace:
    path = workspace_path(value) if value else discover_workspace()
    if path is None or not path.is_file():
        raise WorkspaceError("no workspace.json found; pass --workspace or set GOOGLEOPS_WORKSPACE")
    text = str(path.resolve())
    if any(root in text for root in FORBIDDEN_ROOTS):
        raise WorkspaceError("workspace must live in a project directory, not inside a skill store")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"cannot read workspace: {exc}") from exc
    validate_workspace(data)
    ws = Workspace(path=path, data=data)
    ws.state_dir  # noqa: B018 — raises if it escapes the project
    return ws


def normalize_customer(value: Any) -> str:
    return _digits(value, "customer id")
