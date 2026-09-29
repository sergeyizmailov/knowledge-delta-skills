# 06 — Advertiser verification, video selfie, BOV

Reviewed 2026-08-27. Policy taxonomy → `google-ads/09`. Account supply → `01`. Payments → `02`.
Cloak/replacement → `05`. Grey overlay: how identity gates actually fire, which "pass" paths are
live vs CS.

**Load-bearing official split:** honest fail = pause/retry. **False information = Circumventing
systems** (egregious, cascade). 3 failed identity attempts on the **appeal** path → no further
appeal. Photoshop/redacted gov ID = CS (Nov 2025 examples). No version where fabrication is the
lower-risk path.

Vendor selfie/liveness claims are **not** Google Ads docs. Google does **not** name the Ads selfie
vendor (Jumio/Onfido/Persona/in-house = **unknown**).

## Do not conflate products

| Product | What it is | Ads? |
|---|---|---|
| Google Ads AIV + video selfie | Payments-profile admin, gov ID + selfie | **Yes** |
| Google Account recovery selfie (Jul 2026) | In-house, turn L/R / chin up; deepfake claims | **No** |
| GBP walkthrough video | Business Profile | **No** |
| Merchant Center operator video | FeedShield lore: 3 attempts | **No** |

Importing Account-recovery choreography (blink/turn/smile) as an Ads SOP is how
blogs go wrong.

## AIV task split (official, fetched 2026-08-27)

UI: Admin → Policy → **Account** (old “Advertiser verification”). Only the Ads
admin starts it. `IdentityVerificationService` is the API surface (`google-ads/09`).

| Path | Tasks | Selfie? |
|---|---|---|
| **Individual** | Gov photo ID; SMS 6-digit (**area code = payments-profile country**, phone deleted after); **US SSN** (3 fails → ID; fail-all on appeal → **no appeal**); **video selfie** | **Yes.** Payments-profile **admin only**. 5 ID↔selfie mismatches → contact support |
| **Organization** | D-U-N-S (3 fails → docs); registration docs + authorized-rep photo ID; affiliation via SMS or **org email** | **Not listed** — this is the selfie skip |
| **Agency / Grants** | Agency identity **plus** client identity (send link or complete for client) | Client path depends on client type |

**US individual IDs that pass:** passport, state ID, driving license, Green card.
**Residence permit is not on the US individual list.** EEA pages add national ID /
residence permit / visa. Individual ID **must be issued in payments-profile
country** (EEA: any EEA issuer). Authorized-rep ID for orgs: **any country**.

**US org docs that pass:** IRS CP575 / 147C / IRS-stamped notice; Forms 8871/990
only if findable on IRS site; **state Certificate of Incorporation**; SEC
10-K/10-Q/8-K; Experian/Equifax/TransUnion **business credit report**. W9 is
**not** on the list.

**Hard fails (official):** blur, missing back, poor light, **self-printed =
photocopy or screenshot**, legal-name mismatch, org-name mismatch,
**payments-profile country ≠ document country**, unsupported type, **digital IDs
not accepted**. Four corners, color, not expired.

Re-verify after **payments profile, billing address, or business information**
change. Legal-name change: docs showing **same legal entity**, new name.
Payments-profile **country or ownership** change: **support only**.

## Video selfie — what is actually known

Official: submit gov ID + video selfie; match after 5 attempts or contact us. **No** vendor name,
**no** blink/turn/smile script, **no** glasses/VPN/virtual-camera list. Privacy line "won't be
shared with any third party" does **not** prove in-house processing.

**Confirmed 2025–26 Google Ads selfie pass via deepfake or camera injection: none found.**
Cybernews (2026-08-26) found an Android injection toolkit and **no evidence any IDV provider
accepted it.**

Industry (not Ads): presentation attacks (print, screen, 2D mask) **mostly dead** against iBeta
L2/L3. **Injection** (virtual camera/native Android camera hook) is the live class (iProov +741%
2025; iOS +1,151% H2 2025). MITRE ATLAS 2025-12: iProov red team evaded a **financial-app**
liveness with OBS + non-rooted Android Virtual Camera + faceswap. **Not transferable to Ads until
someone names the Ads vendor.**

