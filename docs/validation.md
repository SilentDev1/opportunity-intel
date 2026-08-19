# Phase 0.5 validation report

## Experiment and corpus

- Run date: 2026-08-19
- Geography: New Hampshire, with live evidence from Bedford, Dover, Manchester, Nashua,
  Portsmouth, and Salem.
- Live sources: seven official municipal sources (five planning/zoning sources, one planning
  archive, and one municipal economic-development newsletter).
- Preserved corpus: 66 source documents, 66 raw records, 50 normalized signals, 45
  organizations, 45 physical-location candidates, and 45 deduplicated opportunities.
- Review method: every candidate was checked against its preserved source text and labeled
  `actionable`, `not_actionable`, `false_positive`, `duplicate`, `stale`, or `uncertain`.
  Reproducible decisions and the detailed export are in `data/review-decisions-phase05.csv` and
  `data/exports/phase05-reviewed.csv`.

This is a bounded validation sample, not a statistically representative statewide estimate.
Different sources expose different historical windows, so the corpus cannot honestly be
converted into a uniform statewide “leads per week” rate yet.

## Results

| Verdict | Count | Share |
|---|---:|---:|
| Actionable | 16 | 35.6% |
| Not actionable | 9 | 20.0% |
| False positive | 9 | 20.0% |
| Uncertain | 6 | 13.3% |
| Duplicate | 3 | 6.7% |
| Stale | 2 | 4.4% |

Bedford produced 5 actionable of 5 candidates. Manchester produced four actionable candidates
and demonstrated cross-source corroboration between planning and zoning records. Portsmouth
produced three actionable of 16 and exposed the most residential and duplicate noise. Salem
produced four actionable of six, including Wonder at 125 South Broadway. Dover's two detected
opening/relocation announcements were real but too late for the intended pre-opening sales
window. Nashua's accessible archive was historical and yielded two stale cases.

## Entity resolution and lifecycle findings

Exact normalized address plus municipality is a useful conservative merge key. It joined
planning and zoning evidence for Aranosian Oil Company (1265 South Willow Street), Greywacke
(231 Woodland Avenue), 25 Lowell Street LLC, and Granite State Poker Alliance (1279 South Willow
Street) without relying on fuzzy name matching. The schema records organization roles so a
property owner, developer, applicant, and operating brand need not be collapsed into one entity.

Signal dates, rather than collection timestamps, drive recency. Projects older than 180 days in
early/planning stages become stale; withdrawal or denial evidence maps to `CANCELLED`. Stage
transitions are retained in stage history, and `first_actionable_at` is separate from detection.

## Vendor simulations

Five rule-based vendor profiles were tested against the 16 reviewed-actionable candidates:

| Profile | Matches scoring 50+ | Average score | Strong (75+) |
|---|---:|---:|---:|
| Commercial cleaning | 16 | 69.8 | 4 |
| IT/MSP | 16 | 69.8 | 4 |
| Security/access control | 5 | 71.0 | 0 |
| Pest control | 4 | 70.8 | 0 |
| Commercial insurance | 16 | 61.0 | 0 |

These are product-behavior simulations, not sales outcomes. General profiles retrieve broad
lists; narrower services need better industry classification and later-stage signals.

## Known-target checks

- Recovered naturally: Wonder, Salem, through official municipal material.
- Detected but too late: Dover opening/relocation announcements in the official newsletter.
- Not recovered from the implemented source windows: The Common Man Roadside, The Goddard School,
  OTTO, Walrus & Whale, and Playa Bowls. They remain useful recall targets, but no candidate was
  inserted merely because it appeared on the benchmark list.

## Failure modes observed

- owners, engineers, and developers mistaken for operating brands;
- residential projects with commercial-sounding LLC names;
- routine maintenance or signage at established locations;
- duplicate legal-name variants in one meeting record;
- municipal/nonprofit construction outside the target customer thesis;
- historical records that look fresh when collection time is incorrectly used;
- a newsletter host returning HTTP 429 after several successful documents.

The collector retries 429/5xx responses and marks a partially successful run `degraded` instead
of discarding useful work. Content hashes and database constraints make collection and
processing repeatable.

## Decision

**KEEP INVESTING IN VALIDATION, BUT DO NOT BUILD CUSTOMER SAAS YET.**

The prototype has crossed the minimum evidence bar: real official data, 45 reviewed candidates,
16 plausible vendor opportunities, provenance, cross-source resolution, lifecycle history, CSV
export, and vendor-specific retrieval. The 35.6% actionable rate is promising, but the sample is
small, source windows are uneven, six candidates remain uncertain, and the system lacks
permit/license feeds and real customer outcome data.

The next gate should be four consecutive weeks of scheduled collection with at least two
building-permit or license sources, measured time-to-detection, reviewer agreement, and outreach
results from three to five local vendors. Build customer-facing SaaS only after that test shows
repeatable weekly volume and buyers confirm that the timing is commercially useful.
