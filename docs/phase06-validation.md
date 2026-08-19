# Phase 0.6 active-implementation report

## Current dataset

| Metric | Count |
|---|---:|
| Official sources | 9 |
| Raw documents | 82 |
| Raw records | 157 |
| Signals | 67 |
| Organizations / locations / candidates | 61 / 61 / 61 |
| Reviewed | 61 |
| Actionable | 16 |
| False positive | 14 |
| Duplicate | 3 |
| Stale | 13 |
| Uncertain | 6 |
| Not actionable | 9 |

The 150-reviewed and 50-actionable gates were not reached. Counts were not padded with weak
license records or future weeks.

## Precision change

- Phase 0.5: 9/45 false positives (20.0%).
- Phase 0.6 aggregate after a blind historical-permit batch: 14/61 (23.0%).
- Replay of the Phase 0.5 corpus under new residential/duplicate rules: all nine known false
  positives and three duplicate variants suppressed, all 16 actionables retained.
- Blind permit result: 5/16 false positives (31.3%), followed by targeted residential occupancy
  and temporary-use exclusions.

Precision has not yet improved on unseen data. The replay shows the corrections are targeted;
another blind batch is required to measure generalization.

## Signal diversity

| Signal | Count |
|---|---:|
| Planning application | 33 |
| Certificate of occupancy | 10 |
| Zoning application | 8 |
| Building permit | 7 |
| Sign permit | 7 |
| Opening confirmed | 1 |
| Relocation | 1 |

Source classes are planning board 36, building permit 17, zoning board 12, and municipal news 2.
License collection added 21 raw records but correctly produced zero signals/opportunities.

## Multi-signal quality

| Signals/opportunity | Opportunities | Reviewed actionable | Actionable rate |
|---|---:|---:|---:|
| 1 | 56 | 13 | 23.2% |
| 2 | 4 | 2 | 50.0% |
| 3 | 1 | 1 | 100.0% |
| 4+ | 0 | 0 | n/a |

The direction supports corroboration, but n=5 for multi-signal opportunities is inadequate.
Real examples are Aranosian Oil, Greywacke, and Granite State Poker, resolved across Manchester
planning/zoning at the same location. No real three-stage planning→permit→hiring timeline exists.

## Weekly flow

Only Week 1 has begun (2026-08-17 through 2026-08-23), and it is incomplete. The live framework
is in `docs/live-validation/`. Historical Salem permits are excluded from fresh weekly volume.
No weeks were fabricated, so fresh actionable opportunities per completed week remains unknown.

## Historical flow and lead time

Fifteen Salem reports spanning 79 event-days yielded 70 commercial permit records, 17 high-value
signals, 16 candidates, 11 real-but-stale events, and five false positives. No credible confirmed
opening-date pairs exist, so lead-time sample size is zero and no percentile statistics are shown.

## Vendor value

| Vendor profile | Matches | Average match score | Strong matches |
|---|---:|---:|---:|
| Commercial cleaning | 16 | 69.8 | 4 |
| IT/MSP | 16 | 69.8 | 4 |
| Security/access control | 5 | 71.0 | 0 |
| Pest control | 4 | 70.8 | 0 |
| Commercial insurance | 16 | 61.0 | 0 |
| Telecom/internet | 16 | 61.0 | 0 |
| Waste management | 7 | 70.8 | 0 |
| POS/payments | 4 | 70.8 | 0 |
| Signage, payroll, landscaping/snow | 0 each | n/a | 0 |

Broad general-service matching dominates. The corpus does not yet prove balanced recurring value
across customer categories. Timing is 2 HIGH, 12 MEDIUM, and 2 LOW among actionables.

## Contactability

Zero of 16 actionable opportunities has a verified official website, business phone, or public
contact page stored (0%). This blocks the claim that the current leads are immediately actionable.

## Source health

Eight sources have successful persisted runs. Dover retained ten documents before a historical
429 failure; retry and degraded-run behavior are implemented. Salem current permit access moved
from weekly bulk PDFs to parcel-oriented portals, so the implemented permit source is historical,
not a durable live feed. Merrimack returns 403 and is not bypassed.

## Best current real opportunities

The strongest evidence/timing examples are Granite State Poker Alliance, Aranosian Oil Company,
Greywacke, Wonder, Bluebird Salem, Net Lease Realty, Griffin Road Realty, Singh Realty, Twenty-One
Keewaydin Drive, Brook Hollow, 304 Maplewood, and Double MC. Several names are property owners or
developers rather than confirmed operators; the detailed analysis states that limitation.

## Recommendation

**CONTINUE VALIDATION.**

The phase disproves any present justification for GO TO CUSTOMER MVP: only 61 candidates are
reviewed; actionable rate fell to 26.2% after honest historical review; aggregate false positives
are 23.0%; no completed weekly cohort, opening lead-time sample, vendor feedback, or contactable
lead coverage exists. Positive evidence remains: 16 real opportunities, four meaningful signal
classes, exact-location cross-source resolution, and a historical permit source that found real
tenant events. The next decisive work is a durable live permit/license feed, contact enrichment
from official business pages, four completed weekly cohorts, and actual vendor ratings.
