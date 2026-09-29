# 11 — Google Ads API error catalog

Reviewed 2026-08-27. Code → cause → fix. Setup and mutate patterns → `10-api-and-automation.md`.

## Reading a failure

`GoogleAdsFailure.errors[]`, each carrying `error_code`, `message`, `trigger`, and
`location.field_path_elements[]`. The response also carries a top-level **`request_id`**.

**Always log `request_id`** — it is the only thing Google support can act on.

```python
try:
    response = ga_service.mutate(customer_id=cid, mutate_operations=ops)
except GoogleAdsException as ex:
    print(f"request_id: {ex.request_id}")
    for error in ex.failure.errors:
        print(f"  {error.error_code} — {error.message}")
        for el in error.location.field_path_elements:
            print(f"    field: {el.field_name}, index: {getattr(el, 'index', None)}")
```

For partial-failure responses the errors are protobuf `Any` values that must be deserialized — see
`10-api-and-automation.md`.

## Catalog

| Family | Values | Cause | Fix |
|---|---|---|---|
| **AuthenticationError** | `OAUTH_TOKEN_INVALID`, `OAUTH_TOKEN_EXPIRED`, `NOT_ADS_USER` | Bad or expired refresh token; the OAuth account has no Ads access at all | Re-run OAuth consent. **Check whether the consent screen is still in Testing status — refresh tokens expire after 7 days there.** Confirm the token's account is invited to at least one Ads/MCC account |
| **AuthorizationError** | `DEVELOPER_TOKEN_NOT_APPROVED`, `USER_PERMISSION_DENIED`, `CUSTOMER_NOT_ENABLED` | Test-tier token hitting a production account; caller lacks a role on the target customer; account suspended or not fully set up | **Check `login-customer-id` first — it is the most common cause.** Then the MCC link, the access tier vs account type, and account status in the UI |
| **QuotaError** | `RESOURCE_EXHAUSTED`, `RESOURCE_TEMPORARILY_EXHAUSTED` | Daily op cap hit or a short-term rate spike | Exponential backoff, never hot-loop. Apply for Standard access if chronically at Basic's 15k/day |
| **RequestError** | `RESOURCE_NOT_FOUND`, `INVALID_CUSTOMER_ID`, `EXPIRED_PAGE_TOKEN` | Malformed customer id, stale pagination token, resource deleted mid-query | Validate ids before sending. **Prefer `SearchStream` to sidestep page-token expiry entirely** |
| **PolicyViolationError / PolicyFindingError** | Ad or keyword text triggers a policy finding | Text matches a policy pattern (trademark, restricted content) | Exemption flow below, or edit the text |
| **CriterionError** | `INVALID_KEYWORD_TEXT`, `KEYWORD_TEXT_TOO_LONG`, `DUPLICATE_CRITERION` | Malformed or duplicated criterion | Normalize and dedupe before mutate; respect the 80-char / 16-word negative limits (`03`) |
| **AdError** | `HEADLINE_TOO_LONG`, `DESCRIPTION_TOO_LONG`, `MISSING_FINAL_URL`, `INVALID_ASSET_TYPE` | RSA text or URL fails schema (30-char headlines, 90-char descriptions) | Validate character counts **client-side** before mutate, then `validate_only` |
| **ResourceCountLimitExceeded** | — | Structural cap hit (keywords per campaign, negatives per shared set, asset groups per campaign) | Query current counts via GAQL before adding; split across more containers. Caps in `01` and `07` |
| **MutateError** | `RESOURCE_NOT_FOUND`, `MUTATE_NOT_ALLOWED`, `INVALID_STATUS_CHANGE` | Target does not exist, or its state disallows the mutation (cannot ENABLE a REMOVED entity) | Query current status first. Never mutate a resource you have not just confirmed exists |
| **FieldError** | `REQUIRED`, `IMMUTABLE_FIELD`, `INVALID_VALUE` | A newly-mandatory field is missing, or an immutable field is being changed | Diff against the current version's required-field list on every major upgrade. **Immutable fields (e.g. `campaign.advertising_channel_type`) cannot be changed — recreate the resource** |
| **DateError** | `INVALID_DATE`, `DATE_RANGE_TOO_WIDE`, `EARLIER_THAN_MINIMUM_DATE` | Malformed date filter or an unsupported range width | Use documented literals or `BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'`; check the resource's max lookback |
| **QueryError** | — | Fields not mutually `selectableWith`; attempted join of independent resources | Check compatibility via `GoogleAdsFieldService` (`10`) |

### Version-migration errors

