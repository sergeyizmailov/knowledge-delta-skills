# 19 — Launch plan file

A plan on disk survives compaction; an in-session todo list does not, and the last step can fire
days after the first. Observed failure: white catalog products passed review, the target swap
never happened — full budget spent on the wrong catalog, no error anywhere.

## Contract

Before the first write call, copy the template below to `.notes/plan.md` in the project directory
(never the skill tree).

- **One open plan at a time** — close it or mark `[-] skipped — why` before starting another;
  overwriting an open plan silently drops whatever was not ticked.
- **Tick against evidence only** — a returned id, a read-back, a screenshot, never intent: a box
  ticked because you meant to do it is the failure this file exists to stop.
- **Deferred steps keep their trigger inline**: `[ ] after <condition> → <action>` — a due
  condition nobody watches for is a step that never happens.
- **Read at session start** (with `.notes/index.md`), **report open boxes at session end** — a
  launch is never "done" while one is open.
- At close, fold ids and outcomes into `.notes/index.md` and delete the plan.

This is the action order, not the check list — what each check means stays in the skills.

🔺 Unverified: whether a reviewer sees live-rendered catalog products, and whether Meta treats a
catalog edit as review-safe — it reserves re-review "at any time".

## Template

```markdown
# Launch <offer/GEO> — <account> — <date>

## 0 Prep
- [ ] Vertical gate passed (authorization / licence) — `10`
- [ ] Proxy up, token type known (`02`); `assets verify --scope all` green
- [ ] Pixel attached to THIS ad account (`GET /act_*/adspixels`) — `04`
- [ ] White creatives AND target creatives ready, stored apart
- [ ] PWA/link built; domain, redirects, macros walked to the offer once — `11`
- [ ] PWA brand = casino named in texts/creatives; no state/lottery/government branding — `playbooks/casino.md`
- [ ] Account pacing: no campaign create on this account in the last ~3h, no throttle cooldown open (`metaops pace`); weak/new account → smaller tree or first launch in UI — `16` § Pacing
- [ ] Tracking live end to end; CAPI + Pixel share one `event_id` — `tracker-ops/01`

## 1 Catalog (skip if none)
- [ ] Source known: Google Sheet feed (`17`) or batch API (`04`) — never both
- [ ] WHITE items loaded; `product_count` read back
- [ ] One product set per ad set; white and target items never in one set
- [ ] Target items prepared but OUTSIDE the set that goes to review
- [ ] Same `product_set_id` on `adset.promoted_object` and on the creative

## 2 Build
- [ ] Spec written with a future, offset-bearing `start_time` (ACTIVE `apply` refuses a past one); dry run clean
- [ ] If this run needs a review window before spend: `"create_status": "PAUSED"` set at spec top level
- [ ] Multi-advertiser OFF — UI checkbox before spend (or while PAUSED, override) — `SKILL.md`
- [ ] Final QA gate passed — `00` 7.5
- [ ] `apply --confirm SPEND`; ids recorded below (ACTIVE by default — this step spends unless PAUSED above)
- [ ] `verify` exit 0 (one read-back; no polling loop)

## 3 Activate (create_status: PAUSED runs only; re-activating a later pause = `edit status --ids … --status ACTIVE --confirm SPEND`)
- [ ] `start_time` refreshed to the geo-time window (`--refresh-start`)
- [ ] `activate --confirm-ui REVIEWED --confirm SPEND`
- [ ] Review watched every 5 min; swap fired the moment each ad turned ACTIVE (no delivery wait, white must not spend)

## 4 After approval — the step that gets forgotten

**Review timing, measured (act_<id>, TR, catalog ads, 2026-09-22):** three ads created
and activated at 18:48 Istanbul were `ACTIVE` by 18:51-18:52 — **~3 minutes**, `ad_review_feedback`
empty. Same account, an ad set targeting edit put a live ad back through review and it came back
`DISAPPROVED` (`Spam`) within one minute. So the wait is minutes, not hours: poll
`effective_status` (low-frequency — the swap watcher's ≥300 s interval, `16`) from about T+3 min and treat `IN_PROCESS` past ~30 min as the anomaly, not the
norm. One sample account, one vertical — re-measure elsewhere before relying on it.

**VIDEO ads are ~10x slower than image ads.** Same account, 2026-09-23: four `SINGLE_VIDEO` DLO ads
activated 05:39 Istanbul were all `ACTIVE` by 06:05-06:10 — **~26 minutes**, no rejects, versus ~3
minutes for the catalog image ads above. Plausibly ASR plus frame scanning. So the "`IN_PROCESS`
past ~30 min is the anomaly" threshold applies to IMAGE ads; for video, start worrying at ~90 min.
Do not re-activate, re-create or "nudge" a video ad that has been pending for 10 minutes.

**A re-review is much faster than the first review, on the same media.** Same four ads, same
day: swapping in a new creative (identical videos, wider DLO locale sets) put all four back into
review and they returned `ACTIVE` in **~3 min**, against ~26 min on the first pass. Inference:
Meta re-uses the verdict on video it has already scanned, so the slow pass is the first sight of
a file, not every pass. Practical consequence: re-pointing an ad at a new creative built from
ALREADY-APPROVED media is cheap. Re-pointing it at fresh video is not.

**Never wait for delivery before swapping** (operator 2026-09-26, after an ad spent $4.74 on a white
kettle while the old gate waited on impressions and on rejects in OTHER ad sets). Approved + zero
spend is the cheapest moment to swap. A stuck ad is a monitoring question, not a swap gate.

- [ ] `assets swap --map … --watch --confirm SWAP` started in the background right after `apply`
      (swaps each set the minute its ads turn ACTIVE; strategy table in `00` 9.7)
- [ ] Watcher exit read: 0 swapped · 2 still in review at max-wait · 1 blocked (fix the named cause)
- [ ] The ad set cannot be repointed — `promoted_object` immutable, `04`.
- [ ] Read back: `product_count`, filter actually changed, live card correct
- [ ] `effective_status` re-checked — no ad went back into review
- [ ] Rejected ad → switched off; same creative/angle/PWA never re-uploaded into this account (FIELD 2026-09-27)
- [ ] Cloaker ON; filter matches ad-set targeting on device/OS AND GEO — `senior-buyer-ops/03`

## 5 Adding an ad set / ad later
- [ ] New ads = new review → white creative on the new ad set only; start `assets swap --watch` for its set
- [ ] New ad set gets its own WHITE product set, fixed at create and unchangeable after
- [ ] Live ad sets and the live target set untouched while the new one is in review
- [ ] Repeat section 4 for the new ad set

## IDs
campaign: · adsets: · ads: · creatives: · catalog/sets: · URLs/subs:
```
