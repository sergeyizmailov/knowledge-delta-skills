# 03 — Domains, redirects, trackers, the review layer

Reviewed 2026-08-27. Tracker metric discipline → `tracker-ops`. Conversion mechanics →
`google-ads/06`.

## What AdsBot actually does

AdsBot **fetches the Final URL chain** as part of ad review and ongoing enforcement — the destination
is inspected directly, repeatedly, after approval too (structural difference from Facebook).

**Destination requirements** [official]:

- Must "work on common browsers and devices", must not "return an HTTP error code for Google AdsBot
  web crawlers on common devices globally". **Blocking/erroring the crawler is itself a violation
  surface**, not just UX. AdsBot egress is **primarily US** — geo-blocking the US = Destination not
  accessible even if buy geo is EU/ASIA. A WAF 429 is same class as 403.
- **"Redirects from the final URL that take the user to a different domain"** — explicitly prohibited.
  Same-domain redirects tolerated.
- **"Tracking templates and expanded URLs must lead to the same content as the final URL."** Operative
  sentence for the whole tracker layer.
- Display URL domain must match where the user actually lands.
- Pages "solely designed to send users elsewhere", replicated/scraped content, incomprehensible
  content are named violation patterns.

**Enforcement: mandatory 7-day warning before suspension.** Not the egregious track.

## Where the line actually is

Google publishes **no** page distinguishing an allowed tracking redirect from prohibited content
substitution **by protocol** — no official "302 is fine, JS is not" statement. Policy text is
intent/outcome-based, split across two pages:

- **Abusing the ad network** — *Evasive ad content*: "Manipulation of ad components like text, image,
  videos, domain, or subdomains in an attempt to bypass detection or enforcement action is not
  allowed." *Circumventing systems*: **egregious, immediate suspension, no warning step.**
- **Misrepresentation** — carries the destination-mismatch language: "Promotions that are not relevant
  to the destination are not allowed"; promising things in the ad that are "unavailable or aren't
  easily found from the destination" is a violation.

**Enforceable question: is the destination relevant/available as advertised, and does content differ
conditioned on who is requesting it — not which redirect mechanism was used.**

Serving different content to reviewers than visitors is Circumventing systems — **no warning,
permanent, propagates**. Filter stacks, white-page requirements, Keitaro/Adspect recipes,
replacement-after-burn → `05`. This file stays on what AdsBot fetches and how ValueTrack should look.

## ValueTrack, tracker wiring and the gclid chain → `tracker-ops/04`

`tracker-ops/references/04-google-lane.md` owns this end to end: the escaping ladder
(`{lpurl}` / `{lpurl+2}` / `{ignore}`, literal `?` vs `%3F`), the Keitaro and RedTrack
configurations, the gclid → OCI chain, backdate windows, the dedup key, and timezone discipline.
Do not restate it here.

Grey-specific, belongs here:

- **The tracker hop must satisfy "same content as the final URL."** Every ValueTrack fact matters only
  because AdsBot re-fetches that chain (§ above).
- **Tracking-template changes take 24–48h to propagate.** A chain judged sooner reads as moderation
  when it's a propagation delay — misdiagnosis burns accounts that were never flagged.
- **Keitaro's own guidance: disable cookie tracking to reduce moderation risk** — vendor admitting its
  default raises review exposure.
- **Do not use RedTrack funnel filters as a cloak.** Vendor says filtering "won't be useful" for Google
  Ads no-redirect campaigns; using it that way = circumvention attempt with none of the function.
  Cloaking/review layer → `05`.
- **Uncertified tracker hosts** in the visible chain = Destination-mismatch surface — disapproval
  codes in `05`.

## Domains

**Safe Browsing / Web Risk** [official]:

- **Malware** — "software or mobile application specifically designed to harm a computer, a mobile
  device, the software it's running, or its users".
- **Unwanted software** — behavior that is "deceptive, unexpected, or that negatively affects the
  user's browsing or computing experience".
- Search Console's Security Issues report splits **Malware** (web-based, no user action) from
  **Harmful downloads** (requires an explicit download).

**Critical tier distinction inside the same Ads policy page:**

- **Malicious software** — egregious. Immediate suspension, no warning, permanent.
- **Compromised site** — "destinations which are hijacked and hacked" — enforced as **ad disapproval**,
  a much lighter tier. **Not a death sentence.**

**Scope clause explaining otherwise inexplicable burns:** malware ban applies to software the site
"hosts or links to, **regardless of whether the software is promoted through the Google advertising
network**". Domain/account-level flag — unconnected to the running campaign still burns the account.

**A Google domain burn has wider blast radius than a Facebook one.** Safe Browsing flag is a
**cross-Google-product signal** — surfaces in Search Console Security Issues, can affect organic
visibility, not just Ads. Facebook domain block is platform-scoped only.

### Rotation discipline

Rotate on **signals, not a timer.** Fixed-timer rotation burns a working domain early, does nothing
for one flagged the day after you reset the clock.

Signals that should trigger rotation:

- A Safe Browsing / Web Risk flag in Search Console Security Issues.
- AdsBot fetch errors appearing in the account.
- A mass-disapproval wave hitting ads pointing at **that domain specifically** while other domains in
  the same account stay clean — that isolates the burn to the domain.
- Hosting-side compromise indicators, including a shared-hosting neighbor's known breach. Rotate off
  compromised-adjacent infrastructure **before** the crawler finds it.

**Attribution discipline — change one variable at a time.** *Fresh domain* on *existing clean account*
still mass-disapproved → account/payment/identity signal implicated, not the domain. *New domain*
clears review on an account that just had another domain mass-disapproved → prior domain was the burn.

> 🔺 **Honest gap:** this single-variable discipline is borrowed from Facebook-side doctrine in
> `meta-grey-ops`. **Not** found in any reachable Google-specific source — relevant forums (afflift,
> BlackHatWorld, Reddit) inaccessible. Sound method, not observed Google-side consensus.

🔺 **Second honest gap:** no source connects **expired-domain vetting** (Moz Spam Score, Majestic Trust
Flow, domain-age tooling) to **Google Ads** account safety — pure organic-SEO/PBN framing. **Do not
assume the SEO practice transfers to Ads risk.**
