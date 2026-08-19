# Phase 0.7 validation report

## Current dataset

| Metric | Count |
|---|---:|
| Sources | 15 |
| Documents | 93 |
| Raw records | 168 |
| Signals | 76 |
| Organizations | 69 |
| Locations / candidates | 63 / 63 |
| Reviewed | 63 |
| Actionable | 17 |
| False positive | 14 |
| Duplicate | 3 |
| Stale | 13 |
| Uncertain | 7 |
| Not actionable | 9 |

The increase includes six targeted official evidence snapshots and five unseen Manchester planning
documents. Historical discoveries remain historical and are not reported as live leads.

## Contactability and operator identification

Contactability is 6/17 actionables (35.3%): six `CONTACTABLE`, zero
`PARTIALLY_CONTACTABLE`, eleven `NOT_CONTACTABLE`, and zero `UNCERTAIN`. The original
mandatory cohort reached 5/16 (31.2%), missing the 70% target.

Operators are known for seven actionables, developer-only for three, and property-owner-only for
seven. Chain/local classification is three chain/franchise, five independent/local, and nine
unknown. The unknown class has zero contactability, so the owner/operator distinction is material.

## Vendor readiness

Readiness is separate from opportunity score and sums: actionable (20), operator (20), exact
location (10), stage confidence (15), independent corroboration (15), contactability (15), and
fresh/timely stage (5).

| Band | Leads | Average score |
|---|---:|---:|
| High (75+) | 6 | 87.7 |
| Medium (50–74.9) | 2 | 60.8 |
| Low (<50) | 9 | 45.3 |

There are six distinct vendor-ready leads, below the ten-lead gate.

## Independent signal corroboration

| Independent families | Opportunities | Actionable | False positives | Actionable rate | FP rate |
|---|---:|---:|---:|---:|---:|
| 1 | 56 | 11 | 14 | 19.6% | 25.0% |
| 2 | 7 | 6 | 0 | 85.7% | 0.0% |
| 3+ | 0 | 0 | 0 | n/a | n/a |

Six of 17 actionables (35.3%) have two independent families; the original cohort is 5/16
(31.2%). Agendas, minutes, zoning hearings, and sign review for one municipal event collapse into
`municipal_land_use`. The observed quality difference is encouraging, but n=7 is too small for a
precision claim.

## Blind precision test

Five previously unseen documents were taken in feed order from the official Manchester planning
source with no record-level preselection. Processing produced two candidates, reviewed before
contact enrichment:

| Result | Count |
|---|---:|
| Batch size | 2 |
| Actionable | 1 |
| False positive | 0 |
| Duplicate | 0 |
| Stale | 0 |
| Uncertain | 1 |
| False-positive rate | 0.0% |
| Actionable rate | 50.0% |

Quirk's automotive-sales expansion was actionable. Coral 516 Elm was uncertain because its
commercial space has no tenant. There was no post-review precision-rule change. The numeric
target was met, but a two-candidate sample does not prove generalization. A Salem attempt failed
in the network sandbox and its bounded authorized retry stalled; both runs remain in source health.

## Vendor value

Exports contain six commercial-cleaning, six IT/MSP, four security/access-control, three
pest-control, and six commercial-insurance matches. These are category matches across six distinct
leads, not 25 unique opportunities or vendor endorsements.

Best leads are Wonder (90.7), Revo Casino (89.5), Aranco Oil (88.9), RPM Fuels (88.3), Quirk
Commercial Trucks (88.3), and Bluebird Self Storage (80.5). Twenty-One Keewaydin advanced to
buildout after an official permit, but remains medium-readiness because its operator is unnamed.

## Live Week 1 and source value

Observed additions are five unseen Manchester documents, five parsed records, three municipal
signals, two candidates, one actionable, and one uncertain. Post-review targeted enrichment added
one Quirk corroboration. Wonder moved to PRE_OPENING on an official announcement; Twenty-One
Keewaydin moved to BUILDOUT on an official permit. Neither is marked open.

Official company pages improved operator/location confirmation and inquiry routes. NH Lottery
added Revo's public location phone; FMCSA resolved Aranosian/Aranco identity and a business phone;
Salem's permit report improved stage confidence. The generic license source remains deprioritized
because 21 records produced no useful opportunities.

## Quality gates

- `pytest`: 34 passed.
- `ruff`: passed.
- `mypy`: passed for 13 source files.
- Alembic fresh upgrade/downgrade/upgrade: passed through revision `20260819_0003`.
- Contact import rerun: zero new contacts; evidence import rerun: zero new objects.
- No vendor response, outreach outcome, future week, private contact, or opening confirmation was
  fabricated. Wonder stays pre-opening because its official locations page conflicts with the
  announced August 13 date.

## Recommendation

**CONTINUE DATA VALIDATION**

The concept improved from zero to six contactable leads, but 35.3% contactability, six
vendor-ready leads, and a two-candidate blind sample do not justify vendor validation yet. The next
decisive work is operator resolution for local projects and a larger current-data blind batch.