`FieldError.REQUIRED` on ad creation that previously worked is the signature of the **v24** change
making `videos` and `logo_images` mandatory on `DemandGenVideoResponsiveAdInfo` and
`VideoResponsiveAdInfo`.

Type errors on `customer_metrics` are the signature of **v25** changing it from generic `Metrics` to
specialized `CustomerMetrics`.

**The dangerous case throws nothing.** Major versions remove fields — a query hardcoded to an older
field set can return **200 OK with silently missing data**. Add field-presence assertions to report
parsing, not only error handling.

## Offline conversion upload errors

| Enum | Cause | Fix |
|---|---|---|
| `INVALID_CONVERSION_DATE_TIME` | Missing or malformed timezone offset | Format is `yyyy-mm-dd HH:mm:ss±HH:mm` — a **space, not `T`**, and the offset is mandatory |
| `EXPIRED_CLICK` | Past the 90-day (gclid) or 63-day (EC for Leads) window | Upload an in-window proxy event and true up with adjustments (**54-day** window; 55 is Hotel Ads only) |
| `CONVERSION_PRECEDES_CLICK` | Conversion timestamp is before the click | **Almost always a timezone reconciliation bug** — normalize tracker and network timestamps to one explicit offset before building the payload |
| `TOO_RECENT_CONVERSION_ACTION` | Uploaded before the conversion action finished propagating | Wait after creating the action; retry |
| `CONVERSION_ALREADY_EXISTS` / `CLICK_CONVERSION_ALREADY_EXISTS` | Duplicate within the dedup window | Dedup key is **gclid + conversion action + date/time**. `order_id` is **not** a dedup key for standard gclid imports — dedup in your own system first |
| `INVALID_EMAIL` / `INVALID_PHONE_NUMBER` | Bad normalization | Lowercase, trim, E.164 phones, SHA-256 lowercase hex. Gmail dot-stripping applies **only** to gmail.com/googlemail.com |
| `MISSING_CONVERSION_ACTION` | Wrong action type or not found | The action must be of type **UPLOAD_CLICKS** |
| `TOO_MANY_CONVERSIONS_IN_REQUEST` | >2,000 per request | Chunk |

**Silent drops are the real hazard.** Rows past the backdate window are dropped without an error in
some paths. Always set `partial_failure = True`, iterate `partial_failure_error`, reconcile accepted vs
rejected counts against the CRM export nightly. A pipeline that never checks looks healthy while
delivering nothing.

## Policy exemption flow

1. Submit the mutate normally.
2. On failure, `PolicyViolationDetails` carries a `key` (`PolicyViolationKey`) per finding plus an
   **`is_exemptible`** flag.
3. If exemptible, resubmit the **same** operation with
   `policy_violation_parameters.exempt_policy_violation_keys[]` populated from the returned keys. This
   requests an exemption review instead of blocking.
4. **If a finding is not exemptible, no code path fixes it.** Edit the text.

```python
except GoogleAdsException as ex:
    exempt_keys = []
    for error in ex.failure.errors:
        details = error.details.policy_violation_details
        if error.error_code.policy_violation_error and details.is_exemptible:
            exempt_keys.append(details.key)
    if exempt_keys:
        op.create.policy_violation_parameters.exempt_policy_violation_keys.extend(exempt_keys)
        response = service.mutate_ad_group_criteria(customer_id=cid, operations=[op])
```

Exemption requests a **review**. It is not a bypass, and it does not apply to account-level
enforcement. Policy tiers and what is appealable → `09-policy-and-compliance.md`.

## Quota and limit errors

| Enum | Limit |
|---|---|
| `TOO_MANY_MUTATE_OPERATIONS` | 10,000 per request |
| `TOO_MANY_ACTION_OPERATIONS` | 100 per request |
| `TOO_MANY_CONVERSIONS_IN_REQUEST` | 2,000 |
| `TOO_MANY_ADJUSTMENTS_IN_REQUEST` | 2,000 |
| `RESOURCE_EXHAUSTED` (64MB) | gRPC max response — narrow the query or paginate |

A failed request returning a `GoogleAdsFailure` **still counts against daily quota**. Network-level
failures and paginated page fetches do not.

## Triage order

1. **`request_id` logged?** If not, fix that first — you are debugging blind.
2. **Auth or authorization?** Check `login-customer-id` before anything else.
3. **Does the resource exist right now?** Query it. Do not assume.
4. **Would `validate_only` have caught this?** If yes, the pipeline is missing its guardrail — fix the
   pipeline, not just this call.
5. **Did a version bump change a required or removed field?** Check the last three majors in `10`.
6. **Is it policy?** Check `is_exemptible` before editing text.
