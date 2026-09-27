#!/usr/bin/env python3
"""Agent-facing launcher for the safe Meta Ads lifecycle.

This is a thin orchestration layer over probe.py, launch.py, bulk.py, verify.py,
and activate.py. It never assembles Graph payloads. apply creates ACTIVE by default
unless the spec sets create_status: PAUSED.

Typical single-account flow:

    metaops --workspace . --profile NAME assets verify --scope core
    metaops --workspace . --profile NAME doctor
    metaops --workspace . --profile NAME plan --spec campaign.json
    metaops --workspace . --profile NAME apply --plan .metaops/plans/<plan>.json --confirm SPEND
    metaops --workspace . --profile NAME verify --plan .metaops/plans/<plan>.json

apply creates every object ACTIVE by default and spends the moment the create succeeds — that
is why it also requires --confirm SPEND. A spec with "create_status": "PAUSED" builds paused
instead, for a run that needs a review window before spend:

    metaops --workspace . --profile NAME activate --plan .metaops/plans/<plan>.json \
        --confirm-ui REVIEWED --confirm SPEND

Use ``--json`` before the subcommand for one machine-readable result on stdout.
Child diagnostics are sent to stderr and are redacted by graph.py again here.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import activate
import asset_graph
import bulk
import graph
import launch
import meta_workspace

HERE = pathlib.Path(__file__).resolve().parent
PLAN_DIR = (HERE / launch.STATE_DIR / "plans").resolve()
RESULT_SCHEMA = "metaops.result/v1"
SINGLE_PLAN_SCHEMA = "metaops.plan/v1"
BULK_PLAN_SCHEMA = "metaops.bulk-plan/v1"
DOCTOR_SCHEMA = "metaops.doctor/v1"
ASSET_RECEIPT_SCHEMA = "metaops.assets/v1"
DEFAULT_TIMEOUT = 900
DOCTOR_MAX_AGE = int(os.environ.get("METAOPS_DOCTOR_MAX_AGE_SECONDS", "86400"))
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
WORKSPACE_LIFECYCLE_COMMANDS = {
    "media", "plan", "apply", "verify", "status", "activate", "bulk-plan", "bulk-apply",
    "bulk-activate", "feed", "edit", "clone", "rules", "catalog", "business", "review",
    "monitor", "comments", "page", "insights",
}

# Command groups implemented in cmd_*.py modules; each exposes register(sub, ctx).
COMMAND_MODULES = ("cmd_edit", "cmd_catalog", "cmd_business", "cmd_operate")


class MetaOpsError(Exception):
    """A launcher precondition or artifact error."""


@dataclass
class ChildResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def check_api_version(value: str | None, label: str) -> str | None:
    """Enforce the N/N-1 window: current passes silently, N-1 passes with an explicit
    sunset warning, anything else hard-fails. Fail-closed is preserved for genuinely
    incompatible payloads by keeping every non-version field check strict — only the
    version itself is downgraded to a warning inside the window."""
    status = graph.version_status(value)
    if status == "unsupported":
        raise MetaOpsError(
            f"{label} uses {value}, current launcher uses {graph.API_VERSION} "
            f"(supported: {', '.join(graph.SUPPORTED_VERSIONS)}); re-plan/re-verify "
            f"under a supported version"
        )
    warning = graph.version_warning(value)
    if warning:
        print(f"  ! {label} {warning}", file=sys.stderr)
    return warning


def configure_workspace(
    value: str | None, require_token: bool = True
) -> meta_workspace.Workspace | None:
    global PLAN_DIR
    selected = value or os.environ.get("METAOPS_WORKSPACE")
    if not selected:
        discovered = meta_workspace.discover_workspace()
        selected = str(discovered) if discovered else None
    if not selected:
        return None
    try:
        workspace = meta_workspace.load_workspace(selected)
    except meta_workspace.WorkspaceError as exc:
        raise MetaOpsError(str(exc)) from exc
    api_version = workspace.data.get("api_version")
    if api_version:
        check_api_version(api_version, "workspace")
    state_root = workspace.state_root
    launch.STATE_DIR = str(state_root)
    bulk.BULK_DIR = str((state_root / "bulk").resolve())
    os.environ["METAOPS_STATE_DIR"] = launch.STATE_DIR
    os.environ["METAOPS_BULK_DIR"] = bulk.BULK_DIR
    defaults = workspace.data.get("defaults") or {}
    token_env = str(defaults.get("token_env", "META_TOKEN"))
    if token_env != "META_TOKEN":
        # A workspace that names its own token env must get THAT token. Falling back to an
        # ambient META_TOKEN would run the workspace under whatever account last exported it.
        if os.environ.get(token_env):
            os.environ["META_TOKEN"] = os.environ[token_env]
        else:
            os.environ.pop("META_TOKEN", None)
            if require_token:
                raise MetaOpsError(
                    f"workspace defaults.token_env={token_env} but ${token_env} is empty; export "
                    "it (the ambient META_TOKEN is not used as a fallback)"
                )
    if defaults.get("allow_no_proxy") is True:
        os.environ.setdefault("META_ALLOW_NO_PROXY", "1")
    else:
        # The no-proxy escape hatch is a workspace decision; an inherited shell export must
        # not silently lift the proxy requirement for a workspace that did not opt in.
        os.environ.pop("META_ALLOW_NO_PROXY", None)
    os.environ["METAOPS_WORKSPACE"] = str(workspace.path)
    allowed_accounts = sorted(
        graph.normalize_account(profile["ad_account_id"])
        for profile in workspace.data["profiles"].values()
    )
    graph.authorize_writes(allowed_accounts)
    PLAN_DIR = (state_root / "plans").resolve()
    return workspace


def require_command_workspace(args: argparse.Namespace) -> None:
    if args.command in WORKSPACE_LIFECYCLE_COMMANDS and not args.workspace_obj:
        raise MetaOpsError(
            f"{args.command} requires a workspace; run inside a workspace or pass --workspace"
        )
    if args.command == "doctor" and not args.whoami and not args.workspace_obj:
        raise MetaOpsError(
            "account-targeted doctor requires a workspace; only doctor --whoami is workspace-free"
        )
    if (
        args.command == "doctor"
        and getattr(args, "scope", "core") == "provisioning"
        and not args.workspace_obj
    ):
        raise MetaOpsError("doctor --scope provisioning requires a workspace profile")


def require_provisioning_admin(
    workspace: meta_workspace.Workspace,
    requested_profile: str | None,
) -> dict[str, str]:
    """Prove the caller is the workspace's current Admin System User.

    Business-level provisioning creates or assigns assets outside an ad-account write
    boundary. OAuth scopes and an assigned asset do not establish that authority, so
    compare the token identity with the workspace System User and read its current role
    from the owning Business Portfolio immediately before the write.
    """
    profile_name, profile = workspace.profile(requested_profile)
    business_id = str(profile["business_id"])
    expected_id = str(profile.get("system_user_id") or "")
    if not expected_id:
        raise MetaOpsError(
            f"profiles.{profile_name} has no system_user_id. Provisioning (doctor --scope "
            "provisioning, catalog/business create, asset assignment) requires an Admin "
            "System User token and its id declared in the workspace profile — a plain user "
            "token cannot provision Business-Portfolio assets (`02`)."
        )
    me = graph.get("me", params={"fields": "id,name"}, context="provisioning token identity")
    current_id = str(me.get("id") or "")
    if not current_id:
        raise MetaOpsError("provisioning could not read the current token identity")
    if current_id != expected_id:
        raise MetaOpsError(
            "provisioning requires the workspace System User token: "
            f"/me is {current_id}, but profiles.{profile_name}.system_user_id is {expected_id}"
        )

    rows: list[dict[str, Any]] = []
    params: dict[str, Any] | None = {"fields": "id,name,role", "limit": 500}
    while params is not None:
        page = graph.get(
            f"{business_id}/system_users",
            params=params,
            context="provisioning System User role",
        )
        rows.extend(row for row in page.get("data", []) if isinstance(row, dict))
        params = graph.next_page_params(page, params)

    system_user = next((row for row in rows if str(row.get("id")) == expected_id), None)
    if system_user is None:
        raise MetaOpsError(
            f"workspace System User {expected_id} is not listed on Business Portfolio {business_id}; "
            "assign an Admin System User and retry"
        )
    role = str(system_user.get("role") or "").upper()
    if role != "ADMIN":
        raise MetaOpsError(
            f"provisioning requires an ADMIN System User; {expected_id} has role {role or 'unknown'}. "
            "Employee System Users may operate assigned assets but cannot create or assign "
            "Business-Portfolio assets."
        )
    return {
        "profile": profile_name,
        "business_id": business_id,
        "system_user_id": expected_id,
        "system_user_name": str(system_user.get("name") or me.get("name") or ""),
        "role": role,
    }


def require_plan_workspace(
    plan: dict[str, Any],
    current: meta_workspace.Workspace | None,
    requested_profile: str | None = None,
) -> tuple[meta_workspace.Workspace, str, dict[str, Any]]:
    if current is None:
        raise MetaOpsError("a workspace is required for every saved lifecycle plan")
    if not plan.get("workspace_path") or not plan.get("workspace_sha"):
        raise MetaOpsError("legacy workspace-free plan is not executable; create a new plan")
    if resolve_input(str(plan["workspace_path"])) != current.path:
        raise MetaOpsError("current workspace does not match the workspace bound to this plan")
    if file_sha(current.path) != plan.get("workspace_sha"):
        raise MetaOpsError("workspace changed after plan; verify assets and create a new plan")
    profile_name, profile = current.profile(requested_profile or plan.get("profile"))
    if plan.get("profile") and plan["profile"] != profile_name:
        raise MetaOpsError("selected profile does not match the profile bound to this plan")
    return current, profile_name, profile


def resolve_input(value: str) -> pathlib.Path:
    return pathlib.Path(value).expanduser().resolve()


def safe_name(value: str, label: str) -> str:
    if not SAFE_NAME.fullmatch(value):
        raise MetaOpsError(
            f"{label} must be 1-120 characters: letters, numbers, dot, underscore, hyphen"
        )
    return value


def read_json(path: pathlib.Path, label: str) -> Any:
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise MetaOpsError(f"{label} does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MetaOpsError(f"{label} is not valid JSON: {path}: {exc}") from exc


def atomic_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def file_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def doctor_path(account_id: str) -> pathlib.Path:
    account = graph.normalize_account(account_id)
    if not re.fullmatch(r"act_[0-9]+", account):
        raise MetaOpsError(f"invalid account id for doctor receipt: {account_id}")
    return (PLAN_DIR / f"doctor.{account}.json").resolve()


def asset_receipt_path(profile: str, scope: str) -> pathlib.Path:
    return (PLAN_DIR / f"assets.{safe_name(profile, 'profile')}.{scope}.json").resolve()


def _fresh_timestamp(receipt: dict[str, Any], path: pathlib.Path) -> None:
    try:
        checked_at = dt.datetime.fromisoformat(str(receipt["checked_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError) as exc:
        raise MetaOpsError(f"receipt has no valid checked_at: {path}") from exc
    if checked_at.tzinfo is None:
        raise MetaOpsError(f"receipt checked_at has no UTC offset: {path}")
    age = (dt.datetime.now(dt.timezone.utc) - checked_at.astimezone(dt.timezone.utc)).total_seconds()
    if age < -300 or age > DOCTOR_MAX_AGE:
        raise MetaOpsError(f"receipt is stale or future-dated ({int(age)}s): refresh it")


def require_doctor(
    spec: dict[str, Any],
    receipt_arg: str | None = None,
    business_id: str | None = None,
) -> tuple[pathlib.Path, str]:
    path = resolve_input(receipt_arg) if receipt_arg else doctor_path(str(spec["account_id"]))
    receipt = read_json(path, "doctor receipt")
    if not isinstance(receipt, dict) or receipt.get("schema") != DOCTOR_SCHEMA:
        raise MetaOpsError(f"unsupported doctor receipt: {path}")
    _fresh_timestamp(receipt, path)
    # Version rides the N/N-1 window (warning on N-1); every other bound field stays
    # fail-closed: a changed account/Page/dataset/BM still refuses even on N-1.
    check_api_version(receipt.get("api_version"), "doctor receipt")
    expected = {
        "account_id": graph.normalize_account(str(spec["account_id"])),
        "page_id": str(spec.get("page_id")) if spec.get("page_id") is not None else None,
        "dataset_id": str(spec.get("pixel_id")) if spec.get("pixel_id") is not None else None,
        "business_id": str(business_id) if business_id is not None else None,
    }
    for key, value in expected.items():
        if value is not None and str(receipt.get(key)) != value:
            raise MetaOpsError(
                f"doctor receipt {key} mismatch ({receipt.get(key)} != {value}); run doctor again"
            )
    return path, file_sha(path)


def requires_catalog(spec: dict[str, Any]) -> bool:
    return any(
        (ad.get("creative") or {}).get("kind") in {"catalog_collection", "catalog_single", "catalog_carousel"}
        for adset in spec.get("adsets") or []
        for ad in adset.get("ads") or []
    )


def require_assets(
    workspace: meta_workspace.Workspace,
    profile: str,
    catalog_required: bool,
) -> tuple[pathlib.Path, str]:
    scopes = ["all"] if catalog_required else ["core", "all"]
    candidates = [asset_receipt_path(profile, scope) for scope in scopes]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        scope = "all" if catalog_required else "core"
        raise MetaOpsError(
            f"fresh asset receipt required; run assets verify --scope {scope} for profile {profile}"
        )
    errors: list[str] = []
    for path in existing:
        try:
            return validate_asset_receipt(path, workspace, profile, catalog_required)
        except MetaOpsError as exc:
            errors.append(str(exc))
    raise MetaOpsError(errors[-1])


def validate_asset_receipt(
    path: pathlib.Path,
    workspace: meta_workspace.Workspace,
    profile: str,
    catalog_required: bool,
) -> tuple[pathlib.Path, str]:
    receipt = read_json(path, "asset receipt")
    if not isinstance(receipt, dict) or receipt.get("schema") != ASSET_RECEIPT_SCHEMA:
        raise MetaOpsError(f"unsupported asset receipt: {path}")
    _fresh_timestamp(receipt, path)
    check_api_version(receipt.get("api_version"), "asset receipt")
    if receipt.get("profile") != profile or receipt.get("workspace_sha") != file_sha(workspace.path):
        raise MetaOpsError("workspace/profile changed after asset verification; verify assets again")
    if catalog_required and receipt.get("scope") != "all":
        raise MetaOpsError("catalog launch requires an all-scope asset receipt")
    return path, file_sha(path)


def child_command(script: str, args: list[str]) -> list[str]:
    return [sys.executable, str(HERE / script), *args]


def normalized_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_child(script: str, args: list[str], timeout: int) -> ChildResult:
    argv = child_command(script, args)
    env = os.environ.copy()
    read_fd: int | None = None
    if graph._WRITE_ACCOUNTS is not None:
        read_fd, write_fd = os.pipe()
        capability = {
            "parent_pid": os.getpid(),
            "allowed_accounts": sorted(graph._WRITE_ACCOUNTS),
        }
        os.write(write_fd, json.dumps(capability).encode("utf-8"))
        os.close(write_fd)
        env["METAOPS_AUTH_FD"] = str(read_fd)
    workspace_path = env.get("METAOPS_WORKSPACE")
    cwd = pathlib.Path(workspace_path).expanduser().resolve().parent if workspace_path else HERE
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            pass_fds=(read_fd,) if read_fd is not None else (),
        )
    finally:
        if read_fd is not None:
            os.close(read_fd)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
        stdout = graph.redact(normalized_text(stdout or exc.stdout))
        stderr = graph.redact(normalized_text(stderr or exc.stderr))
        raise MetaOpsError(
            f"{script} timed out after {timeout}s. It was terminated; reconcile any in-flight "
            f"create from the state file before retrying.\n{stderr or stdout}"
        ) from exc
    return ChildResult(
        argv=argv,
        returncode=proc.returncode,
        stdout=graph.redact(stdout),
        stderr=graph.redact(stderr),
    )


def echo_child(result: ChildResult) -> None:
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", file=sys.stderr)
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)


def graph_error(text: str) -> dict[str, Any] | None:
    match = re.search(r"code=(?P<code>[^ ]+) subcode=(?P<subcode>[^:]+):", text)
    trace = re.search(r"\(trace (?P<trace>[^)]*)\)", text)
    if not match and not trace:
        return None
    out: dict[str, Any] = {}
    if match:
        for key in ("code", "subcode"):
            raw = match.group(key)
            out[key] = None if raw == "None" else int(raw) if raw.isdigit() else raw
    if trace and trace.group("trace"):
        out["fbtrace_id"] = trace.group("trace")
    return out


def result_envelope(
    command: str,
    ok: bool,
    phase: str,
    *,
    artifacts: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "ok": ok,
        "command": command,
        "phase": phase,
        "artifacts": artifacts or {},
        "data": data or {},
        "error": error,
        "next_action": next_action,
    }


def child_failure(command: str, phase: str, child: ChildResult) -> dict[str, Any]:
    combined = f"{child.stderr}\n{child.stdout}".strip()
    return result_envelope(
        command,
        False,
        phase,
        data={"child_exit_code": child.returncode},
        error={
            "kind": "child_failed",
            "message": (combined[-2000:] if combined else f"{child.argv[1]} exited non-zero"),
            "graph": graph_error(combined),
        },
        next_action="Inspect stderr and the state artifact; reconcile in-flight creates before retrying.",
    )


def single_plan_path(run_id: str, spec_sha: str, requested: str | None) -> pathlib.Path:
    if requested:
        return resolve_input(requested)
    return PLAN_DIR / f"{safe_name(run_id, 'run_id')}.{spec_sha}.plan.json"


def load_launch_spec(path: pathlib.Path) -> dict[str, Any]:
    try:
        return launch.load_spec(str(path))
    except SystemExit as exc:
        message = str(exc) or f"invalid launch spec: {path}"
        raise MetaOpsError(message) from exc


def build_single_plan(spec_path: pathlib.Path, state_arg: str | None = None,
                      spec_override: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = spec_override if spec_override is not None else load_launch_spec(spec_path)
    run_id = safe_name(str(spec["run_id"]), "run_id")
    sha = launch.spec_hash(spec)
    state_path = resolve_input(state_arg) if state_arg else (HERE / launch.STATE_DIR / f"{run_id}.json").resolve()
    snapshot = (PLAN_DIR / f"{run_id}.{sha}.spec.json").resolve()
    dry_state = (PLAN_DIR / f"{run_id}.{sha}.dry-state.json").resolve()
    return {
        "schema": SINGLE_PLAN_SCHEMA,
        "created_at": now_utc(),
        "api_version": graph.API_VERSION,
        "kind": "single",
        "run_id": run_id,
        "account_id": spec["account_id"],
        "source_spec_path": str(spec_path),
        "spec_path": str(snapshot),
        "spec_sha": sha,
        "state_path": str(state_path),
        "dry_state_path": str(dry_state),
        "validation_scope": {
            "api": ["campaign", "creatives"],
            "local_only_until_apply": ["campaign budget patch", "ad_sets", "ads"],
        },
        "apply_effect": (
            "Creates or resumes objects PAUSED. Never activates."
            if spec.get("create_status", "ACTIVE") == "PAUSED"
            else "Creates or resumes objects ACTIVE. apply requires --confirm SPEND and spends "
                 "immediately on success."
        ),
    }


def load_plan(path_arg: str, expected: set[str] | None = None) -> tuple[pathlib.Path, dict[str, Any]]:
    path = resolve_input(path_arg)
    plan = read_json(path, "plan")
    if not isinstance(plan, dict) or plan.get("schema") not in {SINGLE_PLAN_SCHEMA, BULK_PLAN_SCHEMA}:
        raise MetaOpsError(f"unsupported plan schema in {path}")
    if expected and plan.get("schema") not in expected:
        raise MetaOpsError(f"wrong plan kind for this command: {plan.get('schema')}")
    # Plan version rides the same N/N-1 window: N-1 warns (sunset), outside refuses.
    # Spec/workspace/doctor/asset bindings below stay fail-closed regardless.
    check_api_version(plan.get("api_version"), "plan")
    return path, plan


def validate_single_plan(
    plan: dict[str, Any],
    current_workspace: meta_workspace.Workspace | None = None,
    requested_profile: str | None = None,
) -> tuple[pathlib.Path, pathlib.Path]:
    spec_path = resolve_input(plan["spec_path"])
    spec = load_launch_spec(spec_path)
    current_sha = launch.spec_hash(spec)
    if current_sha != plan.get("spec_sha"):
        raise MetaOpsError(
            f"spec changed after plan ({plan.get('spec_sha')} != {current_sha}); run plan again"
        )
    if spec.get("run_id") != plan.get("run_id") or spec.get("account_id") != plan.get("account_id"):
        raise MetaOpsError("plan run/account no longer matches the normalized spec; run plan again")
    workspace, profile_name, profile = require_plan_workspace(
        plan, current_workspace, requested_profile
    )
    if graph.normalize_account(profile["ad_account_id"]) != plan.get("account_id"):
        raise MetaOpsError("plan account no longer matches its workspace profile")
    doctor_receipt, doctor_sha = require_doctor(
        spec, plan.get("doctor_receipt"), str(profile["business_id"])
    )
    if str(doctor_receipt) != plan.get("doctor_receipt") or doctor_sha != plan.get("doctor_sha"):
        raise MetaOpsError("doctor receipt changed after plan; run doctor and plan again")
    asset_receipt, asset_sha = validate_asset_receipt(
        resolve_input(str(plan.get("asset_receipt") or "")),
        workspace,
        profile_name,
        requires_catalog(spec),
    )
    if str(asset_receipt) != plan.get("asset_receipt") or asset_sha != plan.get("asset_sha"):
        raise MetaOpsError("asset receipt changed after plan; verify assets and plan again")
    return spec_path, resolve_input(plan["state_path"])


def require_state_binding(plan: dict[str, Any], state_path: pathlib.Path) -> dict[str, Any]:
    state = read_json(state_path, "state")
    if not isinstance(state, dict):
        raise MetaOpsError(f"state is not a JSON object: {state_path}")
    if state.get("spec_sha") != plan.get("spec_sha"):
        raise MetaOpsError(
            f"state belongs to a different spec ({state.get('spec_sha')} != {plan.get('spec_sha')})"
        )
    if graph.normalize_account(str(state.get("spec_account") or "")) != plan.get("account_id"):
        raise MetaOpsError(
            f"state belongs to a different account ({state.get('spec_account')} != {plan.get('account_id')})"
        )
    return state


def validate_future_start(value: str) -> None:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MetaOpsError("--refresh-start must be valid ISO-8601") from exc
    if parsed.tzinfo is None:
        raise MetaOpsError("--refresh-start must include a UTC offset")
    if parsed.astimezone(dt.timezone.utc) <= dt.datetime.now(dt.timezone.utc):
        raise MetaOpsError("--refresh-start must be in the future")


@contextlib.contextmanager
def state_lock(state_path: pathlib.Path) -> Iterator[pathlib.Path]:
    lock = pathlib.Path(str(state_path) + ".metaops.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        detail = ""
        try:
            detail = lock.read_text(encoding="utf-8").strip()
        except OSError:
            pass
        raise MetaOpsError(
            f"state is locked by another launcher: {lock}{f' ({detail})' if detail else ''}"
        ) from exc
    owned = os.fstat(fd)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"pid": os.getpid(), "created_at": now_utc()}))
        yield lock
    finally:
        try:
            current = lock.stat()
            if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
                lock.unlink()
        except FileNotFoundError:
            pass


def _start_time_blocker(
    spec_path: pathlib.Path | None,
    fix: str = "pass a future --refresh-start",
) -> str | None:
    if spec_path is None:
        return None
    try:
        spec = load_launch_spec(spec_path)
        starts = [
            dt.datetime.fromisoformat(str(adset["start_time"]).replace("Z", "+00:00"))
            for adset in spec["adsets"]
        ]
    except (KeyError, TypeError, ValueError, OSError, MetaOpsError) as exc:
        return f"cannot read bound spec start_time: {exc}"
    if any(
        start.tzinfo is None or start.astimezone(dt.timezone.utc) <= dt.datetime.now(dt.timezone.utc)
        for start in starts
    ):
        return f"an ad-set start_time is past or lacks an offset; {fix}"
    return None


APPLY_START_FIX = "set a future start_time with a UTC offset in the spec and run plan again"


def _active_start_blocker(spec_path: pathlib.Path) -> str | None:
    """An ACTIVE create goes live on success, so the same start_time gate activate uses
    applies at apply time. A PAUSED build is checked again at activation instead."""
    spec = load_launch_spec(spec_path)
    if spec.get("create_status", "ACTIVE") != "ACTIVE":
        return None
    return _start_time_blocker(spec_path, APPLY_START_FIX)


def state_summary(state_path: pathlib.Path, spec_path: pathlib.Path | None = None) -> dict[str, Any]:
    if not state_path.exists():
        return {
            "exists": False,
            "phase": "planned",
            "objects": 0,
            "in_flight": [],
            "errors": 0,
            "activation_ready": False,
            "activation_blocker": "state file does not exist; apply the plan",
        }
    state = read_json(state_path, "state")
    objects = state.get("objects") or {}
    in_flight = sorted((state.get("in_flight") or {}).keys())
    receipt = pathlib.Path(str(state_path) + ".verified.json")
    blocker = activate.check_receipt(str(state_path), state)
    if in_flight:
        blocker = f"unresolved in-flight creates: {in_flight}"
    if not any(key.startswith("ad[") for key in objects):
        blocker = "state contains no ads"
    if blocker is None:
        blocker = _start_time_blocker(spec_path)
    phase = "verified" if blocker is None else "reconcile_required" if in_flight else "built"
    return {
        "exists": True,
        "phase": phase,
        "objects": len(objects),
        "object_keys": sorted(objects),
        "in_flight": in_flight,
        "errors": len(state.get("errors") or []),
        "receipt": str(receipt) if receipt.exists() else None,
        "activation_ready": blocker is None,
        "activation_blocker": blocker,
    }


def command_pace(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Local pacing state: throttle cooldowns and last campaign create per account. No API call."""
    import time as _time
    data = graph._pace_load()
    now = _time.time()
    cooldowns = {k: {"minutes_left": round((float(v) - now) / 60, 1),
                     "reason": (data.get("cooldown_reason") or {}).get(k)}
                 for k, v in (data.get("cooldown") or {}).items() if float(v) > now}
    gap_h = float(os.environ.get("METAOPS_CREATE_GAP_HOURS", graph.CAMPAIGN_CREATE_GAP_H))
    creates = {k: {"hours_ago": round((now - float(v)) / 3600, 2),
                   "next_create_in_min": max(0, round((gap_h * 3600 - (now - float(v))) / 60))}
               for k, v in (data.get("last_campaign_create") or {}).items()}
    if args.clear_cooldown:
        data.get("cooldown", {}).pop(args.clear_cooldown, None)
        graph._pace_save(data)
    return 0, result_envelope("pace", True, "pace", data={
        "file": graph._pace_file(), "cooldowns": cooldowns, "campaign_creates": creates,
        "rules": {"throttle_cooldown_min": float(os.environ.get("METAOPS_THROTTLE_COOLDOWN_MIN",
                                                               graph.THROTTLE_COOLDOWN_MIN)),
                  "campaign_create_gap_h": gap_h},
    }, next_action=("Do not touch accounts on cooldown; --clear-cooldown only when the operator asks."
                    if cooldowns else None))


