# 26 — New account after a ban, minimal footprint

Written 2026-09-29. Reason-1 disables are read as a LINKAGE bucket (shared app / system user / card /
proxy / Page / BM, `07`), and `03` says a card that touched a banned account is near-certain block
risk (two secondary sources, untested). `03` also says a Page/pixel owned by a surviving BM can be
re-shared. Both are practitioner doctrine; which link mattered in tr-1 is unknown.

**Case (outcome unknown at writing).** tr-1 (act_<ACCOUNT_ID>) disabled 13:40 UTC; CF1
(act_<ACCOUNT_ID>) went live by hand 15:40 UTC on the same BM, card, Page and pixel "US PWA <buyer>".
Treat that as a test of the footprint, not as a template.

**Checklist.**
1. Freeze and triage first (`23`); the decision is the operator's/TL's. No launch in the same hour.
2. Choose a replacement account with its own history and spend, correct currency and tz (`03` pre-buy QC).
   Currency/tz are permanent (`08`).
3. Do not carry: the rejected creative, angle or PWA into the same account (`05`); a card from a
   disabled account (`03`); a name or headline with the casino name. New files per account
   ("one file = one account", uniquified, `13`).
4. Carry only what is needed and separable: pixel (attach it; it is a shared identity, so weigh
   `03` recovery vs linkage), PWA domain (a flagged domain must change, `07`), Page (prefer one not tied
   to the dead account; PBIA via Use Facebook Page, `18`).
5. Pace: smaller first tree, first launch in the UI (`24`), one create per 3 h, no `clone --times`,
   no retry storms (`16` Pacing).
6. Check `GET /act_<id>/adspixels`, `account_status` = 1, `metaops doctor`, and a CAPI test event.
7. Watch 24-48 h and the siblings before adding a second campaign; log the outcome in the survival log
   (`06`) with the shared attributes, so the next ban can be attributed.
