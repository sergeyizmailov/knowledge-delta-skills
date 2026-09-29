"""Workspace manifest and profile resolution for agent-driven Meta operations."""

from __future__ import annotations

import copy
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any

import tokens

WORKSPACE_SCHEMA = "metaops.workspace/v1"
TOP_LEVEL_KEYS = {
    "schema", "name", "api_version", "blocked_accounts", "profiles", "defaults", "risk",
}
DEFAULT_KEYS = {"profile", "token_env", "token_envs", "allow_no_proxy", "state_dir"}
PROFILE_KEYS = {
    "business_id",
    "app_id",
    "system_user_id",
    "ad_account_id",
    "page_id",
    "instagram_user_id",
    "dataset_id",
    "catalog_id",
    "feed_id",
    "keitaro_campaign_id",
    "product_sets",
    "currency",
    "timezone",
    "token_kind",
    "risk",
}
TOKEN_KINDS = {"system_user", "user", "auto"}
ID_KEYS = {
    "business_id",
    "app_id",
    "system_user_id",
    "page_id",
    "dataset_id",
    "catalog_id",
    "feed_id",
    "keitaro_campaign_id",
}
SAFE_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")

# `doctor --risk` thresholds. These are the operator's OWN priors: no Meta source ties any of them
# to Spam / Account Integrity disables. A `risk` block (workspace top level, then
# `profiles.<p>.risk`, later wins) overrides individual keys; unknown keys are refused so a typo
# cannot silently keep a default.
RISK_DEFAULTS: dict[str, float] = {
    "min_account_age_days": 14,     # account younger than this -> warn
    "min_amount_spent": 50,         # lifetime amount_spent below this, ACCOUNT currency (no FX) -> warn
    "min_pixel_age_days": 3,        # pixel created more recently than this -> warn
    "min_page_followers": 100,      # Page followers below this -> warn
    "max_disapproved_ratio": 0.20,  # DISAPPROVED / ads in window at or above this -> warn
    "disapproved_high_ratio": 0.50, # ... at or above this -> high
    "min_ads_for_ratio": 5,         # fewer ads than this in the window: ratio reported as info only
    "ads_window_days": 30,          # ads created within this many days are counted
    "ads_max_pages": 5,             # /act_X/ads pages (200 rows each) read at most
    "spend_cap_near_ratio": 0.90,   # amount_spent / spend_cap at or above this -> warn (>= 1 -> high)
}
RISK_RATIO_KEYS = {"max_disapproved_ratio", "disapproved_high_ratio", "spend_cap_near_ratio"}
RISK_INT_KEYS = {"min_ads_for_ratio", "ads_window_days", "ads_max_pages"}


class WorkspaceError(Exception):
    """Invalid or inconsistent workspace configuration."""


@dataclass(frozen=True)
class Workspace:
    path: pathlib.Path
    root: pathlib.Path
    data: dict[str, Any]

    @property
    def state_root(self) -> pathlib.Path:
        configured = (self.data.get("defaults") or {}).get("state_dir", ".metaops")
        path = pathlib.Path(str(configured)).expanduser()
        return path.resolve() if path.is_absolute() else (self.root / path).resolve()

    def profile_name(self, requested: str | None = None) -> str:
        name = requested or (self.data.get("defaults") or {}).get("profile")
        if not name:
            raise WorkspaceError("profile is required; pass --profile or set defaults.profile")
        if name not in self.data["profiles"]:
            raise WorkspaceError(f"unknown profile {name!r}; known: {sorted(self.data['profiles'])}")
        return str(name)

    def profile(self, requested: str | None = None) -> tuple[str, dict[str, Any]]:
        name = self.profile_name(requested)
        return name, copy.deepcopy(self.data["profiles"][name])

    def risk_config(self, requested: str | None = None) -> dict[str, float]:
        """RISK_DEFAULTS < workspace `risk` < `profiles.<p>.risk`."""
        _, profile = self.profile(requested)
        return merge_risk(self.data.get("risk"), profile.get("risk"))