def command_doctor(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    scope = getattr(args, "scope", "core")
    if not args.workspace_obj and args.profile:
        raise MetaOpsError("--profile requires --workspace")
    if scope == "provisioning" and not args.workspace_obj:
        raise MetaOpsError("doctor --scope provisioning requires a workspace profile")
    if scope == "provisioning" and args.whoami:
        raise MetaOpsError("doctor --scope provisioning is profile-bound; omit --whoami")
    if scope == "provisioning" and (args.create_pbia or args.attach_pixel):
        raise MetaOpsError("doctor --scope provisioning is read-only; omit --create-pbia/--attach-pixel")
    if args.workspace_obj and not args.whoami:
        _, profile = args.workspace_obj.profile(args.profile)
        for attr, key in (
            ("account", "ad_account_id"), ("page", "page_id"),
            ("dataset", "dataset_id"), ("business", "business_id"),
        ):
            supplied = getattr(args, attr)
            expected = profile.get(key)
            if attr == "account" and supplied:
                supplied = graph.normalize_account(supplied)
            if supplied is not None and str(supplied) != str(expected):
                raise MetaOpsError(f"doctor --{attr} conflicts with workspace profile")
            setattr(args, attr, expected)
    if args.whoami and args.account:
        raise MetaOpsError("use doctor --whoami or doctor --account ..., not both")
    if args.whoami and any((args.page, args.dataset, args.business, args.create_pbia, args.attach_pixel)):
        raise MetaOpsError("doctor --whoami is intake-only; do not combine it with Page/dataset mutations")
    child_args: list[str] = []
    if args.whoami or not args.account:
        child_args.append("--whoami")
    if args.account:
        child_args += ["--account", args.account]
    for flag, value in (("--page", args.page), ("--dataset", args.dataset), ("--business", args.business)):
        if value:
            child_args += [flag, value]
    if args.create_pbia:
        child_args.append("--create-pbia")
    if args.attach_pixel:
        child_args.append("--attach-pixel")
    child = run_child("probe.py", child_args, args.timeout)
    echo_child(child)
    if not child.ok:
        return child.returncode, child_failure("doctor", "gate_failed", child)
    provisioning: dict[str, str] | None = None
    if scope == "provisioning":
        provisioning = require_provisioning_admin(args.workspace_obj, args.profile)
    artifacts: dict[str, Any] = {}
    if args.account:
        account = graph.normalize_account(args.account)
        receipt_path = doctor_path(account)
        receipt = {
            "schema": DOCTOR_SCHEMA,
            "checked_at": now_utc(),
            "api_version": graph.API_VERSION,
            "account_id": account,
            "page_id": str(args.page) if args.page else None,
            "dataset_id": str(args.dataset) if args.dataset else None,
            "business_id": str(args.business) if args.business else None,
        }
        atomic_json(receipt_path, receipt)
        artifacts["doctor_receipt"] = str(receipt_path)
    return 0, result_envelope(
        "doctor", True, "preflight_passed", artifacts=artifacts,
        data={"scope": scope, "provisioning": provisioning} if provisioning else None,
        next_action=(
            "Provisioning authority is live; run a guarded create or asset-assignment command."
            if provisioning else "Create media/spec, then run metaops plan."
        ),
    )


def command_plan(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    spec_path = resolve_input(args.spec)
    if not spec_path.is_file():
        raise MetaOpsError(f"spec does not exist: {spec_path}")
    snapshot_spec: dict[str, Any]
    profile_name = None
    try:
        raw = read_json(spec_path, "spec")
        profile_name, resolved = meta_workspace.resolve_spec(
            raw, args.workspace_obj, args.profile
        )
    except meta_workspace.WorkspaceError as exc:
        raise MetaOpsError(str(exc)) from exc
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    fd, incoming_name = tempfile.mkstemp(prefix=".resolved.", suffix=".json", dir=PLAN_DIR)
    incoming = pathlib.Path(incoming_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(resolved, fh, ensure_ascii=False)
            fh.write("\n")
        snapshot_spec = load_launch_spec(incoming)
    finally:
        incoming.unlink(missing_ok=True)
    plan = build_single_plan(spec_path, args.state, snapshot_spec)
    plan["profile"] = profile_name
    plan["workspace_path"] = str(args.workspace_obj.path)
    plan["workspace_sha"] = file_sha(args.workspace_obj.path)
    asset_receipt, asset_sha = require_assets(
        args.workspace_obj, profile_name, requires_catalog(snapshot_spec)
    )
    plan["asset_receipt"] = str(asset_receipt)
    plan["asset_sha"] = asset_sha
    plan_path = single_plan_path(plan["run_id"], plan["spec_sha"], args.out)
    _, profile = args.workspace_obj.profile(profile_name)
    doctor_receipt, doctor_sha = require_doctor(
        snapshot_spec, args.doctor_receipt, str(profile["business_id"])
    )
    plan["doctor_receipt"] = str(doctor_receipt)
    plan["doctor_sha"] = doctor_sha
    atomic_json(resolve_input(plan["spec_path"]), snapshot_spec)
    child = run_child(
        "launch.py",
        ["--spec", plan["spec_path"], "--dry-run", "--state", plan["dry_state_path"]],
        args.timeout,
    )
    echo_child(child)
    if not child.ok:
        return child.returncode, child_failure("plan", "validation_failed", child)
    swap = plan_swap_check(snapshot_spec, profile)
    if swap.get("blockers"):
        return 1, result_envelope(
            "plan", False, "swap_targets_invalid", data={"swap": swap},
            error={"kind": "swap_target", "message": "; ".join(swap["blockers"])},
            next_action="Fix before launch: target SKUs (creative.swap_to) need name/description/image; white "
                        "items in the review set need their own white name/description and no gambling "
                        "words (creative.allow_white_text overrides the word check on purpose).")
    atomic_json(plan_path, plan)
    return 0, result_envelope(
        "plan",
        True,
        "validated",
        artifacts={"plan": str(plan_path), "dry_state": plan["dry_state_path"]},
        data={"run_id": plan["run_id"], "account_id": plan["account_id"],
              "spec_sha": plan["spec_sha"], "validation_scope": plan["validation_scope"], "swap": swap},
        next_action=f"Review the plan, then run: metaops.py apply --plan {plan_path}",
    )


def plan_swap_check(spec: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Catalog launches: the swap map from creative.swap_to, and its target SKUs checked NOW
    (a missing or empty target found after approval means the white keeps spending)."""
    if not requires_catalog(spec):
        return {}
    swap_map, problems = spec_swap_map(spec, profile.get("product_sets") or {})
    out: dict[str, Any] = {"map": swap_map, "warnings": problems, "blockers": []}
    catalog_id = str(profile.get("catalog_id") or "")
    rids = sorted({r for pair in swap_map.split(",") if pair for r in pair.partition("=")[2].split("+")})
    import swapgate
    if rids and catalog_id:
        out["targets"], out["blockers"] = swapgate.target_items(catalog_id, rids)
    # The review set: white items must carry their own white texts (review reads them under the card).
    sets = sorted({str((ad.get("creative") or {}).get("product_set_id"))
                   for aset in spec.get("adsets") or [] for ad in aset.get("ads") or []
                   if str((ad.get("creative") or {}).get("kind", "")).startswith("catalog")
                   and not (ad.get("creative") or {}).get("allow_white_text")})
    for set_id in sets:
        out["blockers"] += swapgate.white_item_problems(set_id)
    return out


def command_workspace_validate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if not args.workspace_obj:
        raise MetaOpsError("workspace validate requires --workspace")
    profiles = sorted(args.workspace_obj.data["profiles"])
    return 0, result_envelope(
        "workspace validate",
        True,
        "valid",
        artifacts={"workspace": str(args.workspace_obj.path),
                   "state_root": str(args.workspace_obj.state_root)},
        data={"name": args.workspace_obj.data["name"], "profiles": profiles,
              "default_profile": (args.workspace_obj.data.get("defaults") or {}).get("profile")},
        next_action="Run assets verify, then doctor for the selected profile.",
    )


def command_assets_verify(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if not args.workspace_obj:
        raise MetaOpsError("assets verify requires --workspace")
    try:
        report = asset_graph.verify_assets(args.workspace_obj, args.profile, args.scope)
    except (meta_workspace.WorkspaceError, graph.GraphError) as exc:
        raise MetaOpsError(str(exc)) from exc
    ok = bool(report["ready"])
    artifacts = {"workspace": str(args.workspace_obj.path)}
    if ok:
        receipt_path = asset_receipt_path(report["profile"], args.scope)
        atomic_json(receipt_path, {
            "schema": ASSET_RECEIPT_SCHEMA,
            "checked_at": now_utc(),
            "api_version": graph.API_VERSION,
            "workspace": str(args.workspace_obj.path),
            "workspace_sha": file_sha(args.workspace_obj.path),
            "profile": report["profile"],
            "scope": args.scope,
            "token_kind": report.get("token_kind"),
        })
        artifacts["asset_receipt"] = str(receipt_path)
    return (0 if ok else 1), result_envelope(
        "assets verify",
        ok,
        "ready" if ok else "blocked",
        artifacts=artifacts,
        data=report,
        error=None if ok else {
            "kind": "asset_gate",
            "message": f"failed asset checks: {report['failed_checks']}",
        },
        next_action=("Run doctor for this profile." if ok else
                     "Fix the failed asset relationships or empty product sets, then retry."),
    )


def command_assets_products(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if not args.workspace_obj:
        raise MetaOpsError("assets products requires --workspace")
    if args.limit <= 0 or args.limit > 1000:
        raise MetaOpsError("assets products --limit must be between 1 and 1000")
    report = asset_graph.list_catalog_products(args.workspace_obj, args.profile, args.limit)
    return 0, result_envelope(
        "assets products",
        True,
        "listed",
        artifacts={"workspace": str(args.workspace_obj.path)},
        data=report,
        next_action="Use assets set-products with retailer_id values to repair a declared set.",
    )


def command_assets_set_products(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if not args.workspace_obj:
        raise MetaOpsError("assets set-products requires --workspace")
    if args.confirm != "SET":
        raise MetaOpsError("assets set-products requires the literal --confirm SET")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    product_sets = profile.get("product_sets") or {}
    if args.set not in product_sets:
        raise MetaOpsError(
            f"unknown product-set alias {args.set!r}; declared: {sorted(product_sets)}"
        )
    ids = [value.strip() for value in args.retailer_ids.split(",") if value.strip()]
    if not ids:
        raise MetaOpsError("--retailer-ids must contain at least one retailer id")
    require_assets(args.workspace_obj, profile_name, False)
    require_doctor(
        {
            "account_id": profile["ad_account_id"],
            "page_id": profile["page_id"],
            "pixel_id": profile["dataset_id"],
        },
        business_id=str(profile["business_id"]),
    )
    binding = asset_graph.verify_product_set_binding(
        args.workspace_obj, profile_name, args.set
    )
    if not binding["ready"]:
        raise MetaOpsError(
            f"product-set repair binding failed: {binding['checks']}"
        )
    import swapgate
    verdict = swapgate.judge_set(str(product_sets[args.set]), swapgate.catalog_ads(profile["ad_account_id"]),
                                 check_texts=False)
    if verdict["waiting"] and not args.force:
        raise MetaOpsError(
            "assets set-products: an ad on this set is in review and would be reviewed on the NEW "
            f"products: {verdict['waiting']}. Wait, use assets swap --watch for a white->target "
            "swap, or --force if the new products are the ones meant for review."
        )
    child = run_child(
        "mutate_set.py",
        ["--set-id", str(product_sets[args.set]), "--retailer-ids", ",".join(ids)],
        args.timeout,
    )
    echo_child(child)
    if not child.ok:
        return child.returncode, child_failure("assets set-products", "mutation_failed", child)
    asset_receipt_path(profile_name, "all").unlink(missing_ok=True)
    return 0, result_envelope(
        "assets set-products",
        True,
        "updated",
        artifacts={"workspace": str(args.workspace_obj.path)},
        data={"profile": profile_name, "product_set": args.set, "items": len(ids)},
        next_action="Run assets verify --scope all and require a ready receipt before planning.",
    )


def parse_swap_map(spec: str, product_sets: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """`a1=T01,b1=T02` (one product per set) or `a1=T01+T05` (several products in one set,
    carousel/collection). The same alias twice is an error, not a silent overwrite."""
    pairs: list[tuple[str, list[str]]] = []
    for item in spec.split(","):
        alias, _, rids = item.strip().partition("=")
        ids = [r.strip() for r in rids.split("+") if r.strip()]
        if not alias or not ids:
            raise MetaOpsError(f"--map item {item!r} must be alias=retailer_id[+retailer_id...]")
        if alias not in product_sets:
            raise MetaOpsError(f"unknown product-set alias {alias!r}; declared: {sorted(product_sets)}")
        if any(alias == a for a, _ in pairs):
            raise MetaOpsError(f"--map names {alias!r} twice")
        pairs.append((alias, ids))
    return pairs


def swap_round(account: str, catalog_id: str, pairs: list[tuple[str, list[str]]],
               product_sets: dict[str, Any], args: argparse.Namespace,
               with_delivery: bool) -> list[dict[str, Any]]:
    """One gate pass: a verdict per set (ready / waiting / blocked / done). Sets are independent:
    one set's reject or review never holds another."""
    import swapgate
    ads = swapgate.catalog_ads(account)
    impressions = swapgate.lifetime_impressions(account) if with_delivery else {}
    out = []
    for alias, rids in pairs:
        set_id = str(product_sets[alias])
        v = swapgate.judge_set(set_id, ads, paused_ok=args.paused_ok, allow_message=args.allow_message,
                               revert=args.revert, n_items=len(rids))
        for a in v["ads"]:
            a["impressions"] = impressions.get(a["ad"])
        items, bad = swapgate.target_items(catalog_id, rids) if catalog_id else (
            [], ["profile has no catalog_id: cannot check the target items"])
        v["blockers"] += bad
        v["warnings"] += [i["warning"] for i in items if i.get("warning")]
        st = swapgate.set_state(set_id)
        v.update({"alias": alias, "targets": items, "retailer_ids": rids, "members": st["members"]})
        if sorted(st["members"]) == sorted(rids) and not bad:
            v["verdict"] = "done"  # already holds exactly the target: idempotent re-run
        elif v["blockers"]:
            v["verdict"] = "blocked"
        out.append(v)
    return out


def spec_swap_map(spec: dict[str, Any], product_sets: dict[str, Any]) -> tuple[str, list[str]]:
    """creative.swap_to (retailer id, or a list) on catalog ads -> the `--map` for assets swap.
    Returns (map, problems): a catalog ad without swap_to, or a set with no workspace alias."""
    by_id = {str(v): k for k, v in product_sets.items()}
    pairs: dict[str, list[str]] = {}
    problems: list[str] = []
    for aset in spec.get("adsets") or []:
        for ad in aset.get("ads") or []:
            c = ad.get("creative") or {}
            if not str(c.get("kind", "")).startswith("catalog"):
                continue
            target = c.get("swap_to")
            set_id = str(c.get("product_set_id") or "")
            if not target:
                problems.append(f"{ad.get('name')}: catalog ad without creative.swap_to (white keeps spending "
                                "until someone swaps it by hand)")
                continue
            alias = by_id.get(set_id)
            if not alias:
                problems.append(f"{ad.get('name')}: product set {set_id} has no alias in workspace product_sets")
                continue
            rids = [target] if isinstance(target, str) else [str(t) for t in target]
            if pairs.get(alias, rids) != rids:
                problems.append(f"set alias {alias}: two ads ask for different swap_to {pairs[alias]} vs {rids}")
            pairs[alias] = rids
    return ",".join(f"{a}={'+'.join(r)}" for a, r in pairs.items()), problems


def command_assets_swap(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """White->target swap of product sets, per set, the moment that set's ads are approved
    (operator 2026-09-26: never wait for first delivery). --watch keeps polling review and swaps each
    set as soon as it turns ready; --dry-run only prints the verdicts."""
    import time as _time
    if not args.workspace_obj:
        raise MetaOpsError("assets swap requires --workspace")
    if args.confirm != "SWAP":
        raise MetaOpsError("assets swap requires the literal --confirm SWAP")
    if args.watch and args.dry_run:
        raise MetaOpsError("--watch and --dry-run are exclusive")
    if args.watch and args.revert:
        raise MetaOpsError("--revert never waits for review; drop --watch")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    product_sets = profile.get("product_sets") or {}
    pairs = parse_swap_map(args.map, product_sets)
    account = profile["ad_account_id"]
    catalog_id = str(profile.get("catalog_id") or "")
    deadline = _time.monotonic() + args.max_wait
    swapped: list[dict[str, Any]] = []
    final: dict[str, dict[str, Any]] = {}  # alias -> latest verdict, across --watch rounds
    pending = list(pairs)
    while True:
        try:
            verdicts = swap_round(account, catalog_id, pending, product_sets, args, with_delivery=args.dry_run)
        except graph.GraphError as exc:
            # A long --watch must survive a network blip or a transient Graph error; auth or
            # permission errors (token died, account gone) stop it: polling cannot fix them.
            if not args.watch or not (exc.is_transient or exc.code in (-1, 1, 2, 4, 17, 32, 613)) \
                    or _time.monotonic() >= deadline:
                raise
            print(f"  {now_utc()} read failed ({exc.code}), retrying in {args.interval}s", file=sys.stderr)
            _time.sleep(args.interval)
            continue
        if args.dry_run:
            return 0, result_envelope("assets swap", True, "dry_run", data={"sets": verdicts})
        for v in verdicts:
            if v["verdict"] != "ready":
                continue
            child = run_child("mutate_set.py", ["--set-id", v["set"], "--retailer-ids", ",".join(v["retailer_ids"])],
                              args.timeout)
            echo_child(child)
            if not child.ok:
                return child.returncode, child_failure("assets swap", "mutation_failed", child)
            v["verdict"] = "swapped"
            v["swapped_at"] = now_utc()
            swapped.append({"set": v["alias"], "retailer_ids": v["retailer_ids"], "at": v["swapped_at"]})
            print(f"  swapped {v['alias']} -> {'+'.join(v['retailer_ids'])}", file=sys.stderr)
        swapped += [{"set": v["alias"], "retailer_ids": v["retailer_ids"], "already": True}
                    for v in verdicts if v["verdict"] == "done"]
        final.update({v["alias"]: v for v in verdicts})
        waiting = [v for v in final.values() if v["verdict"] == "waiting"]
        blocked = [v for v in final.values() if v["verdict"] == "blocked"]
        if swapped:
            asset_receipt_path(profile_name, "all").unlink(missing_ok=True)
        if not args.watch or not waiting or _time.monotonic() >= deadline:
            break
        pending = [(v["alias"], v["retailer_ids"]) for v in waiting]
        print(f"  {now_utc()} waiting on {[v['alias'] for v in waiting]}: "
              f"{[w for v in waiting for w in v['waiting']][:4]}", file=sys.stderr)
        _time.sleep(args.interval)
    data = {"swapped": swapped, "sets": list(final.values())}
    if blocked:
        return 1, result_envelope("assets swap", False, "gate_blocked", data=data,
                                  error={"kind": "gate", "message": "; ".join(b for v in blocked for b in v["blockers"])},
                                  next_action="Fix the named blockers (texts need a NEW ad; target items need texts).")
    if waiting:
        return 2, result_envelope("assets swap", False, "waiting_review", data=data,
                                  error={"kind": "review", "message": "; ".join(w for v in waiting for w in v["waiting"])},
                                  next_action="Re-run with --watch (polls review, swaps each set on approval).")
    return 0, result_envelope("assets swap", True, "swapped", data=data,
                              next_action="Read back each set's products and every ad's effective_status "
                                          "in 15-60 min (render lag).")


REVIEW_STATUSES = {"PENDING_REVIEW", "IN_PROCESS", "PREAPPROVED"}


def feed_binding(args: argparse.Namespace) -> tuple[str, dict[str, Any], str]:
    if not args.workspace_obj:
        raise MetaOpsError("feed commands require --workspace")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    declared_feed_id = str(profile.get("feed_id") or "")
    if args.feed_id and declared_feed_id and str(args.feed_id) != declared_feed_id:
        raise MetaOpsError(
            "--feed-id does not match profiles.<p>.feed_id; select the profile that owns this feed"
        )
    feed_id = declared_feed_id or args.feed_id
    if not feed_id:
        raise MetaOpsError("no feed id: pass --feed-id or set profiles.<p>.feed_id in workspace.json")
    if not str(feed_id).isdigit():
        raise MetaOpsError("feed id must be numeric")
    return profile_name, profile, str(feed_id)


def feed_source_url(args: argparse.Namespace) -> str:
    if args.url:
        return args.url
    if not args.sheet:
        raise MetaOpsError("pass --url or --sheet (CSV export of the sheet tab is derived)")
    import sheetfeed
    gid = args.gid
    if gid is None:
        try:
            gid = sheetfeed.Sheet(args.sheet, args.tab).meta()["gid"]
        except sheetfeed.SheetError as exc:
            raise MetaOpsError(f"cannot resolve tab gid ({exc}); pass --gid") from exc
    return sheetfeed.csv_export_url(args.sheet, gid)


def ad_statuses(account: str) -> dict[str, str]:
    out: dict[str, str] = {}
    path = f"{account}/ads"
    params: dict[str, Any] = {"fields": "id,effective_status", "limit": 500}
    while True:
        resp = graph.get(path, params=params, context="ads status")
        for ad in resp.get("data", []):
            out[str(ad["id"])] = ad.get("effective_status", "?")
        params = graph.next_page_params(resp, params)
        if params is None:
            return out


def run_feed_upload(args: argparse.Namespace, feed_id: str, url: str) -> tuple[ChildResult, dict[str, Any]]:
    child_args = ["--feed-id", feed_id, "--url", url, "--wait", str(args.wait), "--errors"]
    if args.update_only:
        child_args.append("--update-only")
    child = run_child("feed_upload.py", child_args, args.timeout)
    echo_child(child)
    upload: dict[str, Any] = {}
    for line in (child.stdout or "").splitlines():
        line = line.strip()
        if line.startswith("{"):
            with contextlib.suppress(ValueError):
                upload = json.loads(line)
    return child, upload


def command_feed_sync(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    profile_name, profile, feed_id = feed_binding(args)
    if args.confirm != "FEED":
        raise MetaOpsError("feed sync changes catalog data: pass the literal --confirm FEED")
    url = feed_source_url(args)
    child, upload = run_feed_upload(args, feed_id, url)
    if not child.ok:
        return child.returncode, child_failure("feed sync", "upload_failed", child)
    return 0, result_envelope(
        "feed sync", True, "fetched",
        artifacts={"workspace": str(args.workspace_obj.path)},
        data={"profile": profile_name, "feed_id": feed_id, "url": url, "upload": upload},
        next_action="Check num_invalid_items; then metaops assets verify --scope all if product sets changed.",
    )


def command_feed_swap(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Sheet upsert → immediate fetch → prove no ad re-entered review (swap gate, 04)."""
    import sheetfeed
    profile_name, profile, feed_id = feed_binding(args)
    if args.confirm != "FEED":
        raise MetaOpsError("feed swap changes catalog data: pass the literal --confirm FEED")
    if not args.sheet:
        raise MetaOpsError("feed swap requires --sheet")
    items = sheetfeed.load_items(args.file)
    if not items:
        raise MetaOpsError(f"{args.file}: no items")
    account = profile["ad_account_id"]
    before = ad_statuses(account)
    import swapgate
    rids = [str(i.get("id") or i.get("retailer_id")) for i in items if i.get("id") or i.get("retailer_id")]
    gate = swapgate.item_gate(account, rids, paused_ok=getattr(args, "paused_ok", False))
    if gate["verdict"] != "ready" and not args.force:
        raise MetaOpsError(
            f"swap gate: {gate['verdict']}: {(gate['waiting'] + gate['blockers'])[:5]}. Only ads whose sets "
            "show these rows count (other ads never hold it). Swap the moment they are approved "
            "(no delivery wait), or --force."
        )
    sheet = sheetfeed.Sheet(args.sheet, args.tab)
    header, rows = sheet.read()
    if not header:
        raise MetaOpsError("sheet tab has no header row; run sheetfeed init-header first")
    prospective_header, prospective_rows = sheetfeed.merged_upsert_rows(header, rows, items)
    problems = sheetfeed.validate_rows(prospective_header, prospective_rows, "meta")
    if problems:
        return 1, result_envelope(
            "feed swap", False, "sheet_invalid",
            data={"problems": problems},
            error={"kind": "validation", "message": f"{len(problems)} prospective row problem(s)"},
            next_action="Fix the input rows, then retry feed swap; the sheet was not changed.",
        )
    counts = sheet.upsert(items, header, rows)
    url = feed_source_url(args)
    child, upload = run_feed_upload(args, feed_id, url)
    if not child.ok:
        return child.returncode, child_failure("feed swap", "upload_failed", child)
    after = ad_statuses(account)
    re_review = sorted(ad for ad, st in after.items() if st in REVIEW_STATUSES and before.get(ad) not in REVIEW_STATUSES)
    return (1 if re_review else 0), result_envelope(
        "feed swap", not re_review, "swapped" if not re_review else "re_review",
        artifacts={"workspace": str(args.workspace_obj.path)},
        data={"profile": profile_name, "feed_id": feed_id, "sheet": counts, "upload": upload,
              "ads_checked": len(after), "ads_re_review": re_review},
        next_action=(None if not re_review else
                     "Ads re-entered review after the swap; do not touch them, watch for REJECTS (monitor.py)."),
    )


def command_media(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if not args.image and not args.video:
        raise MetaOpsError("media requires at least one --image or --video path")
    profile_name, profile = args.workspace_obj.profile(args.profile)
    require_assets(args.workspace_obj, profile_name, False)
    require_doctor(
        {
            "account_id": profile["ad_account_id"],
            "page_id": profile["page_id"],
            "pixel_id": profile["dataset_id"],
        },
        business_id=str(profile["business_id"]),
    )
    manifest = (
        resolve_input(args.manifest)
        if args.manifest
        else (args.workspace_obj.state_root / "media" / f"{profile_name}.json").resolve()
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    child_args = ["--account", profile["ad_account_id"], "--manifest", str(manifest)]
    if args.image:
        child_args += ["--image", *[str(resolve_input(path)) for path in args.image]]
    if args.video:
        child_args += ["--video", *[str(resolve_input(path)) for path in args.video]]
    child = run_child("media.py", child_args, args.timeout)
    echo_child(child)
    if not child.ok:
        return child.returncode, child_failure("media", "upload_failed", child)
    if not manifest.is_file():
        raise MetaOpsError(f"media.py succeeded without writing its manifest: {manifest}")
    return 0, result_envelope(
        "media",
        True,
        "uploaded",
        artifacts={"manifest": str(manifest)},
        data={"profile": profile_name, "account_id": profile["ad_account_id"]},
        next_action="Copy the returned image_hash/video_id values into the campaign spec.",
    )


def command_apply(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.confirm != "SPEND":
        raise MetaOpsError(
            "apply creates objects ACTIVE by default and spends the moment the create "
            "succeeds (a spec-level create_status: PAUSED keeps the old paused build) — "
            "refusing without the literal --confirm SPEND"
        )
    plan_path, plan = load_plan(args.plan, {SINGLE_PLAN_SCHEMA})
    spec_path, state_path = validate_single_plan(plan, args.workspace_obj, args.profile)
    with state_lock(state_path), state_lock(spec_path):
        spec_path, state_path = validate_single_plan(plan, args.workspace_obj, args.profile)
        refresh = getattr(args, "refresh_start", None)
        if refresh:
            validate_future_start(refresh)
        else:
            blocker = _active_start_blocker(spec_path)
            if blocker:
                raise MetaOpsError(f"refusing ACTIVE apply: {blocker} "
                                   "(resuming a partial build? pass --refresh-start)")
        if state_path.exists():
            require_state_binding(plan, state_path)
        launch_args = ["--spec", str(spec_path), "--state", str(state_path)]
        if refresh:
            launch_args += ["--start-override", refresh]
        child = run_child("launch.py", launch_args, args.timeout)
    echo_child(child)
    if not child.ok:
        phase = "reconcile_required" if state_summary(state_path).get("in_flight") else "apply_failed"
        out = child_failure("apply", phase, child)
        out["artifacts"] = {"plan": str(plan_path), "state": str(state_path)}
        return child.returncode, out
    summary = state_summary(state_path, spec_path)
    next_action = f"Run: metaops.py verify --plan {plan_path}"
    try:
        _, profile = args.workspace_obj.profile(args.profile)
        swap_map, swap_problems = spec_swap_map(read_json(spec_path, "spec"), profile.get("product_sets") or {})
    except Exception:  # noqa: BLE001 - advisory only, never fail a finished build on it
        swap_map, swap_problems = "", []
    if swap_map:
        next_action += (f"; then START NOW in background (white must not spend): metaops --workspace . "
                        f"--profile {args.profile} --json assets swap --map {swap_map} --watch --confirm SWAP")
        summary["swap_map"] = swap_map
    if swap_problems:
        summary["swap_problems"] = swap_problems
        next_action += f"; swap not planned for: {swap_problems}"
    return 0, result_envelope(
        "apply",
        True,
        "built",
        artifacts={"plan": str(plan_path), "state": str(state_path)},
        data=summary,
        next_action=next_action,
    )


def command_verify(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    plan_path, plan = load_plan(args.plan, {SINGLE_PLAN_SCHEMA})
    spec_path, state_path = validate_single_plan(plan, args.workspace_obj, args.profile)
    if not state_path.exists():
        raise MetaOpsError(f"state does not exist: {state_path}; apply the plan first")
    with state_lock(state_path), state_lock(spec_path):
        spec_path, state_path = validate_single_plan(plan, args.workspace_obj, args.profile)
        require_state_binding(plan, state_path)
        child = run_child(
            "verify.py", ["--state", str(state_path), "--spec", str(spec_path)], args.timeout
        )
    echo_child(child)
    if not child.ok:
        out = child_failure("verify", "verification_failed", child)
        out["artifacts"] = {"plan": str(plan_path), "state": str(state_path)}
        return child.returncode, out
    summary = state_summary(state_path, spec_path)
    return 0, result_envelope(
        "verify",
        True,
        "verified",
        artifacts={"plan": str(plan_path), "state": str(state_path),
                   "receipt": summary.get("receipt")},
        data=summary,
        next_action="Complete the required UI placement/multi-advertiser checks, then activate explicitly.",
    )


def command_activate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    plan_path, plan = load_plan(args.plan, {SINGLE_PLAN_SCHEMA})
    spec_path, state_path = validate_single_plan(plan, args.workspace_obj, args.profile)
    if args.confirm != "SPEND":
        raise MetaOpsError("activation requires the literal --confirm SPEND")
    if args.confirm_ui != "REVIEWED":
        raise MetaOpsError("activation requires --confirm-ui REVIEWED after the UI-only checks")
    child_args = ["--state", str(state_path), "--confirm", "SPEND"]
    if args.refresh_start:
        validate_future_start(args.refresh_start)
        child_args += ["--refresh-start", args.refresh_start]
    with state_lock(state_path), state_lock(spec_path):
        spec_path, state_path = validate_single_plan(plan, args.workspace_obj, args.profile)
        if not args.refresh_start:
            spec = load_launch_spec(spec_path)
            starts = [
                dt.datetime.fromisoformat(str(aset["start_time"]).replace("Z", "+00:00"))
                for aset in spec["adsets"]
            ]
            if any(
                start.tzinfo is None
                or start.astimezone(dt.timezone.utc) <= dt.datetime.now(dt.timezone.utc)
                for start in starts
            ):
                raise MetaOpsError(
                    "an ad-set start_time is past or lacks an offset; pass a future --refresh-start"
                )
        require_state_binding(plan, state_path)
        child = run_child("activate.py", child_args, args.timeout)
    echo_child(child)
    if not child.ok:
        out = child_failure("activate", "activation_failed", child)
        out["artifacts"] = {"plan": str(plan_path), "state": str(state_path)}
        return child.returncode, out
    return 0, result_envelope(
        "activate",
        True,
        "activated",
        artifacts={"plan": str(plan_path), "state": str(state_path)},
        next_action="Read effective_status, spend, billing, destination, and tracker receipt within the hour.",
    )


def command_status(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    plan_path, plan = load_plan(args.plan)
    if plan["schema"] == SINGLE_PLAN_SCHEMA:
        spec_path, state_path = validate_single_plan(plan, args.workspace_obj, args.profile)
        if state_path.exists():
            require_state_binding(plan, state_path)
        summary = state_summary(state_path, spec_path)
        return 0, result_envelope(
            "status", True, summary["phase"], artifacts={"plan": str(plan_path),
                                                          "state": str(state_path)}, data=summary
        )
    validate_bulk_plan(plan, args.workspace_obj)
    validate_bulk_items(plan)
    items = []
    for item in plan.get("items") or []:
        state_path = resolve_input(item["state_path"])
        items.append({**item, "status": state_summary(state_path, resolve_input(item["spec_path"]))})
    phase = "verified" if items and all(i["status"]["activation_ready"] for i in items) else "built"
    if any(i["status"]["in_flight"] for i in items):
        phase = "reconcile_required"
    return 0, result_envelope(
        "status", True, phase, artifacts={"plan": str(plan_path)}, data={"items": items}
    )


def normalize_only(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {graph.normalize_account(v) for v in value.split(",") if v.strip()}


def validated_bulk_rows(rows: Any, only: set[str] | None, run_id: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise MetaOpsError("accounts JSON must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    seen_accounts: set[str] = set()
    seen_tags: set[str] = set()
    routing_keys = {"account_id", "page_id", "pixel_id", "instagram_user_id", "run_id"}
    # create_status decides whether a tree spends on create; the plan's apply_effect and the
    # bulk messages are computed once from the template, so a row must not flip it.
    batch_keys = {"create_status"}
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise MetaOpsError(f"accounts[{index}] must be an object")
        account = graph.normalize_account(str(raw.get("account_id") or ""))
        if not re.fullmatch(r"act_[0-9]+", account):
            raise MetaOpsError(f"accounts[{index}].account_id must be a numeric Meta ad account id")
        tag = safe_name(str(raw.get("tag") or account.removeprefix("act_")),
                        f"accounts[{index}].tag")
        safe_name(f"{run_id}-{tag}", f"accounts[{index}] resolved run_id")
        overrides = raw.get("overrides") or {}
        if not isinstance(overrides, dict):
            raise MetaOpsError(f"accounts[{index}].overrides must be an object")
        forbidden = sorted(routing_keys & set(overrides))
        if forbidden:
            raise MetaOpsError(
                f"accounts[{index}].overrides cannot change routing keys: {forbidden}"
            )
        if batch_keys & set(overrides):
            raise MetaOpsError(
                f"accounts[{index}].overrides cannot set create_status; it is batch-wide — "
                "set it once at template top level"
            )
        if account in seen_accounts:
            raise MetaOpsError(f"duplicate account_id in accounts JSON: {account}")
        if tag in seen_tags:
            raise MetaOpsError(f"duplicate tag in accounts JSON: {tag}")
        seen_accounts.add(account)
        seen_tags.add(tag)
        row = json.loads(json.dumps(raw))
        row["account_id"] = account
        row["tag"] = tag
        normalized.append(row)
    if only and not (only & seen_accounts):
        raise MetaOpsError(f"--only matched none of the accounts JSON rows: {sorted(only)}")
    return normalized


def workspace_bulk_rows(
    workspace: meta_workspace.Workspace,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_account: dict[str, tuple[str, dict[str, Any]]] = {}
    for name in workspace.data["profiles"]:
        profile_name, profile = workspace.profile(name)
        by_account[graph.normalize_account(profile["ad_account_id"])] = (profile_name, profile)
    routed: list[dict[str, Any]] = []
    for row in rows:
        account = row["account_id"]
        if account not in by_account:
            raise MetaOpsError(f"bulk account {account} is not an allowed workspace profile")
        profile_name, profile = by_account[account]
        resolved = json.loads(json.dumps(row))
        for row_key, profile_key in (
            ("page_id", "page_id"),
            ("pixel_id", "dataset_id"),
            ("instagram_user_id", "instagram_user_id"),
        ):
            supplied = resolved.get(row_key)
            expected = profile.get(profile_key)
            if supplied is not None and str(supplied) != str(expected):
                raise MetaOpsError(
                    f"bulk {account} {row_key} conflicts with workspace profile {profile_name}"
                )
            if expected is not None:
                resolved[row_key] = expected
        resolved["workspace_profile"] = profile_name
        routed.append(resolved)
    return routed


def workspace_bulk_candidate(
    template: dict[str, Any],
    row: dict[str, Any],
) -> dict[str, Any]:
    candidate = json.loads(json.dumps(template))
    for key in ("account_id", "page_id", "pixel_id", "instagram_user_id"):
        if key in row:
            candidate[key] = row[key]
    if row.get("overrides"):
        candidate = bulk.deep_merge(candidate, row["overrides"])
    if row.get("media"):
        candidate = bulk.apply_media(candidate, row["media"])
    return candidate


def validate_workspace_bulk_specs(
    workspace: meta_workspace.Workspace,
    template: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        candidate = workspace_bulk_candidate(template, row)
        if any(
            "product_set" in (ad.get("creative") or {})
            for adset in candidate.get("adsets") or []
            for ad in adset.get("ads") or []
        ):
            raise MetaOpsError(
                "workspace bulk requires declared product_set_id values; aliases are single-plan only"
            )
        meta_workspace.resolve_spec(candidate, workspace, row["workspace_profile"])


def build_bulk_plan(template_path: pathlib.Path, accounts_path: pathlib.Path,
                    run_arg: str | None, only_arg: str | None,
                    workspace: meta_workspace.Workspace | None = None) -> dict[str, Any]:
    template = read_json(template_path, "template")
    rows = read_json(accounts_path, "accounts")
    run_id = safe_name(run_arg or template_path.stem, "bulk run")
    only = normalize_only(only_arg)
    rows = validated_bulk_rows(rows, only, run_id)
    if workspace:
        rows = workspace_bulk_rows(workspace, rows)
        validate_workspace_bulk_specs(workspace, template, rows)
    inputs_sha = bulk.inputs_hash(template, rows, only)
    template_snapshot = (PLAN_DIR / f"bulk-{run_id}.{inputs_sha}.template.json").resolve()
    accounts_snapshot = (PLAN_DIR / f"bulk-{run_id}.{inputs_sha}.accounts.json").resolve()
    plan = {
        "schema": BULK_PLAN_SCHEMA,
        "created_at": now_utc(),
        "api_version": graph.API_VERSION,
        "kind": "bulk",
        "run_id": run_id,
        "source_template_path": str(template_path),
        "source_accounts_path": str(accounts_path),
        "template_path": str(template_snapshot),
        "accounts_path": str(accounts_snapshot),
        "only": sorted(only) if only else None,
        "inputs_sha": inputs_sha,
        "validation_scope": {
            "api": ["campaigns", "creatives"],
            "local_only_until_apply": ["campaign budget patches", "ad_sets", "ads"],
        },
        "apply_effect": (
            "Creates or resumes every selected tree PAUSED. Never activates."
            if template.get("create_status", "ACTIVE") == "PAUSED"
            else "Creates or resumes every selected tree ACTIVE. bulk-apply requires "
                 "--confirm SPEND and spends immediately on success."
        ),
        "items": [],
    }
    if workspace:
        plan["workspace_path"] = str(workspace.path)
        plan["workspace_sha"] = file_sha(workspace.path)
    return plan


def bulk_plan_path(plan: dict[str, Any], requested: str | None) -> pathlib.Path:
    if requested:
        return resolve_input(requested)
    return PLAN_DIR / f"bulk-{plan['run_id']}.{plan['inputs_sha']}.plan.json"


def validate_bulk_plan(
    plan: dict[str, Any],
    current_workspace: meta_workspace.Workspace | None = None,
    receipt_accounts: set[str] | None = None,
) -> tuple[pathlib.Path, pathlib.Path]:
    template_path = resolve_input(plan["template_path"])
    accounts_path = resolve_input(plan["accounts_path"])
    template = read_json(template_path, "template")
    rows = read_json(accounts_path, "accounts")
    only = set(plan["only"]) if plan.get("only") else None
    current = bulk.inputs_hash(template, rows, only)
    if current != plan.get("inputs_sha"):
        raise MetaOpsError(
            f"template/accounts changed after plan ({plan.get('inputs_sha')} != {current}); re-plan"
        )
    if current_workspace is None:
        raise MetaOpsError("a workspace is required for every saved bulk plan")
    if not plan.get("workspace_path") or not plan.get("workspace_sha"):
        raise MetaOpsError("legacy workspace-free bulk plan is not executable; create a new plan")
    if resolve_input(str(plan["workspace_path"])) != current_workspace.path:
        raise MetaOpsError("current workspace does not match the workspace bound to this bulk plan")
    if file_sha(current_workspace.path) != plan.get("workspace_sha"):
        raise MetaOpsError("workspace changed after bulk-plan; re-plan")
    workspace = current_workspace
    rows = workspace_bulk_rows(workspace, rows)
    receipts = plan.get("doctor_receipts")
    if not isinstance(receipts, list) or not receipts:
        raise MetaOpsError("bulk plan has no bound doctor receipts; run bulk-plan again")
    by_account = {binding.get("account_id"): binding for binding in receipts}
    selected_rows = [row for row in rows if not only or row["account_id"] in only]
    if set(by_account) != {row["account_id"] for row in selected_rows}:
        raise MetaOpsError("bulk doctor receipts do not match the selected accounts")
    if receipt_accounts is not None:
        normalized_receipt_accounts = {
            graph.normalize_account(account) for account in receipt_accounts
        }
        planned_accounts = {row["account_id"] for row in selected_rows}
        if not normalized_receipt_accounts or not normalized_receipt_accounts <= planned_accounts:
            raise MetaOpsError(
                f"receipt validation accounts are not in this bulk plan: "
                f"{sorted(normalized_receipt_accounts - planned_accounts)}"
            )
        receipt_rows = [
            row for row in selected_rows if row["account_id"] in normalized_receipt_accounts
        ]
    else:
        receipt_rows = selected_rows
    for row in receipt_rows:
        binding = by_account[row["account_id"]]
        routing = {
            key: row.get(key, template.get(key))
            for key in ("account_id", "page_id", "pixel_id")
        }
        _, profile = workspace.profile(row["workspace_profile"])
        receipt_path, receipt_sha = require_doctor(
            routing, binding["path"], str(profile["business_id"])
        )
        if receipt_sha != binding.get("sha"):
            raise MetaOpsError(f"doctor receipt changed after bulk-plan: {receipt_path}")
    if workspace:
        asset_bindings = plan.get("asset_receipts") or []
        by_profile = {binding.get("profile"): binding for binding in asset_bindings}
        for profile_name in {row["workspace_profile"] for row in receipt_rows}:
            binding = by_profile.get(profile_name)
            if not binding:
                raise MetaOpsError(f"bulk plan has no asset receipt for profile {profile_name}")
            receipt_path, receipt_sha = validate_asset_receipt(
                resolve_input(binding["path"]), workspace, profile_name,
                bool(binding.get("catalog_required")),
            )
            if receipt_sha != binding.get("sha"):
                raise MetaOpsError(f"asset receipt changed after bulk-plan: {receipt_path}")
    return template_path, accounts_path


def bind_bulk_doctors(
    plan: dict[str, Any],
    template: dict[str, Any],
    rows: list[dict[str, Any]],
    workspace: meta_workspace.Workspace,
) -> list[dict[str, str]]:
    selected = set(plan["only"]) if plan.get("only") else None
    bindings: list[dict[str, str]] = []
    for row in rows:
        if selected and row["account_id"] not in selected:
            continue
        routing = {
            key: row.get(key, template.get(key))
            for key in ("account_id", "page_id", "pixel_id")
        }
        _, profile = workspace.profile(row["workspace_profile"])
        receipt_path, receipt_sha = require_doctor(
            routing, business_id=str(profile["business_id"])
        )
        bindings.append({"account_id": row["account_id"],
                         "path": str(receipt_path), "sha": receipt_sha})
    return bindings


def bind_bulk_assets(
    workspace: meta_workspace.Workspace,
    template: dict[str, Any],
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    profiles = sorted({row["workspace_profile"] for row in rows})
    bindings: list[dict[str, Any]] = []
    for profile_name in profiles:
        catalog_required = any(
            row["workspace_profile"] == profile_name
            and requires_catalog(workspace_bulk_candidate(template, row))
            for row in rows
        )
        path, sha = require_assets(workspace, profile_name, catalog_required)
        bindings.append({
            "profile": profile_name,
            "path": str(path),
            "sha": sha,
            "catalog_required": catalog_required,
        })
    return bindings


def expected_bulk_state_paths(plan: dict[str, Any]) -> list[pathlib.Path]:
    rows = read_json(resolve_input(plan["accounts_path"]), "accounts snapshot")
    selected = set(plan["only"]) if plan.get("only") else None
    paths: list[pathlib.Path] = []
    for row in rows:
        if selected and row["account_id"] not in selected:
            continue
        run_id = safe_name(f"{plan['run_id']}-{row['tag']}", "resolved bulk run_id")
        paths.append((HERE / launch.STATE_DIR / f"{run_id}.json").resolve())
    return sorted(paths)


def validate_bulk_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    expected_states = {str(path) for path in expected_bulk_state_paths(plan)}
    items = plan.get("items")
    if not isinstance(items, list) or not items:
        raise MetaOpsError("bulk plan contains no resolved items; run bulk-plan again")
    actual_states: set[str] = set()
    for item in items:
        spec_path = resolve_input(item["spec_path"])
        spec = load_launch_spec(spec_path)
        if launch.spec_hash(spec) != item.get("spec_sha"):
            raise MetaOpsError(f"resolved bulk spec changed after plan: {spec_path}")
        if spec.get("account_id") != item.get("account_id") or spec.get("run_id") != item.get("run_id"):
            raise MetaOpsError(f"resolved bulk item identity mismatch: {spec_path}")
        actual_states.add(str(resolve_input(item["state_path"])))
    if actual_states != expected_states:
        raise MetaOpsError("bulk item state paths do not match the bound accounts snapshot")
    return items


def bulk_args(plan: dict[str, Any], template_path: pathlib.Path,
              accounts_path: pathlib.Path) -> list[str]:
    out = ["--template", str(template_path), "--accounts", str(accounts_path),
           "--run", plan["run_id"]]
    if plan.get("only"):
        out += ["--only", ",".join(plan["only"])]
    return out


def discover_bulk_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    root = (HERE / bulk.BULK_DIR / plan["run_id"]).resolve()
    expected_states = {str(path) for path in expected_bulk_state_paths(plan)}
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            spec = launch.load_spec(str(path))
        except (SystemExit, OSError, json.JSONDecodeError):
            continue
        state_path = str((HERE / launch.STATE_DIR / f"{spec['run_id']}.json").resolve())
        if state_path not in expected_states:
            continue
        items.append({
            "account_id": spec["account_id"],
            "run_id": spec["run_id"],
            "spec_path": str(path.resolve()),
            "spec_sha": launch.spec_hash(spec),
            "state_path": state_path,
        })
    return items


def command_bulk_plan(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    template_path, accounts_path = resolve_input(args.template), resolve_input(args.accounts)
    plan = build_bulk_plan(
        template_path, accounts_path, args.run, args.only, args.workspace_obj
    )
    plan_path = bulk_plan_path(plan, args.out)
    template = read_json(template_path, "template")
    rows = validated_bulk_rows(read_json(accounts_path, "accounts"),
                               set(plan["only"]) if plan.get("only") else None, plan["run_id"])
    if args.workspace_obj:
        rows = workspace_bulk_rows(args.workspace_obj, rows)
        validate_workspace_bulk_specs(args.workspace_obj, template, rows)
    template_snapshot = resolve_input(plan["template_path"])
    accounts_snapshot = resolve_input(plan["accounts_path"])
    atomic_json(template_snapshot, template)
    atomic_json(accounts_snapshot, rows)
    plan["doctor_receipts"] = bind_bulk_doctors(
        plan, template, rows, args.workspace_obj
    )
    if args.workspace_obj:
        plan["asset_receipts"] = bind_bulk_assets(args.workspace_obj, template, rows)
    child_args = bulk_args(plan, template_snapshot, accounts_snapshot) + ["--dry-run"]
    child = run_child("bulk.py", child_args, args.timeout)
    echo_child(child)
    if not child.ok:
        return child.returncode, child_failure("bulk-plan", "validation_failed", child)
    plan["items"] = discover_bulk_items(plan)
    validate_bulk_items(plan)
    atomic_json(plan_path, plan)
    return 0, result_envelope(
        "bulk-plan", True, "validated", artifacts={"plan": str(plan_path)},
        data={"run_id": plan["run_id"], "inputs_sha": plan["inputs_sha"],
              "items": plan["items"], "validation_scope": plan["validation_scope"]},
        next_action=f"Review the plan, then run: metaops.py bulk-apply --plan {plan_path}",
    )


def command_bulk_apply(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    if args.confirm != "SPEND":
        raise MetaOpsError(
            "bulk-apply creates objects ACTIVE by default and spends the moment each create "
            "succeeds (a template-level create_status: PAUSED keeps the old paused build) — "
            "refusing without the literal --confirm SPEND"
        )
    plan_path, plan = load_plan(args.plan, {BULK_PLAN_SCHEMA})
    template_path, accounts_path = validate_bulk_plan(plan, args.workspace_obj)
    child_args = bulk_args(plan, template_path, accounts_path)
    if args.verify:
        child_args.append("--verify")
    if args.dlo_tested:
        child_args.append("--dlo-tested")
    batch_lock = (HERE / bulk.BULK_DIR / plan["run_id"] / ".metaops-batch").resolve()
    validate_bulk_items(plan)
    state_paths = expected_bulk_state_paths(plan)
    item_by_state = {str(resolve_input(item["state_path"])): item for item in plan["items"]}
    with contextlib.ExitStack() as stack:
        stack.enter_context(state_lock(batch_lock))
        stack.enter_context(state_lock(template_path))
        stack.enter_context(state_lock(accounts_path))
        for state_path in state_paths:
            stack.enter_context(state_lock(state_path))
            if state_path.exists():
                item = item_by_state[str(state_path)]
                require_state_binding(
                    {"spec_sha": item["spec_sha"], "account_id": item["account_id"]},
                    state_path,
                )
        template_path, accounts_path = validate_bulk_plan(plan, args.workspace_obj)
        for item in validate_bulk_items(plan):
            blocker = _active_start_blocker(resolve_input(item["spec_path"]))
            if blocker:
                raise MetaOpsError(f"refusing ACTIVE bulk-apply for {item['account_id']}: {blocker}")
        child = run_child("bulk.py", child_args, args.timeout)
    echo_child(child)
    if not child.ok:
        out = child_failure("bulk-apply", "partial_failure", child)
        out["artifacts"] = {"plan": str(plan_path)}
        return child.returncode, out
    plan["items"] = discover_bulk_items(plan)
    validate_bulk_items(plan)
    atomic_json(plan_path, plan)
    return 0, result_envelope(
        "bulk-apply", True, "built", artifacts={"plan": str(plan_path)},
        data={"items": plan["items"], "verified": bool(args.verify)},
        next_action="Review status for each tree; activation remains per-tree and explicit.",
    )


def command_bulk_activate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    plan_path, plan = load_plan(args.plan, {BULK_PLAN_SCHEMA})
    account = graph.normalize_account(args.account)
    validate_bulk_plan(plan, args.workspace_obj, {account})
    items = validate_bulk_items(plan)
    selected = [item for item in items if item["account_id"] == account]
    if len(selected) != 1:
        raise MetaOpsError(f"bulk plan has no unique item for {account}")
    if args.confirm != "SPEND" or args.confirm_ui != "REVIEWED":
        raise MetaOpsError(
            "bulk activation requires --confirm-ui REVIEWED and literal --confirm SPEND"
        )
    item = selected[0]
    spec_path = resolve_input(item["spec_path"])
    state_path = resolve_input(item["state_path"])
    child_args = ["--state", str(state_path), "--confirm", "SPEND"]
    if args.refresh_start:
        validate_future_start(args.refresh_start)
        child_args += ["--refresh-start", args.refresh_start]
    with state_lock(state_path), state_lock(spec_path):
        validate_bulk_plan(plan, args.workspace_obj, {account})
        validate_bulk_items(plan)
        require_state_binding(
            {"spec_sha": item["spec_sha"], "account_id": item["account_id"]}, state_path
        )
        if not args.refresh_start:
            spec = load_launch_spec(spec_path)
            starts = [
                dt.datetime.fromisoformat(str(adset["start_time"]).replace("Z", "+00:00"))
                for adset in spec["adsets"]
            ]
            if any(
                start.tzinfo is None
                or start.astimezone(dt.timezone.utc) <= dt.datetime.now(dt.timezone.utc)
                for start in starts
            ):
                raise MetaOpsError(
                    "an ad-set start_time is past or lacks an offset; pass a future --refresh-start"
                )
        child = run_child("activate.py", child_args, args.timeout)
    echo_child(child)
    if not child.ok:
        out = child_failure("bulk-activate", "activation_failed", child)
        out["artifacts"] = {
            "plan": str(plan_path), "state": str(state_path), "spec": str(spec_path)
        }
        return child.returncode, out
    return 0, result_envelope(
        "bulk-activate",
        True,
        "activated",
        artifacts={"plan": str(plan_path), "state": str(state_path)},
        data={"account_id": account, "run_id": item["run_id"]},
        next_action="Read effective_status, spend, billing, destination, and tracker receipt.",
    )


class MetaOpsParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        if "--json" in sys.argv[1:]:
            command = next(
                (part for part in sys.argv[1:] if part in WORKSPACE_LIFECYCLE_COMMANDS | {
                    "doctor", "workspace", "assets",
                }),
                "parse",
            )
            payload = result_envelope(
                command, False, "launcher_error",
                error={"kind": "usage", "message": message},
            )
            print(json.dumps(payload, ensure_ascii=False))
            raise SystemExit(2)
        super().error(message)


def add_json_help(parser: argparse.ArgumentParser) -> None:
    parser.epilog = "Put --json before the subcommand for a stable machine-readable result."


def parser() -> argparse.ArgumentParser:
    ap = MetaOpsParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="one JSON result on stdout; diagnostics on stderr")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"child timeout in seconds (default {DEFAULT_TIMEOUT})")
    ap.add_argument(
        "--workspace",
        help="workspace directory/file; default METAOPS_WORKSPACE or nearest workspace.json",
    )
    ap.add_argument("--profile", help="workspace profile; defaults to workspace defaults.profile")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("workspace", help="validate the workspace manifest")
    workspace_sub = p.add_subparsers(dest="workspace_action", required=True)
    action = workspace_sub.add_parser("validate", help="validate workspace.json locally")
    action.set_defaults(handler=command_workspace_validate)

    p = sub.add_parser("assets", help="inspect the workspace asset graph")
    assets_sub = p.add_subparsers(dest="assets_action", required=True)
    action = assets_sub.add_parser("verify", help="read and verify every profile asset")
    action.add_argument(
        "--scope", choices=("core", "all"), default="all",
        help="core skips catalog/product sets; all is required for catalog launches",
    )
    action.set_defaults(handler=command_assets_verify)
    action = assets_sub.add_parser("products", help="list catalog product ids for set repair")
    action.add_argument("--limit", type=int, default=100)
    action.set_defaults(handler=command_assets_products)
    action = assets_sub.add_parser("set-products", help="replace a declared product-set filter")
    action.add_argument("--set", required=True, help="product-set alias from workspace profile")
    action.add_argument("--retailer-ids", required=True, help="comma-separated retailer ids")
    action.add_argument("--force", action="store_true",
                        help="mutate even while an ad on the set is in review (it is reviewed on the new products)")
    action.add_argument("--confirm", required=True, help="must be literal SET")
    action.set_defaults(handler=command_assets_set_products)
    action = assets_sub.add_parser("swap", help="white->target swap of product sets on approval, per set, gated")
    action.add_argument("--map", required=True,
                        help="alias=retailer_id[+retailer_id] pairs, e.g. a1=T01,b1=T02 or c1=T01+T02+T03")
    action.add_argument("--dry-run", action="store_true", help="show per-set verdicts, change nothing")
    action.add_argument("--watch", action="store_true",
                        help="poll review and swap each set the moment its ads are approved")
    action.add_argument("--interval", type=int, default=300, help="--watch poll seconds (default 300; pacing, FIELD 2026-09-27)")
    action.add_argument("--max-wait", type=int, default=12 * 3600, help="--watch give-up seconds (default 12 h)")
    action.add_argument("--paused-ok", action="store_true",
                        help="treat ADSET_PAUSED/CAMPAIGN_PAUSED ads as approved (you saw them ACTIVE); "
                             "an ad-level PAUSED already counts as reviewed")
    action.add_argument("--allow-message", action="store_true",
                        help="accept a non-neutral primary text (it stays after the swap)")
    action.add_argument("--revert", action="store_true",
                        help="target -> white (before a review request / creative edit): no review wait, no text gate")
    action.add_argument("--confirm", required=True, help="must be literal SWAP")
    action.set_defaults(handler=command_assets_swap)

    p = sub.add_parser("pace", help="local pacing state: throttle cooldowns, last campaign create per account")
    p.add_argument("--clear-cooldown", metavar="ACT_ID", help="drop one cooldown (only when the operator asks)")
    p.set_defaults(handler=command_pace)

    p = sub.add_parser("doctor", help="token/account preflight through probe.py")
    p.add_argument(
        "--scope", choices=("core", "provisioning"), default="core",
        help="provisioning additionally proves the declared System User is currently ADMIN",
    )
    p.add_argument("--whoami", action="store_true")
    p.add_argument("--account")
    p.add_argument("--page")
    p.add_argument("--dataset")
    p.add_argument("--business")
    p.add_argument("--create-pbia", action="store_true")
    p.add_argument("--attach-pixel", action="store_true")
    p.set_defaults(handler=command_doctor)

    p = sub.add_parser("media", help="upload profile-scoped images/videos and write a manifest")
    p.add_argument("--image", nargs="*", default=[])
    p.add_argument("--video", nargs="*", default=[])
    p.add_argument("--manifest", help="output path; default .metaops/media/<profile>.json")
    p.set_defaults(handler=command_media)

    p = sub.add_parser("feed", help="catalog feed: immediate fetch / sheet swap")
    feed_sub = p.add_subparsers(dest="feed_action", required=True)
    for name, handler, help_text in (
        ("sync", command_feed_sync, "POST /{feed_id}/uploads with the sheet CSV URL and wait"),
        ("swap", command_feed_swap, "upsert rows into the sheet, fetch now, prove no ad re-entered review"),
    ):
        action = feed_sub.add_parser(name, help=help_text)
        action.add_argument("--feed-id", help="only allowed when the profile has no feed_id")
        action.add_argument("--sheet", help="Google Sheet URL/id (public link for Meta)")
        action.add_argument("--tab", default="products")
        action.add_argument("--gid", type=int, help="tab gid when GSHEETS_JSON_KEY_FILE is not set")
        action.add_argument("--url", help="explicit feed URL instead of the sheet CSV export")
        action.add_argument("--update-only", action="store_true")
        action.add_argument("--wait", type=int, default=120)
        action.add_argument("--confirm", required=True, help="must be literal FEED")
        if name == "swap":
            action.add_argument("--file", required=True, help="CSV/JSON items keyed by id")
            action.add_argument("--force", action="store_true", help="skip the in-review swap gate")
            action.add_argument("--paused-ok", action="store_true",
                                help="treat paused ads on affected sets as approved")
        action.set_defaults(handler=handler)

    p = sub.add_parser("plan", help="validate one spec and write a hash-bound plan")
    p.add_argument("--spec", required=True)
    p.add_argument("--state", help="explicit state path for apply/resume")
    p.add_argument("--out", help="plan artifact path")
    p.add_argument("--doctor-receipt", help="account-specific receipt; default from doctor")
    p.set_defaults(handler=command_plan)

    p = sub.add_parser("apply", help="create/resume one plan; ACTIVE by default, spends immediately")
    p.add_argument("--plan", required=True)
    p.add_argument(
        "--confirm", required=True,
        help="must be literal SPEND — apply creates ACTIVE objects and spends on success unless "
             "the spec sets create_status: PAUSED",
    )
    p.add_argument("--refresh-start", help="future ISO-8601 start_time with offset for ad sets not yet "
                   "created; resumes a partial build whose spec start_time has passed (spec/plan unchanged)")
    p.set_defaults(handler=command_apply)

    for name, help_text, handler in (
        ("verify", "read back one built plan and write its receipt", command_verify),
        ("status", "inspect local plan/state/receipt without network", command_status),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--plan", required=True)
        p.set_defaults(handler=handler)

    p = sub.add_parser("activate", help="activate a verified single plan; spends")
    p.add_argument("--plan", required=True)
    p.add_argument("--confirm", required=True, help="must be literal SPEND")
    p.add_argument("--confirm-ui", required=True, help="must be REVIEWED after UI-only checks")
    p.add_argument("--refresh-start")
    p.set_defaults(handler=command_activate)

    p = sub.add_parser("bulk-plan", help="validate a template/accounts batch and bind its inputs")
    p.add_argument("--template", required=True)
    p.add_argument("--accounts", required=True)
    p.add_argument("--run")
    p.add_argument("--only")
    p.add_argument("--out")
    p.set_defaults(handler=command_bulk_plan)

    p = sub.add_parser("bulk-apply", help="create/resume a bound batch; ACTIVE by default, spends immediately")
    p.add_argument("--plan", required=True)
    p.add_argument(
        "--confirm", required=True,
        help="must be literal SPEND — bulk-apply creates ACTIVE objects and spends on success "
             "unless the template sets create_status: PAUSED",
    )
    p.add_argument("--verify", action="store_true", help="verify every built tree")
    p.add_argument("--dlo-tested", action="store_true",
                   help="operator attestation required by bulk.py for multi-account DLO/catalog")
    p.set_defaults(handler=command_bulk_apply)

    p = sub.add_parser("bulk-activate", help="activate one verified account from a bulk plan")
    p.add_argument("--plan", required=True)
    p.add_argument("--account", required=True)
    p.add_argument("--confirm", required=True, help="must be literal SPEND")
    p.add_argument("--confirm-ui", required=True, help="must be REVIEWED after UI-only checks")
    p.add_argument("--refresh-start")
    p.set_defaults(handler=command_bulk_activate)

    import importlib
    for module_name in COMMAND_MODULES:
        module = importlib.import_module(module_name)
        module.register(sub, sys.modules[__name__])

    add_json_help(ap)
    return ap


def human_summary(payload: dict[str, Any]) -> None:
    mark = "OK" if payload["ok"] else "FAILED"
    print(f"{mark}: {payload['command']} → {payload['phase']}")
    for name, path in payload.get("artifacts", {}).items():
        if path:
            print(f"  {name}: {path}")
    if payload.get("next_action"):
        print(f"  next: {payload['next_action']}")
    if payload.get("error"):
        print(f"  error: {payload['error'].get('message')}", file=sys.stderr)


def main() -> int:
    args = parser().parse_args()
    try:
        if not any(arg == "--timeout" or arg.startswith("--timeout=") for arg in sys.argv[1:]):
            raw_timeout = os.environ.get("METAOPS_TIMEOUT_SECONDS")
            if raw_timeout is not None:
                try:
                    args.timeout = int(raw_timeout)
                except ValueError as exc:
                    raise MetaOpsError("METAOPS_TIMEOUT_SECONDS must be a positive integer") from exc
        if args.timeout <= 0:
            raise MetaOpsError("--timeout must be > 0")
        # Only the offline manifest check may run without the workspace's token.
        args.workspace_obj = configure_workspace(
            args.workspace,
            require_token=args.handler is not command_workspace_validate,
        )
        require_command_workspace(args)
        if args.workspace_obj:
            # Account context for pacing: throttles on object paths (campaign/ad ids carry no
            # act_) are charged to the profile's ad account, here and in child scripts.
            try:
                _, _prof = args.workspace_obj.profile(getattr(args, "profile", None))
                if _prof.get("ad_account_id"):
                    os.environ["METAOPS_ACCOUNT_CONTEXT"] = graph.normalize_account(_prof["ad_account_id"])
                    graph._LAST_ACCOUNT = os.environ["METAOPS_ACCOUNT_CONTEXT"]
            except meta_workspace.WorkspaceError:
                pass
        code, payload = args.handler(args)
    except (MetaOpsError, meta_workspace.WorkspaceError, graph.GraphError, KeyError, TypeError,
            ValueError, OSError, subprocess.SubprocessError) as exc:
        message = graph.redact(str(exc))
        payload = result_envelope(
            args.command,
            False,
            "launcher_error",
            error={"kind": "precondition", "message": message},
        )
        code = 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        human_summary(payload)
    return code


if __name__ == "__main__":
    sys.exit(main())
