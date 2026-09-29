"""gmcops — Merchant Center doctor / products / data sources / Ads link, via Merchant API v1.

Read-heavy by design: the account shell, gates, issues, programs and product statuses are read;
writes are limited to product inputs, data sources, homepage claim, program enable, ToS accept,
and proposing the Ads link. Suspension appeals are not exposed by the API without an allowlist.

Env: GMC_JSON_KEY_FILE (service account added as a user on the Merchant Center account) or
GADS_CLIENT_ID / GADS_CLIENT_SECRET / GMC_REFRESH_TOKEN (OAuth, scope .../auth/content).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import time
from typing import Any

SCOPE = "https://www.googleapis.com/auth/content"
RESULT_SCHEMA = "gmcops.result/v1"
GATES = ("homepage_claimed", "business_info_address", "business_info_phone", "shipping_settings",
         "terms_of_service", "data_source_for_country")


class GmcError(Exception):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def envelope(command: str, ok: bool, phase: str, *, data: dict | None = None, error: dict | None = None,
             next_action: str | None = None, artifacts: dict | None = None) -> dict[str, Any]:
    return {"schema": RESULT_SCHEMA, "ok": ok, "command": command, "phase": phase, "artifacts": artifacts or {},
            "data": data or {}, "error": error, "next_action": next_action}


def credentials():
    key = os.environ.get("GMC_JSON_KEY_FILE")
    if key:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(key, scopes=[SCOPE])
    from google.oauth2.credentials import Credentials
    missing = [k for k in ("GADS_CLIENT_ID", "GADS_CLIENT_SECRET", "GMC_REFRESH_TOKEN") if not os.environ.get(k)]
    if missing:
        raise GmcError(f"set GMC_JSON_KEY_FILE or {', '.join(missing)}")
    return Credentials(None, refresh_token=os.environ["GMC_REFRESH_TOKEN"], client_id=os.environ["GADS_CLIENT_ID"],
                       client_secret=os.environ["GADS_CLIENT_SECRET"], token_uri="https://oauth2.googleapis.com/token",
                       scopes=[SCOPE])


def to_dict(msg: Any) -> Any:
    from google.protobuf.json_format import MessageToDict
    pb = getattr(msg, "_pb", msg)
    return MessageToDict(pb, preserving_proto_field_name=True)


class Gmc:
    def __init__(self, account_id: str):
        if not str(account_id).isdigit():
            raise GmcError("account id must be numeric")
        self.account = str(account_id)
        self.parent = f"accounts/{self.account}"
        self.creds = credentials()
        import google.shopping.merchant_accounts_v1 as acc
        import google.shopping.merchant_datasources_v1 as ds
        import google.shopping.merchant_issueresolution_v1 as ir
        import google.shopping.merchant_products_v1 as pr
        import google.shopping.merchant_reports_v1 as rp
        self.acc, self.ds, self.pr, self.rp, self.ir = acc, ds, pr, rp, ir

    def svc(self, mod: Any, name: str) -> Any:
        return getattr(mod, name)(credentials=self.creds)

    # ---- reads
    def account_info(self) -> dict[str, Any]:
        return to_dict(self.svc(self.acc, "AccountsServiceClient").get_account(name=self.parent))

    def homepage(self) -> dict[str, Any]:
        return to_dict(self.svc(self.acc, "HomepageServiceClient").get_homepage(name=f"{self.parent}/homepage"))

    def business_info(self) -> dict[str, Any]:
        return to_dict(self.svc(self.acc, "BusinessInfoServiceClient").get_business_info(
            name=f"{self.parent}/businessInfo"))

    def shipping(self) -> dict[str, Any]:
        return to_dict(self.svc(self.acc, "ShippingSettingsServiceClient").get_shipping_settings(
            name=f"{self.parent}/shippingSettings"))

    def tos_state(self, country: str | None) -> dict[str, Any]:
        """Merchant Center ToS state for a country (MERCHANT_CENTER-US). Without a country only the
        application-data ToS is readable, which is not the Merchant Center agreement."""
        svc = self.svc(self.acc, "TermsOfServiceAgreementStateServiceClient")
        if country:
            return to_dict(svc.get_terms_of_service_agreement_state(
                name=f"{self.parent}/termsOfServiceAgreementState/MERCHANT_CENTER-{country.upper()}"))
        return {"_note": "application ToS only; pass --country for the Merchant Center agreement",
                **to_dict(svc.retrieve_for_application_terms_of_service_agreement_state(parent=self.parent))}

    def programs(self) -> list[dict[str, Any]]:
        return [to_dict(p) for p in self.svc(self.acc, "ProgramsServiceClient").list_programs(parent=self.parent)]

    def issues(self) -> list[dict[str, Any]]:
        return [to_dict(i) for i in self.svc(self.acc, "AccountIssueServiceClient").list_account_issues(
            parent=self.parent)]

    def services(self) -> list[dict[str, Any]]:
        return [to_dict(s) for s in self.svc(self.acc, "AccountServicesServiceClient").list_account_services(
            parent=self.parent)]

    def data_sources(self) -> list[dict[str, Any]]:
        return [to_dict(d) for d in self.svc(self.ds, "DataSourcesServiceClient").list_data_sources(parent=self.parent)]

    def sub_accounts(self) -> list[dict[str, Any]]:
        return [to_dict(a) for a in self.svc(self.acc, "AccountsServiceClient").list_sub_accounts(provider=self.parent)]

    def report(self, query: str) -> list[dict[str, Any]]:
        req = self.rp.SearchRequest(parent=self.parent, query=query, page_size=1000)
        return [to_dict(r) for r in self.svc(self.rp, "ReportServiceClient").search(request=req)]

    def product(self, name: str) -> dict[str, Any]:
        return to_dict(self.svc(self.pr, "ProductsServiceClient").get_product(name=name))

    # ---- writes
    def insert_product(self, data_source: str, product_input: dict[str, Any]) -> dict[str, Any]:
        req = self.pr.InsertProductInputRequest(parent=self.parent, data_source=data_source,
                                                product_input=self.pr.ProductInput(product_input))
        return to_dict(self.svc(self.pr, "ProductInputsServiceClient").insert_product_input(request=req))

    def create_api_data_source(self, display_name: str, feed_label: str | None, language: str | None,
                               countries: list[str]) -> dict[str, Any]:
        primary: dict[str, Any] = {"countries": countries} if countries else {}
        if feed_label:
            primary["feed_label"] = feed_label
        if language:
            primary["content_language"] = language
        source = self.ds.DataSource(display_name=display_name, primary_product_data_source=primary)
        return to_dict(self.svc(self.ds, "DataSourcesServiceClient").create_data_source(
            parent=self.parent, data_source=source))

    def claim_homepage(self, overwrite: bool) -> dict[str, Any]:
        req = self.acc.ClaimHomepageRequest(name=f"{self.parent}/homepage", overwrite=overwrite)
        return to_dict(self.svc(self.acc, "HomepageServiceClient").claim_homepage(request=req))

    def enable_program(self, program: str) -> dict[str, Any]:
        return to_dict(self.svc(self.acc, "ProgramsServiceClient").enable_program(
            name=f"{self.parent}/programs/{program}"))

    def accept_tos(self, region: str) -> dict[str, Any]:
        tos = self.svc(self.acc, "TermsOfServiceServiceClient")
        latest = tos.retrieve_latest_terms_of_service(request=self.acc.RetrieveLatestTermsOfServiceRequest(
            region_code=region, kind=self.acc.TermsOfServiceKind.MERCHANT_CENTER))
        tos.accept_terms_of_service(request=self.acc.AcceptTermsOfServiceRequest(
            name=latest.name, account=self.parent, region_code=region))
        return {"accepted": latest.name, "region": region}

    def propose_ads_link(self, ads_customer_id: str) -> dict[str, Any]:
        service = self.acc.AccountService(campaigns_management={}, provider=f"providers/{ads_customer_id}")
        req = self.acc.ProposeAccountServiceRequest(parent=self.parent, provider=f"providers/{ads_customer_id}",
                                                    account_service=service)
        return to_dict(self.svc(self.acc, "AccountServicesServiceClient").propose_account_service(request=req))


# ---------------------------------------------------------------- commands

def cmd_doctor(g: Gmc, args: argparse.Namespace) -> tuple[int, dict]:
    problems: list[str] = []
    data: dict[str, Any] = {"account": g.account_info()}
    gates: dict[str, Any] = {}

    def safe(label: str, fn):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — every gate reports independently
            data.setdefault("errors", {})[label] = str(exc)[:400]
            return None

    hp = safe("homepage", g.homepage)
    gates["homepage_claimed"] = bool(hp and hp.get("claimed"))
    data["homepage"] = hp
    bi = safe("business_info", g.business_info) or {}
    data["business_info"] = bi
    gates["business_info_address"] = bool(bi.get("address"))
    gates["business_info_phone"] = bi.get("phone_verification_state") == "VERIFIED"
    sh = safe("shipping", g.shipping) or {}
    gates["shipping_settings"] = bool(sh.get("services"))
    data["shipping_services"] = len(sh.get("services", []))
    tos = safe("tos", lambda: g.tos_state(args.country)) or {}
    data["terms_of_service"] = tos
    gates["terms_of_service"] = bool(args.country) and bool(tos) and not tos.get("required") and bool(tos.get("accepted"))
    sources = safe("data_sources", g.data_sources) or []
    data["data_sources"] = [{"name": s.get("name"), "display_name": s.get("display_name"), "input": s.get("input"),
                             "primary": s.get("primary_product_data_source")} for s in sources]
    country = args.country
    gates["data_source_for_country"] = any(
        s.get("primary_product_data_source") is not None and (
            not country or not s["primary_product_data_source"].get("countries")
            or country in s["primary_product_data_source"]["countries"]) for s in sources)
    data["gates"] = gates
    problems += [f"gate {k} not satisfied" for k, v in gates.items() if not v]
    if country == "US":
        problems.append("US tax settings are not readable through Merchant API — confirm in the UI (gate 5)")
    programs = safe("programs", g.programs) or []
    data["programs"] = [{"name": p.get("name", "").rsplit("/", 1)[-1], "state": p.get("state"),
                         "unmet": p.get("unmet_requirements", [])} for p in programs]
    for p in data["programs"]:
        if p["name"] in ("shopping-ads", "free-listings") and p["state"] != "ENABLED":
            problems.append(f"program {p['name']} is {p['state']}: {p['unmet']}")
    issues = safe("issues", g.issues) or []
    data["issues"] = [{"id": i.get("name", "").rsplit("/", 1)[-1], "severity": i.get("severity"), "title": i.get("title"),
                       "detail": (i.get("detail") or "")[:300], "doc": i.get("documentation_uri")} for i in issues]
    for i in data["issues"]:
        if i["severity"] == "CRITICAL":
            problems.append(f"CRITICAL account issue: {i['id']} — {i['title']}")
    services = safe("services", g.services) or []
    data["ads_links"] = [{"provider": s.get("provider"), "display": s.get("provider_display_name"),
                          "state": (s.get("handshake") or {}).get("approval_state")} for s in services
                         if "campaigns_management" in s]
    if args.ads_customer and not any(str(args.ads_customer) in (link["provider"] or "") and link["state"] == "ESTABLISHED"
                                     for link in data["ads_links"]):
        problems.append(f"Ads customer {args.ads_customer} link not ESTABLISHED (propose with: gmcops link propose)")
    try:
        rows = g.report("SELECT aggregated_reporting_context_status FROM product_view")
        counts: dict[str, int] = {}
        for r in rows:
            k = (r.get("product_view") or {}).get("aggregated_reporting_context_status", "UNKNOWN")
            counts[k] = counts.get(k, 0) + 1
        data["products_by_status"] = counts
        if counts and not counts.get("ELIGIBLE") and not counts.get("ELIGIBLE_LIMITED"):
            problems.append("no eligible products")
    except Exception as exc:  # noqa: BLE001
        data.setdefault("errors", {})["product_view"] = str(exc)[:400]
    ok = not problems
    receipt = {"schema": "gmcops.doctor/v1", "created_at": now(), "account": g.account, "ok": ok, "data": data,
               "problems": problems}
    if args.out:
        path = pathlib.Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(receipt, indent=2, default=str))
    return (0 if ok else 1), envelope("doctor", ok, "ready" if ok else "blocked", data={**data, "problems": problems},
                                      artifacts={"receipt": args.out},
                                      next_action=None if ok else "Fix gates/issues in the UI or via gmcops writes; "
                                                                  "account issues are re-reviewed by Google after edits.")


def cmd_products(g: Gmc, args: argparse.Namespace) -> tuple[int, dict]:
    if args.products_action == "status":
        where = f" WHERE aggregated_reporting_context_status = '{args.status}'" if args.status else ""
        rows = g.report("SELECT id, offer_id, feed_label, title, aggregated_reporting_context_status, "
                        f"status_per_reporting_context, item_issues FROM product_view{where}")
        items = [r.get("product_view") for r in rows]
        if args.out:
            pathlib.Path(args.out).write_text(json.dumps(items, indent=2, default=str))
        return 0, envelope("products", True, "reported", data={"count": len(items),
                                                              "items": items if not args.out else None},
                           artifacts={"out": args.out})
    if args.products_action == "get":
        return 0, envelope("products", True, "reported", data=g.product(f"{g.parent}/products/{args.name}"))
    if args.products_action == "insert":
        payload = json.loads(pathlib.Path(args.file).read_text())
        items = payload if isinstance(payload, list) else [payload]
        results = []
        for item in items:
            for key in ("offer_id", "content_language", "feed_label", "product_attributes"):
                if key not in item:
                    raise GmcError(f"product input missing {key}")
            attrs = item["product_attributes"]
            for key in ("title", "link", "image_link", "availability", "price"):
                if key not in attrs:
                    raise GmcError(f"{item['offer_id']}: product_attributes missing {key}")
            if "sale_price" in attrs and "price" not in attrs:
                raise GmcError(f"{item['offer_id']}: sale_price without price is a misrepresentation trigger")
            results.append(g.insert_product(args.data_source, item))
        names = [r.get("name") for r in results]
        polled = None
        if args.wait:
            polled = []
            deadline = time.time() + args.wait
            for name in names:
                product_name = name.replace("/productInputs/", "/products/")
                status = None
                while time.time() < deadline:
                    try:
                        status = g.product(product_name).get("product_status")
                        break
                    except Exception:  # noqa: BLE001 — processing delay is "several minutes"
                        time.sleep(20)
                polled.append({"name": product_name, "status": status})
        return 0, envelope("products", True, "inserted", data={"inputs": names, "status": polled},
                           next_action="Processed product appears after several minutes; rerun products get/status.")
    raise GmcError("unknown products action")


def cmd_datasources(g: Gmc, args: argparse.Namespace) -> tuple[int, dict]:
    if args.ds_action == "list":
        return 0, envelope("datasources", True, "reported", data={"data_sources": g.data_sources()})
    if args.ds_action == "create-api":
        created = g.create_api_data_source(args.display_name, args.feed_label, args.language,
                                           args.countries.split(",") if args.countries else [])
        return 0, envelope("datasources", True, "created", data=created,
                           next_action=f"gmcops products insert --data-source {created.get('name')} --file items.json")
    raise GmcError("unknown datasources action")


def cmd_account(g: Gmc, args: argparse.Namespace) -> tuple[int, dict]:
    if args.account_action == "claim-homepage":
        if args.overwrite and args.confirm != "OVERWRITE":
            raise GmcError("--overwrite takes the claim away from another account and breaks its feeds; "
                           "pass --confirm OVERWRITE")
        return 0, envelope("account", True, "claimed", data=g.claim_homepage(args.overwrite))
    if args.account_action == "enable-program":
        return 0, envelope("account", True, "enabled", data=g.enable_program(args.program))
    if args.account_action == "accept-tos":
        return 0, envelope("account", True, "accepted", data=g.accept_tos(args.region))
    if args.account_action == "sub-accounts":
        return 0, envelope("account", True, "reported", data={"sub_accounts": g.sub_accounts()})
    raise GmcError("unknown account action")


def cmd_link(g: Gmc, args: argparse.Namespace) -> tuple[int, dict]:
    if args.link_action == "propose":
        if not str(args.ads_customer).isdigit():
            raise GmcError("--ads-customer must be the 10-digit Ads customer id")
        return 0, envelope("link", True, "proposed", data=g.propose_ads_link(args.ads_customer),
                           next_action=f"Accept on the Ads side: googleops link accept --merchant {g.account}")
    return 0, envelope("link", True, "reported", data={"services": g.services()})


def cmd_report(g: Gmc, args: argparse.Namespace) -> tuple[int, dict]:
    rows = g.report(args.mcql)
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(rows, indent=2, default=str))
    return 0, envelope("report", True, "reported", data={"count": len(rows), "rows": rows if not args.out else None},
                       artifacts={"out": args.out})


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="gmcops", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", required=True, help="Merchant Center account id (sub-account for a portfolio)")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="command", required=True)
    d = sub.add_parser("doctor", help="gates, programs, account issues, Ads link, product status counts")
    d.add_argument("--country", help="target country for the data-source gate, e.g. US")
    d.add_argument("--ads-customer", help="Ads customer id expected to be linked")
    d.add_argument("--out", help="write the receipt JSON here")
    p = sub.add_parser("products").add_subparsers(dest="products_action", required=True)
    st = p.add_parser("status")
    st.add_argument("--status", help="filter aggregated_reporting_context_status, e.g. NOT_ELIGIBLE_OR_DISAPPROVED")
    st.add_argument("--out")
    p.add_parser("get").add_argument("--name", required=True, help="contentLanguage~feedLabel~offerId")
    ins = p.add_parser("insert")
    ins.add_argument("--data-source", required=True, help="accounts/{id}/dataSources/{id} (API input type)")
    ins.add_argument("--file", required=True, help="one ProductInput JSON object or a list")
    ins.add_argument("--wait", type=int, default=0, help="seconds to poll for the processed product")
    ds = sub.add_parser("datasources").add_subparsers(dest="ds_action", required=True)
    ds.add_parser("list")
    c = ds.add_parser("create-api")
    c.add_argument("--display-name", required=True)
    c.add_argument("--feed-label")
    c.add_argument("--language")
    c.add_argument("--countries", help="comma-separated CLDR codes")
    a = sub.add_parser("account").add_subparsers(dest="account_action", required=True)
    ch = a.add_parser("claim-homepage")
    ch.add_argument("--overwrite", action="store_true")
    ch.add_argument("--confirm")
    a.add_parser("enable-program").add_argument("--program", required=True,
                                                help="shopping-ads | free-listings | product-ratings | checkout")
    a.add_parser("accept-tos").add_argument("--region", required=True)
    a.add_parser("sub-accounts")
    lk = sub.add_parser("link")
    lk.add_argument("link_action", choices=["status", "propose"])
    lk.add_argument("--ads-customer")
    r = sub.add_parser("report", help="read-only Merchant Center Query Language")
    r.add_argument("--mcql", required=True)
    r.add_argument("--out")
    return ap


COMMANDS = {"doctor": cmd_doctor, "products": cmd_products, "datasources": cmd_datasources, "account": cmd_account,
            "link": cmd_link, "report": cmd_report}


def main() -> int:
    args = parser().parse_args()
    try:
        g = Gmc(args.account)
        code, result = COMMANDS[args.command](g, args)
    except GmcError as exc:
        code, result = 2, envelope(args.command, False, "rejected", error={"kind": "GmcError", "message": str(exc)})
    except Exception as exc:  # noqa: BLE001 — surface API errors as JSON
        code, result = 1, envelope(args.command, False, "api_error",
                                   error={"kind": type(exc).__name__, "message": str(exc)[:2000]})
    if args.json:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        print(f"[{result['command']}] ok={result['ok']} phase={result['phase']}", file=sys.stderr)
        print(json.dumps({k: result[k] for k in ("data", "error", "next_action")}, indent=2, ensure_ascii=False,
                         default=str))
    return code


if __name__ == "__main__":
    sys.exit(main())