def _load_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkspaceError(f"workspace does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"workspace is not valid JSON: {path}: {exc}") from exc


def workspace_path(value: str) -> pathlib.Path:
    path = pathlib.Path(value).expanduser().resolve()
    return path / "workspace.json" if path.is_dir() else path


def discover_workspace(start: pathlib.Path | None = None) -> pathlib.Path | None:
    current = (start or pathlib.Path.cwd()).expanduser().resolve()
    current = current.parent if current.is_file() else current
    for root in (current, *current.parents):
        candidate = root / "workspace.json"
        if candidate.is_file():
            return candidate
    return None


def load_workspace(value: str) -> Workspace:
    path = workspace_path(value)
    parts = path.parts
    if any(parts[index] == "skills" and index > 0 and parts[index - 1].startswith(".")
           for index in range(len(parts))):
        raise WorkspaceError(
            "workspace.json must live in a project directory outside skill stores"
        )
    data = _load_json(path)
    validate_workspace(data)
    workspace = Workspace(path=path, root=path.parent, data=data)
    if workspace.state_root != workspace.root and workspace.root not in workspace.state_root.parents:
        raise WorkspaceError("workspace.defaults.state_dir must stay inside the workspace")
    return workspace


def _numeric_id(value: Any, label: str) -> str:
    text = str(value or "")
    if not text.isdigit():
        raise WorkspaceError(f"{label} must be a numeric Meta id")
    return text


def validate_risk_block(block: Any, label: str) -> None:
    """A `risk` block is an object of known threshold keys with sane numbers. Absent is fine."""
    if not isinstance(block, dict):
        raise WorkspaceError(f"{label} must be an object")
    unknown = sorted(set(block) - set(RISK_DEFAULTS))
    if unknown:
        raise WorkspaceError(f"{label} has unsupported keys: {unknown}; known: {sorted(RISK_DEFAULTS)}")
    for key, value in block.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
            raise WorkspaceError(f"{label}.{key} must be a number")
        if value < 0:
            raise WorkspaceError(f"{label}.{key} must not be negative")
        if key in RISK_RATIO_KEYS and value > 1:
            raise WorkspaceError(f"{label}.{key} is a ratio between 0 and 1")
        if key in RISK_INT_KEYS and (value != int(value) or value < 1):
            raise WorkspaceError(f"{label}.{key} must be a whole number of at least 1")


def merge_risk(*blocks: Any) -> dict[str, float]:
    """RISK_DEFAULTS overlaid by each given block in order (None / missing blocks are skipped)."""
    merged: dict[str, float] = dict(RISK_DEFAULTS)
    for index, block in enumerate(blocks):
        if block is None:
            continue
        validate_risk_block(block, f"risk[{index}]")
        merged.update(block)
    return merged


def validate_workspace(data: Any) -> None:
    if not isinstance(data, dict) or data.get("schema") != WORKSPACE_SCHEMA:
        raise WorkspaceError(f"workspace.schema must be {WORKSPACE_SCHEMA!r}")
    unknown_top = sorted(set(data) - TOP_LEVEL_KEYS)
    if unknown_top:
        raise WorkspaceError(f"workspace has unsupported keys: {unknown_top}")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise WorkspaceError("workspace.name must be a non-empty string")
    if not isinstance(data.get("api_version"), str) or not re.fullmatch(
        r"v[0-9]+\.[0-9]+", data["api_version"]
    ):
        raise WorkspaceError("workspace.api_version must look like v26.0")
    defaults = data.get("defaults")
    if not isinstance(defaults, dict):
        raise WorkspaceError("workspace.defaults must be an object")
    unknown_defaults = sorted(set(defaults) - DEFAULT_KEYS)
    if unknown_defaults:
        raise WorkspaceError(f"workspace.defaults has unsupported keys: {unknown_defaults}")
    if not defaults.get("profile"):
        raise WorkspaceError("workspace.defaults.profile is required")
    if not isinstance(defaults["profile"], str):
        raise WorkspaceError("workspace.defaults.profile must be a string")
    if "state_dir" in defaults and not isinstance(defaults["state_dir"], str):
        raise WorkspaceError("workspace.defaults.state_dir must be a string")
    if "allow_no_proxy" in defaults and not isinstance(defaults["allow_no_proxy"], bool):
        raise WorkspaceError("workspace.defaults.allow_no_proxy must be a boolean")
    if "risk" in data:
        validate_risk_block(data["risk"], "workspace.risk")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise WorkspaceError("workspace.profiles must be a non-empty object")
    raw_blocked = data.get("blocked_accounts", [])
    if not isinstance(raw_blocked, list):
        raise WorkspaceError("workspace.blocked_accounts must be an array")
    if any(not isinstance(value, str) for value in raw_blocked):
        raise WorkspaceError("every blocked account must be a string")
    if any(not re.fullmatch(r"act_[0-9]+", value) for value in raw_blocked):
        raise WorkspaceError("every blocked account must be act_<numeric>")
    blocked_list = list(raw_blocked)
    if len(set(blocked_list)) != len(blocked_list):
        raise WorkspaceError("workspace.blocked_accounts contains duplicates")
    blocked = set(blocked_list)
    accounts: set[str] = set()
    for name, profile in profiles.items():
        if not SAFE_ALIAS.fullmatch(str(name)):
            raise WorkspaceError(f"invalid profile name: {name!r}")
        if not isinstance(profile, dict):
            raise WorkspaceError(f"profiles.{name} must be an object")
        unknown = sorted(set(profile) - PROFILE_KEYS)
        if unknown:
            raise WorkspaceError(f"profiles.{name} has unsupported keys: {unknown}")
        # app_id/system_user_id are OPTIONAL: a System User token needs both to run its
        # provisioning-authority and BM-ownership checks; a plain user token (own BM admin,
        # third-party developer app, or a scraped browser session, `02`) has neither and
        # still launches — asset_graph.py resolves the acting token_kind and downgrades the
        # app/System-User BM-ownership checks to warnings when it is not a System User.
        # `doctor --scope provisioning` and any Business-Portfolio provisioning command still
        # hard-require system_user_id (metaops.require_provisioning_admin).
        required = {
            "business_id", "ad_account_id", "page_id",
            "dataset_id", "currency", "timezone",
        }
        missing = sorted(key for key in required if not profile.get(key))
        if missing:
            raise WorkspaceError(f"profiles.{name} is missing required keys: {missing}")
        if not isinstance(profile.get("ad_account_id"), str):
            raise WorkspaceError(f"profiles.{name}.ad_account_id must be a string")
        account = profile["ad_account_id"]
        if not re.fullmatch(r"act_[0-9]+", account):
            raise WorkspaceError(f"profiles.{name}.ad_account_id must be act_<numeric>")
        if account in blocked:
            raise WorkspaceError(f"profiles.{name} uses blocked account {account}")
        if account in accounts:
            raise WorkspaceError(f"duplicate ad account across profiles: {account}")
        accounts.add(account)
        profile["ad_account_id"] = account
        for key in ID_KEYS:
            if key in profile:
                if not isinstance(profile[key], str):
                    raise WorkspaceError(f"profiles.{name}.{key} must be a string")
                _numeric_id(profile[key], f"profiles.{name}.{key}")
        if "instagram_user_id" in profile:
            if not isinstance(profile["instagram_user_id"], str):
                raise WorkspaceError(f"profiles.{name}.instagram_user_id must be a string")
            if profile["instagram_user_id"] != "auto":
                _numeric_id(profile["instagram_user_id"], f"profiles.{name}.instagram_user_id")
        sets = profile.get("product_sets", {})
        if not isinstance(sets, dict):
            raise WorkspaceError(f"profiles.{name}.product_sets must be an object")
        for alias, set_id in sets.items():
            if not SAFE_ALIAS.fullmatch(str(alias)):
                raise WorkspaceError(f"invalid product-set alias in profiles.{name}: {alias!r}")
            if not isinstance(set_id, str):
                raise WorkspaceError(f"profiles.{name}.product_sets.{alias} must be a string")
            _numeric_id(set_id, f"profiles.{name}.product_sets.{alias}")
        if "risk" in profile:
            validate_risk_block(profile["risk"], f"profiles.{name}.risk")
        if "token_kind" in profile and profile["token_kind"] not in TOKEN_KINDS:
            raise WorkspaceError(
                f"profiles.{name}.token_kind must be one of {sorted(TOKEN_KINDS)}"
            )
        currency = profile.get("currency")
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise WorkspaceError(f"profiles.{name}.currency must be an ISO 4217 code")
        if not isinstance(profile.get("timezone"), str) or not profile["timezone"]:
            raise WorkspaceError(f"profiles.{name}.timezone must be a non-empty string")
    default = defaults.get("profile")
    if default and default not in profiles:
        raise WorkspaceError(f"defaults.profile {default!r} is not defined")
    token_env = defaults.get("token_env", "META_TOKEN")
    if not isinstance(token_env, str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", token_env):
        raise WorkspaceError("defaults.token_env must be an uppercase environment variable")
    if "token_envs" in defaults:
        # {capability: ENV_NAME}: which variable holds the token for business reads, catalog, CAPI
        # events and rules (tokens.py). Ads reads and writes keep token_env / META_TOKEN.
        token_envs = defaults["token_envs"]
        if not isinstance(token_envs, dict):
            raise WorkspaceError("workspace.defaults.token_envs must be an object")
        unknown_caps = sorted(set(token_envs) - set(tokens.ROUTED_CAPABILITIES))
        if unknown_caps:
            raise WorkspaceError(
                f"workspace.defaults.token_envs has unsupported capabilities: {unknown_caps}; "
                f"known: {list(tokens.ROUTED_CAPABILITIES)}"
            )
        for capability, name in token_envs.items():
            if not isinstance(name, str) or not tokens.ENV_NAME.fullmatch(name):
                raise WorkspaceError(
                    f"defaults.token_envs.{capability} must be an uppercase environment variable"
                )


def resolve_spec(
    raw: dict[str, Any],
    workspace: Workspace,
    requested_profile: str | None = None,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise WorkspaceError("campaign spec must be a JSON object")
    name, profile = workspace.profile(requested_profile or raw.get("profile"))
    resolved = copy.deepcopy(raw)
    routing = {
        "account_id": profile["ad_account_id"],
        "page_id": profile.get("page_id"),
        "pixel_id": profile.get("dataset_id"),
        "instagram_user_id": profile.get("instagram_user_id", "auto"),
        "currency": profile.get("currency"),
    }
    for key, value in routing.items():
        if value is None:
            continue
        existing = resolved.get(key)
        if existing is not None and str(existing) != str(value):
            raise WorkspaceError(
                f"spec {key}={existing!r} conflicts with profile {name} value {value!r}"
            )
        resolved[key] = value
    resolved["profile"] = name
    aliases = profile.get("product_sets") or {}
    allowed_set_ids = {str(value) for value in aliases.values()}
    for aset in resolved.get("adsets") or []:
        promoted = aset.get("promoted_object") or {}
        nested_routing = {
            "pixel_id": profile.get("dataset_id"),
            "page_id": profile.get("page_id"),
            "product_catalog_id": profile.get("catalog_id"),
            "catalog_id": profile.get("catalog_id"),
        }
        for key, expected in nested_routing.items():
            if promoted.get(key) is not None and str(promoted[key]) != str(expected):
                raise WorkspaceError(
                    f"ad set promoted_object.{key}={promoted[key]!r} conflicts with profile {name}"
                )
        promoted_set = promoted.get("product_set_id")
        if promoted_set is not None and str(promoted_set) not in allowed_set_ids:
            raise WorkspaceError("ad set promoted_object.product_set_id is not declared in profile")
        for ad in aset.get("ads") or []:
            creative = ad.get("creative") or {}
            alias = creative.pop("product_set", None)
            if alias is not None:
                if alias not in aliases:
                    raise WorkspaceError(
                        f"creative product_set alias {alias!r} is not defined in profile {name}"
                    )
                existing = creative.get("product_set_id")
                if existing is not None and str(existing) != str(aliases[alias]):
                    raise WorkspaceError("creative product_set and product_set_id conflict")
                creative["product_set_id"] = str(aliases[alias])
            raw_set = creative.get("product_set_id")
            if raw_set is not None and str(raw_set) not in allowed_set_ids:
                raise WorkspaceError("creative.product_set_id is not declared in profile")
    return name, resolved
