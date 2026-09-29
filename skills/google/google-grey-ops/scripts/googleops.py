"""googleops — agent-facing Google Ads launch lifecycle.

workspace validate -> doctor -> plan (validate_only) -> apply (PAUSED) -> verify (read-back)
-> activate (--confirm SPEND). Bulk: bulk-plan -> bulk-apply -> bulk-activate (one customer each).
Read-only helpers: report (GAQL), monitor.

stdout: exactly one googleops.result/v1 JSON object with --json. Diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
from typing import Any, Iterator

import gads_build
import gads_client
import gads_spec
import gads_verify
import gads_workspace
from google.protobuf import field_mask_pb2

RESULT_SCHEMA = "googleops.result/v1"
PLAN_SCHEMA = "googleops.plan/v1"
BULK_SCHEMA = "googleops.bulk-plan/v1"
DOCTOR_MAX_AGE = int(os.environ.get("GOOGLEOPS_DOCTOR_MAX_AGE_SECONDS", "86400"))


class OpsError(Exception):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: pathlib.Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OpsError(f"cannot read {label} {path}: {exc}") from exc


def atomic_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def envelope(command: str, ok: bool, phase: str, *, artifacts: dict | None = None, data: dict | None = None,
             error: dict | None = None, next_action: str | None = None) -> dict[str, Any]:
    return {"schema": RESULT_SCHEMA, "ok": ok, "command": command, "phase": phase,
            "artifacts": artifacts or {}, "data": data or {}, "error": error, "next_action": next_action}


@contextlib.contextmanager
def lock(path: pathlib.Path) -> Iterator[None]:
    lk = pathlib.Path(str(path) + ".lock")
    lk.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lk, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise OpsError(f"state locked by another process: {lk} ({lk.read_text(errors='ignore').strip()})") from exc
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps({"pid": os.getpid(), "created_at": now()}))
        yield
    finally:
        lk.unlink(missing_ok=True)


# ---------------------------------------------------------------- context

class Ctx:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.ws = gads_workspace.load_workspace(args.workspace)
        self.profile_name, self.profile = self.ws.profile(args.profile)
        self.customer_id = gads_workspace.normalize_customer(self.profile["customer_id"])
        self.login_customer_id = gads_workspace.normalize_customer(self.profile["login_customer_id"])
        if self.ws.blocked(self.customer_id):
            raise OpsError(f"customer {self.customer_id} is in blocked_customers")
        self.state_dir = self.ws.state_dir
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = gads_client.build_client(self.login_customer_id, self.ws.api_version,
                                                   self.ws.data["defaults"].get("auth", "oauth"))
        return self._client

    def doctor_path(self, customer_id: str | None = None) -> pathlib.Path:
        return self.state_dir / "doctor" / f"{customer_id or self.customer_id}.json"

    def plan_dir(self) -> pathlib.Path:
        return self.state_dir / "plans"

    def state_path(self, run_id: str, customer_id: str | None = None) -> pathlib.Path:
        return self.state_dir / "state" / f"{customer_id or self.customer_id}-{run_id}.json"


def run_mutate(ctx: Ctx, customer_id: str, ops: list[Any], validate_only: bool) -> Any:
    from google.ads.googleads.errors import GoogleAdsException

    req = ctx.client.get_type("MutateGoogleAdsRequest")
    req.customer_id = customer_id
    req.mutate_operations.extend(ops)
    req.validate_only = validate_only
    try:
        return ctx.client.get_service("GoogleAdsService").mutate(request=req)
    except GoogleAdsException as exc:
        raise OpsError(json.dumps({"kind": "google_ads_failure", **gads_client.failure_details(exc)})) from exc


# ---------------------------------------------------------------- doctor

def require_doctor(ctx: Ctx, customer_id: str | None = None) -> tuple[pathlib.Path, str]:
    path = ctx.doctor_path(customer_id)
    if not path.is_file():
        raise OpsError(f"no doctor receipt for {customer_id or ctx.customer_id}; run: googleops doctor")
    receipt = read_json(path, "doctor receipt")
    age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(receipt["created_at"])
    if age.total_seconds() > DOCTOR_MAX_AGE:
        raise OpsError(f"doctor receipt older than {DOCTOR_MAX_AGE}s; rerun doctor")
    if receipt.get("workspace_sha") != file_sha(ctx.ws.path):
        raise OpsError("workspace.json changed since doctor; rerun doctor")
    if not receipt.get("ok"):
        raise OpsError("last doctor run failed; fix it before planning")
    return path, file_sha(path)


def cmd_doctor(ctx: Ctx) -> tuple[int, dict]:
    client = ctx.client
    problems: list[str] = []
    data: dict[str, Any] = {"customer_id": ctx.customer_id, "login_customer_id": ctx.login_customer_id,
                            "api_version": ctx.ws.api_version, "egress": gads_client.egress_check()}
    from google.ads.googleads.errors import GoogleAdsException
    try:
        accessible = client.get_service("CustomerService").list_accessible_customers().resource_names
    except GoogleAdsException as exc:
        return 1, envelope("doctor", False, "auth_failed", error=gads_client.failure_details(exc),
                           next_action="Fix credentials/developer token; see references/09 and google-ads/11.")
    data["accessible_customers"] = [r.rsplit("/", 1)[-1] for r in accessible]
    if ctx.login_customer_id not in data["accessible_customers"]:
        problems.append(f"login_customer_id {ctx.login_customer_id} is not directly accessible to this credential")
    try:
        rows = gads_client.search(client, ctx.customer_id, """
            SELECT customer.id, customer.descriptive_name, customer.currency_code, customer.time_zone,
              customer.status, customer.manager, customer.test_account, customer.auto_tagging_enabled,
              customer.conversion_tracking_setting.conversion_tracking_id,
              customer.conversion_tracking_setting.conversion_tracking_status
            FROM customer""")
    except GoogleAdsException as exc:
        details = gads_client.failure_details(exc)
        return 1, envelope("doctor", False, "customer_unreachable", data=data, error=details,
                           next_action="USER_PERMISSION_DENIED/CUSTOMER_NOT_ENABLED: check login_customer_id "
                                       "and that the customer sits under this MCC (references/09).")
    c = rows[0].customer
    data["customer"] = {"name": c.descriptive_name, "currency": c.currency_code, "timezone": c.time_zone,
                        "status": c.status.name, "manager": c.manager, "test_account": c.test_account,
                        "auto_tagging": c.auto_tagging_enabled,
                        "conversion_tracking_status": c.conversion_tracking_setting.conversion_tracking_status.name,
                        "conversion_tracking_id": c.conversion_tracking_setting.conversion_tracking_id}
    if c.currency_code != ctx.profile["currency"]:
        problems.append(f"profile currency {ctx.profile['currency']} != account currency {c.currency_code}")
    if c.time_zone != ctx.profile["timezone"]:
        problems.append(f"profile timezone {ctx.profile['timezone']} != account timezone {c.time_zone}")
    if c.status.name != "ENABLED":
        problems.append(f"customer status {c.status.name}")
    if c.manager:
        problems.append("customer_id is a manager account; launches need a client account")
    if not c.auto_tagging_enabled:
        problems.append("auto-tagging is off: no gclid on clicks, offline conversion import will not work")
    billing = gads_client.search(client, ctx.customer_id, """
        SELECT billing_setup.id, billing_setup.status, billing_setup.payments_account_info.payments_account_id
        FROM billing_setup""")
    data["billing_setups"] = [{"id": r.billing_setup.id, "status": r.billing_setup.status.name} for r in billing]
    if not any(b["status"] == "APPROVED" for b in data["billing_setups"]):
        problems.append("no APPROVED billing setup — PAUSED build is fine, activation would not serve")
    convs = gads_client.search(client, ctx.customer_id, """
        SELECT conversion_action.id, conversion_action.name, conversion_action.status, conversion_action.type,
          conversion_action.category, conversion_action.primary_for_goal,
          conversion_action.include_in_conversions_metric, conversion_action.origin
        FROM conversion_action WHERE conversion_action.status = 'ENABLED'""")
    data["conversion_actions"] = [{"id": r.conversion_action.id, "name": r.conversion_action.name,
                                   "type": r.conversion_action.type_.name, "category": r.conversion_action.category.name,
                                   "primary_for_goal": r.conversion_action.primary_for_goal,
                                   "include_in_conversions": r.conversion_action.include_in_conversions_metric}
                                  for r in convs]
    if not any(a["include_in_conversions"] for a in data["conversion_actions"]):
        problems.append("no conversion action is included in 'Conversions' — Smart Bidding has nothing to chase")
    for alias, cid in (ctx.profile.get("conversion_actions") or {}).items():
        if not any(str(a["id"]) == str(cid) for a in data["conversion_actions"]):
            problems.append(f"profile conversion_actions.{alias}={cid} not found/enabled on the account")
    links = gads_client.search(client, ctx.customer_id, """
        SELECT product_link.product_link_id, product_link.type, product_link.merchant_center.merchant_center_id
        FROM product_link""")
    data["merchant_center_links"] = [str(r.product_link.merchant_center.merchant_center_id) for r in links
                                     if r.product_link.type_.name == "MERCHANT_CENTER"]
    if ctx.profile.get("merchant_id") and str(ctx.profile["merchant_id"]) not in data["merchant_center_links"]:
        pending = gads_client.search(client, ctx.customer_id, """
            SELECT product_link_invitation.product_link_invitation_id, product_link_invitation.status,
              product_link_invitation.merchant_center.merchant_center_id
            FROM product_link_invitation""")
        data["merchant_center_invitations"] = [
            {"id": r.product_link_invitation.product_link_invitation_id, "status": r.product_link_invitation.status.name,
             "merchant_id": str(r.product_link_invitation.merchant_center.merchant_center_id)} for r in pending]
        problems.append(f"merchant_id {ctx.profile['merchant_id']} is not linked to this customer "
                        "(accept the invitation with: googleops link accept --merchant <id>)")
    # write probe: a validate_only budget create proves mutate access without persisting anything
    probe = client.get_type("MutateOperation")
    budget = probe.campaign_budget_operation.create
    budget.name = f"googleops write probe {now()}"
    budget.amount_micros = 1_000_000
    budget.explicitly_shared = False
    try:
        run_mutate(ctx, ctx.customer_id, [probe], validate_only=True)
        data["write_probe"] = "ok"
    except OpsError as exc:
        data["write_probe"] = str(exc)[:500]
        problems.append("validate_only write probe failed — read access is not write access")
    ok = not problems
    receipt = {"schema": "googleops.doctor/v1", "ok": ok, "created_at": now(), "customer_id": ctx.customer_id,
               "profile": ctx.profile_name, "workspace_sha": file_sha(ctx.ws.path), "api_version": ctx.ws.api_version,
               "data": data, "problems": problems}
    atomic_json(ctx.doctor_path(), receipt)
    return (0 if ok else 1), envelope(
        "doctor", ok, "ready" if ok else "blocked", artifacts={"receipt": str(ctx.doctor_path())},
        data={**data, "problems": problems},
        next_action="googleops plan --spec <spec.json>" if ok else "Fix every problem, then rerun doctor.")


# ---------------------------------------------------------------- plan / apply / verify / activate

def load_spec(ctx: Ctx, path: pathlib.Path, tag: str | None = None) -> dict[str, Any]:
    raw = read_json(path, "spec")
    if tag is not None:
        raw = json.loads(json.dumps(raw).replace("{tag}", tag))
    try:
        return gads_spec.normalize(raw, ctx.profile)
    except gads_spec.SpecError as exc:
        raise OpsError(f"spec rejected: {exc}") from exc


def validate_graph(ctx: Ctx, customer_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    """validate_only pass. PMax needs its assets created before the graph, so the graph validation
    substitutes temp asset ids; if the API rejects that ordering the scope is recorded as partial."""
    g_assets = None
    scope = "full"
    if spec["campaign"]["kind"] == "pmax_retail":
        g = gads_build.Graph(ctx.client, customer_id)
        asset_ops, mapping = gads_build.pmax_asset_operations(g, spec)
        if asset_ops:
            run_mutate(ctx, customer_id, asset_ops, validate_only=True)
        g_assets = gads_build.resolve_existing_assets(g, spec)
        for name, pairs in mapping.items():
            for key, _ in pairs:
                if key not in g_assets.get(name, {}):
                    g_assets.setdefault(name, {})[key] = ctx.client.get_service("AssetService").asset_path(
                        customer_id, str(-1000 - len(g_assets[name])))
    graph = gads_build.build_graph(ctx.client, customer_id, spec, g_assets)
    try:
        run_mutate(ctx, customer_id, graph.ops, validate_only=True)
    except OpsError as exc:
        try:
            errors = json.loads(exc.args[0]).get("errors", [])
        except (ValueError, TypeError, AttributeError):
            errors = []
        asset_link_only = bool(errors) and all(
            (e.get("code") or "").split(".")[0] in ("asset_group_asset_error", "asset_link_error", "asset_error")
            or "asset_group_asset_operation" in (e.get("path") or "")
            for e in errors)
        if spec["campaign"]["kind"] == "pmax_retail" and asset_link_only:
            scope = "partial:pmax-assets-validated-graph-deferred"
        else:
            raise
    return {"operations": gads_build.summarize(graph), "validation_scope": scope}


def merchant_binding(ctx: Ctx, spec: dict[str, Any]) -> dict[str, Any]:
    """Retail kinds: bind a fresh, passing gmcops doctor receipt when given; warn loudly when not."""
    if spec["campaign"]["kind"] not in ("pmax_retail", "shopping"):
        return {}
    receipt_arg = getattr(ctx.args, "merchant_receipt", None)
    if not receipt_arg:
        if getattr(ctx.args, "allow_unverified_merchant", False):
            print("WARNING: retail plan without a Merchant Center receipt — gates/issues/eligibility "
                  "unverified; the campaign may build PAUSED and never serve", file=sys.stderr)
            return {"merchant_receipt": None, "merchant_unverified": True}
        raise OpsError("retail kinds require --merchant-receipt <gmcops doctor --out receipt.json> "
                       "(or --allow-unverified-merchant to accept a campaign that may never serve)")
    path = pathlib.Path(receipt_arg).expanduser().resolve()
    receipt = read_json(path, "merchant receipt")
    if receipt.get("schema") != "gmcops.doctor/v1" or str(receipt.get("account")) != str(spec["campaign"]["merchant_id"]):
        raise OpsError("merchant receipt is not a gmcops doctor receipt for this spec's merchant_id")
    age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(receipt["created_at"])
    if age.total_seconds() > DOCTOR_MAX_AGE or not receipt.get("ok"):
        raise OpsError("merchant receipt is stale or failed; rerun gmcops doctor")
    return {"merchant_receipt": str(path), "merchant_sha": file_sha(path)}


def cmd_plan(ctx: Ctx) -> tuple[int, dict]:
    spec_path = pathlib.Path(ctx.args.spec).expanduser().resolve()
    doctor_path, doctor_sha = require_doctor(ctx)
    spec = load_spec(ctx, spec_path, ctx.args.tag)
    merchant = merchant_binding(ctx, spec)
    summary = validate_graph(ctx, ctx.customer_id, spec)
    plan = {**merchant, "schema": PLAN_SCHEMA, "created_at": now(), "run_id": spec["run_id"], "profile": ctx.profile_name,
            "customer_id": ctx.customer_id, "api_version": ctx.ws.api_version, "spec_source": str(spec_path),
            "spec": spec, "spec_sha": sha(spec), "workspace_sha": file_sha(ctx.ws.path),
            "doctor_receipt": str(doctor_path), "doctor_sha": doctor_sha,
            "state_path": str(ctx.state_path(spec["run_id"])), **summary}
    plan_path = ctx.plan_dir() / f"{ctx.customer_id}-{spec['run_id']}-{plan['spec_sha'][:12]}.json"
    atomic_json(plan_path, plan)
    return 0, envelope("plan", True, "validated", artifacts={"plan": str(plan_path)},
                       data={"run_id": spec["run_id"], "customer_id": ctx.customer_id,
                             "kind": spec["campaign"]["kind"],
                             "daily_budget_major": spec["campaign"]["daily_budget_micros"] / 1e6,
                             "currency": spec["currency"], **summary},
                       next_action=f"Review the plan, then: googleops apply --plan {plan_path}")


def load_plan(ctx: Ctx, value: str, schema: str) -> tuple[pathlib.Path, dict[str, Any]]:
    path = pathlib.Path(value).expanduser().resolve()
    plan = read_json(path, "plan")
    if plan.get("schema") != schema:
        raise OpsError(f"{path} is not a {schema}")
    if plan.get("api_version") != ctx.ws.api_version:
        raise OpsError("plan was made under another api_version; re-plan")
    if plan.get("workspace_sha") != file_sha(ctx.ws.path):
        raise OpsError("workspace.json changed since plan; re-plan")
    return path, plan


def bind_plan(ctx: Ctx, plan: dict[str, Any], customer_id: str) -> None:
    if plan["customer_id"] != customer_id:
        raise OpsError("plan customer_id does not match the selected profile")
    if sha(plan["spec"]) != plan["spec_sha"]:
        raise OpsError("plan spec hash mismatch — plan file was edited; re-plan")
    d_path = pathlib.Path(plan["doctor_receipt"])
    if not d_path.is_file() or file_sha(d_path) != plan["doctor_sha"]:
        raise OpsError("doctor receipt changed or missing since plan; rerun doctor and re-plan")
    require_doctor(ctx, customer_id)


def apply_plan(ctx: Ctx, plan: dict[str, Any], customer_id: str, state_path: pathlib.Path) -> dict[str, Any]:
    spec = plan["spec"]
    state = read_json(state_path, "state") if state_path.exists() else {
        "schema": "googleops.state/v1", "run_id": spec["run_id"], "customer_id": customer_id,
        "spec_sha": plan["spec_sha"], "api_version": ctx.ws.api_version, "objects": {}, "assets": {},
        "in_flight": None, "request_ids": [], "created_at": now()}
    if state["spec_sha"] != plan["spec_sha"]:
        raise OpsError("existing state belongs to a different spec; use a new run_id")
    if state.get("in_flight"):
        raise OpsError(f"state has an in-flight mutate ({state['in_flight']}); reconcile in the UI, "
                       "then clear in_flight manually before retrying")
    if state["objects"].get("campaign"):
        return state
    pmax_assets: dict[str, dict[str, str]] | None = None
    if spec["campaign"]["kind"] == "pmax_retail":
        g = gads_build.Graph(ctx.client, customer_id)
        pmax_assets = gads_build.resolve_existing_assets(g, spec)
        if not state["assets"]:
            asset_ops, mapping = gads_build.pmax_asset_operations(g, spec)
            state["in_flight"] = {"phase": "assets", "at": now()}
            atomic_json(state_path, state)
            resp = run_mutate(ctx, customer_id, asset_ops, validate_only=False)
            created = [r.asset_result.resource_name for r in resp.mutate_operation_responses]
            idx = 0
            for name, pairs in mapping.items():
                for key, _ in pairs:
                    if key.startswith("asset:"):
                        continue
                    state["assets"].setdefault(name, {})[key] = created[idx]
                    idx += 1
            state["in_flight"] = None
            atomic_json(state_path, state)
        for name, mp in state["assets"].items():
            pmax_assets.setdefault(name, {}).update(mp)
    graph = gads_build.build_graph(ctx.client, customer_id, spec, pmax_assets)
    state["in_flight"] = {"phase": "graph", "at": now(), "operations": gads_build.summarize(graph)}
    atomic_json(state_path, state)
    resp = run_mutate(ctx, customer_id, graph.ops, validate_only=False)
    objects: dict[str, Any] = {"ad_groups": [], "ads": [], "asset_groups": [], "criteria": [], "assets": []}
    for r in resp.mutate_operation_responses:
        which = gads_client.oneof(r, "response")
        rn = getattr(r, which).resource_name
        if which == "campaign_result":
            objects["campaign"] = rn
        elif which == "campaign_budget_result":
            objects["budget"] = rn
        elif which == "ad_group_result":
            objects["ad_groups"].append(rn)
        elif which == "ad_group_ad_result":
            objects["ads"].append(rn)
        elif which == "asset_group_result":
            objects["asset_groups"].append(rn)
        elif which == "asset_result":
            objects["assets"].append(rn)
        else:
            objects["criteria"].append(rn)
    state["objects"] = objects
    state["in_flight"] = None
    state["applied_at"] = now()
    atomic_json(state_path, state)
    return state


def cmd_apply(ctx: Ctx) -> tuple[int, dict]:
    plan_path, plan = load_plan(ctx, ctx.args.plan, PLAN_SCHEMA)
    bind_plan(ctx, plan, ctx.customer_id)
    state_path = pathlib.Path(plan["state_path"])
    with lock(state_path):
        try:
            state = apply_plan(ctx, plan, ctx.customer_id, state_path)
        except OpsError as exc:
            st = read_json(state_path, "state") if state_path.exists() else {}
            phase = "reconcile_required" if st.get("in_flight") else "apply_failed"
            if phase == "apply_failed" and st:
                st["in_flight"] = None
                atomic_json(state_path, st)
            err = exc.args[0]
            try:
                err = json.loads(err)
            except (ValueError, TypeError):
                err = {"kind": "ops_error", "message": str(err)}
            return 1, envelope("apply", False, phase, artifacts={"plan": str(plan_path), "state": str(state_path)},
                               error=err, next_action="Fix the spec and re-plan, or reconcile in-flight objects.")
    return 0, envelope("apply", True, "built_paused", artifacts={"plan": str(plan_path), "state": str(state_path)},
                       data={"objects": state["objects"]},
                       next_action=f"googleops verify --plan {plan_path}")


def cmd_verify(ctx: Ctx) -> tuple[int, dict]:
    plan_path, plan = load_plan(ctx, ctx.args.plan, PLAN_SCHEMA)
    bind_plan(ctx, plan, ctx.customer_id)
    state_path = pathlib.Path(plan["state_path"])
    if not state_path.exists():
        raise OpsError("no state; apply first")
    state = read_json(state_path, "state")
    if state.get("in_flight") or not state["objects"].get("campaign"):
        raise OpsError("state incomplete; reconcile/apply before verify")
    result = gads_verify.verify(ctx.client, ctx.customer_id, plan["spec"], state)
    receipt_path = pathlib.Path(str(state_path).replace(".json", ".verified.json"))
    if result["ok"]:
        atomic_json(receipt_path, {"schema": "googleops.verified/v1", "created_at": now(),
                                   "state_sha": file_sha(state_path), "spec_sha": plan["spec_sha"],
                                   "facts": result["facts"]})
    else:
        receipt_path.unlink(missing_ok=True)
    return (0 if result["ok"] else 1), envelope(
        "verify", result["ok"], "verified" if result["ok"] else "verification_failed",
        artifacts={"plan": str(plan_path), "state": str(state_path),
                   "receipt": str(receipt_path) if result["ok"] else None},
        data={"facts": result["facts"], "problems": result["problems"]},
        next_action="Check policy approval in the UI, review-layer readiness, then: googleops activate "
                    "--plan <plan> --confirm SPEND" if result["ok"] else "Fix mismatches; verify again.")


def enable_objects(ctx: Ctx, customer_id: str, spec: dict[str, Any], state: dict[str, Any]) -> list[str]:
    """Ads -> ad groups / asset groups -> campaign. Stops on first failure."""
    client = ctx.client
    enabled: list[str] = []
    ops: list[Any] = []

    def update(field: str, rn: str, enum_name: str) -> None:
        op = client.get_type("MutateOperation")
        target = getattr(op, field).update
        target.resource_name = rn
        target.status = getattr(getattr(client.enums, enum_name), "ENABLED")
        client.copy_from(getattr(op, field).update_mask, field_mask_pb2.FieldMask(paths=["status"]))
        ops.append(op)

    objects = state["objects"]
    for rn in objects.get("ads", []):
        update("ad_group_ad_operation", rn, "AdGroupAdStatusEnum")
    for rn in objects.get("ad_groups", []):
        update("ad_group_operation", rn, "AdGroupStatusEnum")
    for rn in objects.get("asset_groups", []):
        update("asset_group_operation", rn, "AssetGroupStatusEnum")
    if ops:
        run_mutate(ctx, customer_id, ops, validate_only=False)
        enabled += [gads_client.oneof(o, "operation") for o in ops]
    ops.clear()
    update("campaign_operation", objects["campaign"], "CampaignStatusEnum")
    run_mutate(ctx, customer_id, ops, validate_only=False)
    enabled.append("campaign")
    return enabled


def activate(ctx: Ctx, plan: dict[str, Any], customer_id: str, confirm: str, confirm_ui: str) -> dict[str, Any]:
    if confirm != "SPEND":
        raise OpsError("activation requires the literal --confirm SPEND")
    if confirm_ui != "REVIEWED":
        raise OpsError("activation requires --confirm-ui REVIEWED after the UI-only checks (policy, destination)")
    state_path = pathlib.Path(plan["state_path"])
    receipt_path = pathlib.Path(str(state_path).replace(".json", ".verified.json"))
    if not receipt_path.is_file():
        raise OpsError("no verification receipt; run verify first")
    receipt = read_json(receipt_path, "verification receipt")
    if receipt["state_sha"] != file_sha(state_path) or receipt["spec_sha"] != plan["spec_sha"]:
        raise OpsError("state or spec changed after verification; verify again")
    state = read_json(state_path, "state")
    if ctx.args.refresh_start:
        start = dt.date.fromisoformat(ctx.args.refresh_start)
        if start < dt.date.today():
            raise OpsError("--refresh-start must be today or later (YYYY-MM-DD, account timezone)")
        op = ctx.client.get_type("MutateOperation")
        c = op.campaign_operation.update
        c.resource_name = state["objects"]["campaign"]
        c.start_date = start.strftime("%Y%m%d")
        ctx.client.copy_from(op.campaign_operation.update_mask, field_mask_pb2.FieldMask(paths=["start_date"]))
        run_mutate(ctx, customer_id, [op], validate_only=False)
    enabled = enable_objects(ctx, customer_id, plan["spec"], state)
    state["activated_at"] = now()
    atomic_json(state_path, state)
    return {"enabled": enabled, "campaign": state["objects"]["campaign"],
            "daily_budget_major": plan["spec"]["campaign"]["daily_budget_micros"] / 1e6,
            "currency": plan["spec"]["currency"]}


def cmd_activate(ctx: Ctx) -> tuple[int, dict]:
    plan_path, plan = load_plan(ctx, ctx.args.plan, PLAN_SCHEMA)
    bind_plan(ctx, plan, ctx.customer_id)
    with lock(pathlib.Path(plan["state_path"])):
        data = activate(ctx, plan, ctx.customer_id, ctx.args.confirm, ctx.args.confirm_ui)
    return 0, envelope("activate", True, "activated", artifacts={"plan": str(plan_path)}, data=data,
                       next_action="Within the hour: campaign.primary_status, ad approval, spend, tracker receipt. "
                                   "Any budget anomaly: pause first, diagnose second.")


def cmd_status(ctx: Ctx) -> tuple[int, dict]:
    plan_path, plan = load_plan(ctx, ctx.args.plan, PLAN_SCHEMA if not ctx.args.bulk else BULK_SCHEMA)
    if ctx.args.bulk:
        items = []
        for item in plan["items"]:
            sp = pathlib.Path(item["state_path"])
            st = read_json(sp, "state") if sp.exists() else None
            items.append({"customer_id": item["customer_id"], "state": str(sp),
                          "built": bool(st and st["objects"].get("campaign")),
                          "in_flight": st.get("in_flight") if st else None,
                          "verified": pathlib.Path(str(sp).replace(".json", ".verified.json")).is_file(),
                          "activated_at": st.get("activated_at") if st else None})
        return 0, envelope("status", True, "reported", artifacts={"plan": str(plan_path)}, data={"items": items})
    sp = pathlib.Path(plan["state_path"])
    st = read_json(sp, "state") if sp.exists() else None
    live = None
    if st and st["objects"].get("campaign"):
        rows = gads_client.search(ctx.client, ctx.customer_id, f"""
            SELECT campaign.status, campaign.primary_status, campaign.primary_status_reasons, campaign.serving_status,
              metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions
            FROM campaign WHERE campaign.resource_name = '{st['objects']['campaign']}' AND segments.date DURING TODAY""")
        if rows:
            r = rows[0]
            live = {"status": r.campaign.status.name, "primary_status": r.campaign.primary_status.name,
                    "reasons": [x.name for x in r.campaign.primary_status_reasons],
                    "serving_status": r.campaign.serving_status.name, "cost_major_today": r.metrics.cost_micros / 1e6,
                    "impressions": r.metrics.impressions, "clicks": r.metrics.clicks, "conversions": r.metrics.conversions}
        else:
            live = {"note": "no rows today (no impressions yet or paused)"}
    return 0, envelope("status", True, "reported", artifacts={"plan": str(plan_path), "state": str(sp)},
                       data={"state": st, "live": live})


# ---------------------------------------------------------------- bulk

def cmd_bulk_plan(ctx: Ctx) -> tuple[int, dict]:
    template = pathlib.Path(ctx.args.template).expanduser().resolve()
    accounts = read_json(pathlib.Path(ctx.args.accounts).expanduser().resolve(), "accounts")
    if not isinstance(accounts, list) or not accounts:
        raise OpsError("accounts file must be a non-empty list of {profile, tag}")
    items = []
    for row in accounts:
        prof_name, prof = ctx.ws.profile(row["profile"])
        customer_id = gads_workspace.normalize_customer(prof["customer_id"])
        if ctx.ws.blocked(customer_id):
            raise OpsError(f"{prof_name}: customer {customer_id} is blocked")
        sub = Ctx(argparse.Namespace(**{**vars(ctx.args), "profile": prof_name}))
        d_path, d_sha = require_doctor(sub, customer_id)
        spec = load_spec(sub, template, str(row.get("tag", prof_name)))
        spec["run_id"] = f"{ctx.args.run}-{row.get('tag', prof_name)}"
        summary = validate_graph(sub, customer_id, spec)
        items.append({"profile": prof_name, "customer_id": customer_id, "tag": row.get("tag", prof_name),
                      "spec": spec, "spec_sha": sha(spec), "doctor_receipt": str(d_path), "doctor_sha": d_sha,
                      "state_path": str(sub.state_path(spec["run_id"], customer_id)), **summary})
    plan = {"schema": BULK_SCHEMA, "created_at": now(), "run": ctx.args.run, "api_version": ctx.ws.api_version,
            "workspace_sha": file_sha(ctx.ws.path), "template": str(template), "items": items}
    plan_path = ctx.plan_dir() / f"bulk-{ctx.args.run}-{sha(items)[:12]}.json"
    atomic_json(plan_path, plan)
    return 0, envelope("bulk-plan", True, "validated", artifacts={"plan": str(plan_path)},
                       data={"items": [{k: v for k, v in i.items() if k not in ("spec",)} for i in items]},
                       next_action=f"googleops bulk-apply --plan {plan_path}")


def cmd_bulk_apply(ctx: Ctx) -> tuple[int, dict]:
    plan_path, plan = load_plan(ctx, ctx.args.plan, BULK_SCHEMA)
    results = []
    for item in plan["items"]:
        sub = Ctx(argparse.Namespace(**{**vars(ctx.args), "profile": item["profile"]}))
        single = {**item, "schema": PLAN_SCHEMA, "run_id": item["spec"]["run_id"], "api_version": plan["api_version"],
                  "workspace_sha": plan["workspace_sha"]}
        state_path = pathlib.Path(item["state_path"])
        try:
            bind_plan(sub, single, item["customer_id"])
            with lock(state_path):
                st = apply_plan(sub, single, item["customer_id"], state_path)
            verified = None
            if ctx.args.verify:
                v = gads_verify.verify(sub.client, item["customer_id"], item["spec"], st)
                verified = v["ok"]
                rp = pathlib.Path(str(state_path).replace(".json", ".verified.json"))
                if v["ok"]:
                    atomic_json(rp, {"schema": "googleops.verified/v1", "created_at": now(),
                                     "state_sha": file_sha(state_path), "spec_sha": item["spec_sha"], "facts": v["facts"]})
                else:
                    rp.unlink(missing_ok=True)
            results.append({"customer_id": item["customer_id"], "ok": True, "campaign": st["objects"].get("campaign"),
                            "verified": verified})
        except OpsError as exc:
            results.append({"customer_id": item["customer_id"], "ok": False, "error": str(exc)[:1500]})
            if not ctx.args.continue_on_error:
                break
    ok = all(r["ok"] for r in results) and len(results) == len(plan["items"])
    return (0 if ok else 1), envelope("bulk-apply", ok, "built_paused" if ok else "partial",
                                      artifacts={"plan": str(plan_path)}, data={"results": results},
                                      next_action="Verify each, then activate one reviewed customer per command.")


def cmd_bulk_activate(ctx: Ctx) -> tuple[int, dict]:
    plan_path, plan = load_plan(ctx, ctx.args.plan, BULK_SCHEMA)
    target = gads_workspace.normalize_customer(ctx.args.customer)
    item = next((i for i in plan["items"] if i["customer_id"] == target), None)
    if item is None:
        raise OpsError(f"customer {target} is not in this bulk plan")
    sub = Ctx(argparse.Namespace(**{**vars(ctx.args), "profile": item["profile"]}))
    single = {**item, "schema": PLAN_SCHEMA, "run_id": item["spec"]["run_id"], "api_version": plan["api_version"],
              "workspace_sha": plan["workspace_sha"]}
    bind_plan(sub, single, target)
    with lock(pathlib.Path(item["state_path"])):
        data = activate(sub, single, target, ctx.args.confirm, ctx.args.confirm_ui)
    return 0, envelope("bulk-activate", True, "activated", artifacts={"plan": str(plan_path)},
                       data={"customer_id": target, **data})


# ---------------------------------------------------------------- read-only helpers

def row_to_dict(row: Any) -> dict[str, Any]:
    from google.protobuf.json_format import MessageToDict
    return MessageToDict(gads_client.raw(row), preserving_proto_field_name=True)


def cmd_report(ctx: Ctx) -> tuple[int, dict]:
    query = ctx.args.gaql
    if any(word in query.upper() for word in (" MUTATE", "INSERT ", "UPDATE ", "DELETE ")):
        raise OpsError("report is read-only GAQL")
    rows = [row_to_dict(r) for r in gads_client.search(ctx.client, ctx.customer_id, query)]
    if ctx.args.out:
        atomic_json(pathlib.Path(ctx.args.out), rows)
    return 0, envelope("report", True, "reported", artifacts={"out": ctx.args.out},
                       data={"rows": rows if not ctx.args.out else len(rows), "count": len(rows)})


def cmd_monitor(ctx: Ctx) -> tuple[int, dict]:
    accounts = []
    for name, prof in ctx.ws.data["profiles"].items():
        if ctx.args.profiles and name not in ctx.args.profiles.split(","):
            continue
        sub = Ctx(argparse.Namespace(**{**vars(ctx.args), "profile": name}))
        entry: dict[str, Any] = {"profile": name, "customer_id": sub.customer_id}
        try:
            cust = gads_client.search(sub.client, sub.customer_id,
                                      "SELECT customer.status, customer.descriptive_name FROM customer")[0].customer
            entry["status"] = cust.status.name
            rows = gads_client.search(sub.client, sub.customer_id, f"""
                SELECT campaign.name, campaign.status, campaign.primary_status, metrics.cost_micros, metrics.clicks,
                  metrics.conversions, metrics.impressions
                FROM campaign WHERE campaign.status != 'REMOVED' AND segments.date DURING {ctx.args.range}""")
            entry["campaigns"] = [{"name": r.campaign.name, "status": r.campaign.status.name,
                                   "primary_status": r.campaign.primary_status.name,
                                   "cost_major": r.metrics.cost_micros / 1e6, "clicks": r.metrics.clicks,
                                   "impressions": r.metrics.impressions, "conversions": r.metrics.conversions}
                                  for r in rows]
            entry["cost_major"] = sum(c["cost_major"] for c in entry["campaigns"])
            disapproved = gads_client.search(sub.client, sub.customer_id, """
                SELECT campaign.name, ad_group_ad.policy_summary.approval_status
                FROM ad_group_ad WHERE ad_group_ad.policy_summary.approval_status = 'DISAPPROVED'
                  AND ad_group_ad.status != 'REMOVED'""")
            entry["disapproved_ads"] = len(disapproved)
            entry["verdict"] = ("SUSPENDED" if entry["status"] != "ENABLED" else
                                "REJECTS" if disapproved else
                                "SPENDING" if entry["cost_major"] > 0 else "IDLE")
        except Exception as exc:  # noqa: BLE001 — a sweep must report every account
            entry["verdict"] = "ERROR"
            entry["error"] = str(exc)[:800]
        accounts.append(entry)
    if ctx.args.jsonl:
        with open(ctx.args.jsonl, "a", encoding="utf-8") as fh:
            for a in accounts:
                fh.write(json.dumps({"at": now(), **a}, default=str) + "\n")
    return 0, envelope("monitor", True, "reported", data={"accounts": accounts})


def cmd_link(ctx: Ctx) -> tuple[int, dict]:
    client = ctx.client
    merchant = str(ctx.args.merchant)
    if ctx.args.link_action == "accept":
        rows = gads_client.search(client, ctx.customer_id, f"""
            SELECT product_link_invitation.resource_name, product_link_invitation.status,
              product_link_invitation.merchant_center.merchant_center_id
            FROM product_link_invitation WHERE product_link_invitation.merchant_center.merchant_center_id = {merchant}""")
        pending = [r for r in rows if r.product_link_invitation.status.name == "PENDING_APPROVAL"]
        if not pending:
            return 1, envelope("link", False, "no_pending_invitation",
                               data={"invitations": [r.product_link_invitation.status.name for r in rows]},
                               next_action="Propose the link from Merchant Center (gmcops link propose) first.")
        svc = client.get_service("ProductLinkInvitationService")
        resp = svc.update_product_link_invitation(
            customer_id=ctx.customer_id, resource_name=pending[0].product_link_invitation.resource_name,
            product_link_invitation_status=client.enums.ProductLinkInvitationStatusEnum.ACCEPTED)
        return 0, envelope("link", True, "accepted", data={"resource_name": resp.resource_name})
    rows = gads_client.search(client, ctx.customer_id, """
        SELECT product_link.product_link_id, product_link.merchant_center.merchant_center_id FROM product_link
        WHERE product_link.type = 'MERCHANT_CENTER'""")
    return 0, envelope("link", True, "reported",
                       data={"linked": [str(r.product_link.merchant_center.merchant_center_id) for r in rows]})


def cmd_workspace_validate(ctx: Ctx) -> tuple[int, dict]:
    return 0, envelope("workspace", True, "valid", data={"path": str(ctx.ws.path), "profile": ctx.profile_name,
                                                          "customer_id": ctx.customer_id,
                                                          "state_dir": str(ctx.state_dir)})


# ---------------------------------------------------------------- cli

def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="googleops", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", help="path to workspace.json or its directory (default: discover upward)")
    ap.add_argument("--profile", help="profile name (default: defaults.profile)")
    ap.add_argument("--json", action="store_true", help="print one result JSON object on stdout")
    sub = ap.add_subparsers(dest="command", required=True)
    w = sub.add_parser("workspace").add_subparsers(dest="workspace_action", required=True)
    w.add_parser("validate")
    sub.add_parser("doctor", help="credential/account/billing/conversion/link preflight + validate_only write probe")
    p = sub.add_parser("plan", help="normalize a spec, validate_only the graph, write a hash-bound plan")
    p.add_argument("--spec", required=True)
    p.add_argument("--tag", help="value substituted for {tag} in the spec")
    p.add_argument("--merchant-receipt", help="gmcops doctor --out receipt for retail kinds (bound to the plan)")
    p.add_argument("--allow-unverified-merchant", action="store_true",
                   help="retail kinds only: plan without a Merchant Center receipt (explicit opt-out)")
    for name in ("apply", "verify"):
        sub.add_parser(name).add_argument("--plan", required=True)
    a = sub.add_parser("activate", help="enable a verified plan; spends")
    a.add_argument("--plan", required=True)
    a.add_argument("--confirm", required=True, help="literal SPEND")
    a.add_argument("--confirm-ui", required=True, help="literal REVIEWED")
    a.add_argument("--refresh-start", help="YYYY-MM-DD campaign start date to set before enabling")
    s = sub.add_parser("status")
    s.add_argument("--plan", required=True)
    s.add_argument("--bulk", action="store_true")
    bp = sub.add_parser("bulk-plan")
    bp.add_argument("--template", required=True)
    bp.add_argument("--accounts", required=True, help="JSON list of {profile, tag}")
    bp.add_argument("--run", required=True)
    ba = sub.add_parser("bulk-apply")
    ba.add_argument("--plan", required=True)
    ba.add_argument("--verify", action="store_true")
    ba.add_argument("--continue-on-error", action="store_true")
    bac = sub.add_parser("bulk-activate")
    bac.add_argument("--plan", required=True)
    bac.add_argument("--customer", required=True)
    bac.add_argument("--confirm", required=True)
    bac.add_argument("--confirm-ui", required=True)
    bac.add_argument("--refresh-start")
    r = sub.add_parser("report", help="read-only GAQL")
    r.add_argument("--gaql", required=True)
    r.add_argument("--out")
    m = sub.add_parser("monitor", help="status/spend/disapproval sweep across profiles")
    m.add_argument("--profiles", help="comma-separated subset")
    m.add_argument("--range", default="TODAY", help="GAQL date literal, e.g. YESTERDAY, LAST_7_DAYS")
    m.add_argument("--jsonl", help="append one line per account to this survival log")
    lk = sub.add_parser("link", help="Merchant Center link state / accept invitation")
    lk.add_argument("link_action", choices=["status", "accept"])
    lk.add_argument("--merchant")
    return ap


COMMANDS = {
    "doctor": cmd_doctor, "plan": cmd_plan, "apply": cmd_apply, "verify": cmd_verify, "activate": cmd_activate,
    "status": cmd_status, "bulk-plan": cmd_bulk_plan, "bulk-apply": cmd_bulk_apply, "bulk-activate": cmd_bulk_activate,
    "report": cmd_report, "monitor": cmd_monitor, "link": cmd_link,
}


def main() -> int:
    args = parser().parse_args()
    for attr in ("refresh_start", "tag", "merchant_receipt", "allow_unverified_merchant"):
        if not hasattr(args, attr):
            setattr(args, attr, None)
    try:
        ctx = Ctx(args)
        if args.command == "workspace":
            code, result = cmd_workspace_validate(ctx)
        else:
            code, result = COMMANDS[args.command](ctx)
    except (OpsError, gads_workspace.WorkspaceError, gads_client.ClientError, gads_build.BuildError) as exc:
        message = exc.args[0] if exc.args else str(exc)
        try:
            error = json.loads(message) if isinstance(message, str) and message.startswith("{") else None
        except ValueError:
            error = None
        code, result = 2, envelope(args.command, False, "rejected",
                                   error=error or {"kind": type(exc).__name__, "message": str(message)})
    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        print(f"[{result['command']}] ok={result['ok']} phase={result['phase']}", file=sys.stderr)
        if result["error"]:
            print(json.dumps(result["error"], indent=2, default=str), file=sys.stderr)
        print(json.dumps({"artifacts": result["artifacts"], "data": result["data"],
                          "next_action": result["next_action"]}, indent=2, ensure_ascii=False, default=str))
    return code


if __name__ == "__main__":
    sys.exit(main())
