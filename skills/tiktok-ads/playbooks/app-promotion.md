# App promotion (installs, in-app events, SKAN, Minis)

## Gate

Open, subject to the app's own category (a gambling or finance app inherits that vertical's gate —
`08`). iOS adds a structural layer that is not a policy gate but shapes everything.

## Campaign setup specifics

`objective_type: APP_PROMOTION` **requires `app_promotion_type`**:
`APP_INSTALL` · `APP_RETARGETING` · `APP_PREREGISTRATION` (allowlist-only).

`campaign_type`: `REGULAR_CAMPAIGN` or `IOS14_CAMPAIGN` (Dedicated Campaign, which carries quota
limits). `APP_RETARGETING` and `APP_PREREGISTRATION` can only be `REGULAR_CAMPAIGN`.

**TikTok Minis** (`app_promotion_type: MINIS` — mini games, mini dramas) is a 2026 sub-product under
Upgraded Smart+, absent from most third-party guides (`03`).

## Measurement is the whole game

- **MMPs**: Adjust, Airbridge, AppsFlyer, Branch, Kochava, Singular.
- **The legacy MMP postback flow was discontinued 31 March 2025**, replaced by mandatory **SAN**
  direct integration. Tutorials teaching token-based postback setup — including recent video
  material — are stale on this point (`07`, `11`).
- **SKAN 4.0**: the fine-grained schema is usually auto-copied on migration, *"not guaranteed — must
  be confirmed"*; the **coarse schema must be configured manually**, materially reduces null rates,
  and unlocks the 2nd and 3rd postback windows.
- **App attribution windows under SKAN 4 are 2, 7 and 35 days** — do not conflate with web CTA/VTA.
- `postback_window_mode` on a disabled iOS14 campaign determines which postback is secured and **how
  long campaign quota is held** (up to 41 days for mode 3). Set it deliberately.
- `disable_skan_campaign` (allowlist) trades SKAN metrics for SAN metrics and exemption from
  Dedicated Campaign quota.

## Optimization goals and deep bidding

`INSTALL` (install) · `IN_APP_EVENT` (AEO) · `VALUE` (VBO).

**"Install with in-app event" is no longer creatable on TikTok placement or Automatic Placement**
(since Nov 2024) — only on Pangle and Global App Bundle. Existing ad groups are unaffected. A plan
that assumes it on TikTok placement will fail at create.

`deep_bid_type` for app: `MIN` (double bid — holds install cost *and* event cost near target, costs
install volume) · `PACING` (holds install cost near target, maximises events, event cost runs higher)
· `AEO` · `VO_MIN_ROAS` / `VO_HIGHEST_VALUE` for value.

**VBO unlock for app: ≥30 unique Purchase events with value in any consecutive 7 days** (standard
placements), or **≥50 lifetime** for Pangle-only plus separate allowlisting (`05`).

From end of September 2026, **non-CBO App Install VBO Smart+ campaigns can no longer be created via
API** — TikTok says they delivered significantly worse (`03`).

## Numbers to get from the operator

- Payout event: install, or a specific in-app event, or revenue.
- **D0/D1/D7 event rates and retention** — decides whether AEO or VBO is even reachable.
- LTV by GEO, and the LTV:CAC target.
- MMP in use, and **whether SAN integration is actually live** (not "configured").
- iOS vs Android split — they are effectively two different measurement regimes.

## TikTok-specific failure modes

- Optimizing on installs when payout is on an in-app event, then discovering install quality is the
  whole variance.
- SKAN coarse schema left unconfigured — high null rates that look like poor performance.
- Assuming "install with in-app event" works on TikTok placement (it does not).
- Pangle blended into a TikTok-placement ad group: cheap installs flatter the blended CPI while
  contributing nothing. **Break out by placement before judging** (`04`).
- Global App Bundle creative specs differ from TikTok in-feed — different resolution floors, no
  emoji, 50 KB profile image (`06`).

## Shape of the derivation

App category gate → iOS vs Android measurement regime → MMP and SAN live? → payout event → optimization
goal and deep bid from D0/D7 event volume → VBO reachable? → placement strategy with Pangle broken out
→ SKAN schema configured → structure from readable tests → judging window from the event's lag.