## BOV — live form (UAV_Harmonized_BOV_Form, 2026-08-27)

30 days. PDF. Google **explicitly allows hiding/editing proprietary info** on
relationship docs — that is **not** a license to edit a gov ID. Proof-of-address
(utility, bank): typically **last 90 days**. Screenshots, zips, digital IDs: no.

Spine that grey teams actually hit:

- Use of Ads: employer / agency-for-org / agency-for-individual / own unregistered
- Type: **First party / Online sales portal / Brand reseller / Marketing-advertising
  agency / Other**
- If agency/affiliate: **Direct affiliate / Member of an affiliate network /
  Marketing agency with negotiated contracts** — **name the network + website +
  contracts**
- Who delivers goods; who creates **ad** content vs **website** content; who the
  customer holds responsible for non-fulfillment; **any other parties who sign in**
- Who pays; licenses (gov / professional / vendor / another business holds it / none)
- How you protect PII + **privacy-policy URL**

Official fail if answers don’t hold: name/address/website mismatch vs the Ads
account; missing value-chain (agency, **end service provider**, **domain owner**,
anyone who logs in); affiliate who won’t name the end provider; payments-profile
country ≠ docs country.

Google does **not** officially say it cross-checks WHOIS / LinkedIn / GMB. It
**does** say: form vs documents vs **existing Ads account**, website **associated
with the account**, payments-profile country, disclosure name.

**Who fills it:** per **customer ID**, by someone who knows ops. **Tenant, not
“the MCC owner instead of the tenant.”** MCC Accounts page **does not show BOV
status**. If **agency pays**, Google still makes the **client** verify a (possibly
non-billing) payments profile for the **disclosure name**.

YeezyPay 2026-04 (vendor): MCC-as-shield **closed**; MCC itself needs corp docs
since 2025; BOV on one child **sooner or later hits the MCC**. Vendor claim, not
Google wording.

## Grey SOP 2026 (live vs dead)

| Move | What it actually is |
|---|---|
| Real nominee + real unexpired physical ID, face matches the photo, payments-profile name/country/address match, SMS in-country | A **drop**, not a bypass. This is what still **passes AIV** |
| Register as **Organization** with a real LLC/COI/IRS letter + D-U-N-S | **Skips the selfie task.** Authorized-rep ID can be foreign; org docs cannot |
| Agency MCC seat | Vendor 2026: agency seats **almost never get BOV**. Isolation is the MCC’s history, not immortality (`01`, `05`) |
| Take BOV on a grey self-reg | **Don’t.** Cannot answer truthfully without naming the offer source. Lying = CS. YeezyPay 2026 SOP: **cut losses, replace via agency** — contradicts older “fabricate a storefront” lore |
| File BOV as an actual affiliate | Official branch exists: **Member of an affiliate network** + network name + end provider + contracts. Passable if disclosable. Impassable if the real offer is undisclosable |
| Claim **First party** when you are an affiliate | **Auto-CS shape.** Official issues page |
| Photocopy / screenshot / printout / digital wallet ID | **DEAD** |
| Photoshop / redacted gov ID | **DEAD / CS** |
| Miss BOV deadline | Official: **pause**. YeezyPay saying this is CS is **false** |
| Open the Ads account on behalf of someone else / VPN at creation | Community expert (Celebird 2025-06). Not Google. Creating-for-others can ban all involved |
| “Already-passed verification accounts” | The **product** is a nominee/org that already completed AIV — not a liveness exploit |
| Same nominee on Google + Meta + bank | Intra-Google cascade is official. Cross-platform selfie share **undocumented**. Shared phone / legal name / address / card is the practical radius |

Warm-up, cloak, antidetect, slow scale, white page **thematically tied to the
offer** (crypto white ≠ pet shop) **delay** BOV. They do not pass it.

## Gaps

- Google Ads selfie vendor: **not named**.
- Ads-specific liveness prompts, glasses, VPN, virtual-camera handling: unpublished.
- Confirmed 2025–26 Ads deepfake/injection pass: **none**.
- WHOIS / LinkedIn / GMB as BOV oracles: not in official text.
- Re-fetch before acting: `15577076`, `UAV_Harmonized_BOV_Form`, `9872280` (geo).
  Doc lists and form fields move in weeks–months.
