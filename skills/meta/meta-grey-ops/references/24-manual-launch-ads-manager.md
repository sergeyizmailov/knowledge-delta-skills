# 24 — Manual launch in Ads Manager (1-5-1 checklist)

Written 2026-09-29 from the CF1 Oklahoma longread (act_<ACCOUNT_ID>, USD, America/Los_Angeles, launched
by hand 15:40 UTC). Use when the API path is not usable, on a weak/new account (`16` § Pacing), or right
after an account death when API load is a suspect. Same rules as `SKILL.md`: no casino names in names,
headline, description, display link; on any disapproval do not edit or resubmit.

**Campaign.** Objective Sales, CBO on, daily budget, bid strategy **Bid cap** (no cap = uncapped
conversion goal). Name `<keitaro id> US PWA <ST> Longread<n> <buyer>` (`03`), no casino name.
1-5-1 = 5 ad sets, one ad each (`04` Structures): build ad set 1, then **Duplicate the ad set** inside
the same campaign and change only name, image and text.

**Ad set.** Conversion location Website, event Purchase, the pixel attached to THIS account,
attribution 7d click + 1d view (immutable after create). Region (e.g. Oklahoma), age 21-65.
Placements **Manual**: Mobile, Facebook and Instagram, all their placements; untick Threads feed,
Messenger Stories, WhatsApp Status, Apps and sites; untick "Allow limited spending to excluded
placements". Equivalent of `placements: "fb_ig_all"` (`SKILL.md`). Bid cap amount on the ad set.

**Ad.** Identity: the Page and Instagram = **Use Facebook Page** (no real IG needed). Single image, primary
text from the file, headline a neutral ≤40-char line, description empty, CTA **See details** (SEE_DETAILS,
live on CF1 ads; if it is missing from the list pick Learn more and tell the operator), website URL =
the PWA link, display link empty or root domain. URL parameters:
`campaign_id={{campaign.id}}&campaign_name={{campaign.name}}&adset_id={{adset.id}}&adset_name={{adset.name}}&ad_id={{ad.id}}&ad_name={{ad.name}}&placement={{placement}}&source={{site_source_name}}&fbp=<pixel>&buyer=<id>&act=<account>&funnel=pwa&approach=longread`.
All Advantage+ creative enhancements off, Multi-advertiser ads off. **Ticking those off in the UI did not
clear everything** (field 2026-09-29, all five CF1 ads, read via API): `creative_sourcing_spec.featured_offering_spec`
("Show spotlights", pulls website text into the ad) read back OPT_IN and social-feedback preservation
is on, while `degrees_of_freedom_spec` showed nothing OPT_IN. Look for a spotlights-style toggle in the ad's
Advantage+ creative panel before publish (exact UI label unverified). Clearing it afterwards is
`metaops edit creative --enhancements-off` (clone-and-swap: a new creative, review re-opens; not applied
live yet, the operator decides).

**Advantage+ sales campaign limits (field 2026-09-29).** In the Sales flow **Advantage+ audience could
not be switched off** (the plan sheet said "off"; the ad set went live with it on), and
catalog fields appear even without a catalog: ignore them. With Advantage+ audience age_min is capped at 25
and age_max forced to 65 (`04`), gender and interests are not hard controls. Reported by secondary sources,
unverified here: unticking "use as a suggestion" makes an input a hard control. API ad sets created by
`metaops` set `advantage_audience: false`; that choice was not available in this UI flow.

**After publish.** Ad set "Delivery: No ads" right after publish is UI lag. All 5 ads were PENDING_REVIEW at
15:44 and ACTIVE at 15:47-48 UTC. Get the ids (`metaops review --ids …`, read-only) into `.notes/`.
Exact renames: `metaops edit rename --set ID=NAME` (ACTIVE → IN_PROCESS → ACTIVE in ~15 s, no review); the
tracker keeps the first-publish name in sub5, so split by sub6 (ad_id). Make ad names unique before
publish (four ads once shared one name). Any deviation from the plan sheet: touch nothing, report.
