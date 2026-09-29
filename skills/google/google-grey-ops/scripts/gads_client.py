"""Google Ads client factory. Credentials come from the environment only.

Env:
  GADS_DEVELOPER_TOKEN            required
  GADS_CLIENT_ID / GADS_CLIENT_SECRET / GADS_REFRESH_TOKEN   oauth (installed-app refresh token)
  GADS_JSON_KEY_FILE              service_account (key file; the SA email must be added as a user
                                  in Admin > Access and security of the MCC — no domain-wide delegation)
  GADS_PROXY                      http(s)://host:port, applied as grpc_proxy for every call
  GADS_ALLOW_NO_PROXY=1           explicit opt-out when direct egress is the intended identity
"""

from __future__ import annotations

import os
from typing import Any


class ClientError(Exception):
    pass


def _env(name: str, required: bool = False) -> str | None:
    value = os.environ.get(name)
    if required and not value:
        raise ClientError(f"{name} is not set")
    return value


def egress_check() -> str:
    proxy = _env("GADS_PROXY")
    if proxy:
        os.environ.setdefault("grpc_proxy", proxy)
        os.environ.setdefault("https_proxy", proxy)
        return "proxy"
    if _env("GADS_ALLOW_NO_PROXY") == "1":
        return "direct"
    raise ClientError("set GADS_PROXY (identity egress) or GADS_ALLOW_NO_PROXY=1 to confirm direct egress")


def build_client(login_customer_id: str, api_version: str, auth: str = "oauth") -> Any:
    from google.ads.googleads.client import GoogleAdsClient

    egress_check()
    config: dict[str, Any] = {
        "developer_token": _env("GADS_DEVELOPER_TOKEN", required=True),
        "login_customer_id": login_customer_id,
        "use_proto_plus": True,
    }
    if auth == "service_account":
        config["json_key_file_path"] = _env("GADS_JSON_KEY_FILE", required=True)
    else:
        config["client_id"] = _env("GADS_CLIENT_ID", required=True)
        config["client_secret"] = _env("GADS_CLIENT_SECRET", required=True)
        config["refresh_token"] = _env("GADS_REFRESH_TOKEN", required=True)
    return GoogleAdsClient.load_from_dict(config, version=api_version)


def offline_client(api_version: str) -> Any:
    """Client with dummy credentials: builds protos and enums, never calls the API."""
    from google.ads.googleads.client import GoogleAdsClient
    from google.oauth2.credentials import Credentials

    return GoogleAdsClient(
        credentials=Credentials(token="offline"),
        developer_token="offline",
        login_customer_id="0000000000",
        version=api_version,
        use_proto_plus=True,
    )


def raw(msg: Any) -> Any:
    """Underlying protobuf message for a proto-plus wrapper (or the message itself)."""
    return getattr(msg, "_pb", msg)


def oneof(msg: Any, name: str) -> str | None:
    return raw(msg).WhichOneof(name)


def failure_details(exc: Any) -> dict[str, Any]:
    """Flatten a GoogleAdsException into JSON."""
    errors = []
    failure = getattr(exc, "failure", None)
    for err in getattr(failure, "errors", []) or []:
        code = err.error_code
        which = raw(code).WhichOneof("error_code")
        name = getattr(getattr(code, which), "name", None) if which else None
        path = ".".join(
            f"{el.field_name}[{el.index}]" if el.HasField("index") else el.field_name
            for el in err.location.field_path_elements
        )
        errors.append({"code": f"{which}.{name}" if which else str(code), "message": err.message,
                       "path": path, "trigger": str(err.trigger)[:200] if err.trigger else None})
    return {"request_id": getattr(exc, "request_id", None), "errors": errors}


def search(client: Any, customer_id: str, query: str) -> list[Any]:
    service = client.get_service("GoogleAdsService")
    rows: list[Any] = []
    for batch in service.search_stream(customer_id=customer_id, query=query):
        rows.extend(batch.results)
    return rows
