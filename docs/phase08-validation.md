# Phase 0.8 validation report

Run date: 2026-08-19

## Dataset

Documents 166; raw records 390; signals 148; organizations 136; locations 127; reviewed opportunities 128. Manual outcomes: 23 actionable, 24 false positives, 4 duplicates, 59 stale, 7 uncertain, and 11 not actionable.

## Original actionable cohort

The required operator/contact pass was performed against the original 17 Phase 0.7 actionables before expanding discovery.

- Operator confidence: 5 CONFIRMED, 4 HIGH, 1 MEDIUM, 7 UNKNOWN.
- Contactable: 11/17 (64.7%), up from 6/17; target met without relaxing verification.
- Vendor readiness: 6 A, 2 B, 9 C; 8 distinct A/B leads, below the target of 10.
- Two independent evidence families: 7/17 (41.2%), meeting the 40% cohort target after exact-address FedEx corroboration.

Across the expanded 23-actionable corpus, contactability is 11/23 (47.8%) and independent corroboration is 7/23 (30.4%) because the newly validated blind leads have not yet been operator/contact enriched. Current readiness is 6 A, 2 B, and 15 C.

## Contact utility

Among the original cohort: 3 LOCAL_DIRECT, 5 BUSINESS_GENERAL, 1 CORPORATE, 1 DEVELOPER, 1 PROPERTY_MANAGER, and 6 UNKNOWN. Developer/property-manager contacts improve reachability but cannot qualify a lead for A/B readiness under the implemented thresholds.

Lifecycle timestamps are now stored. Only three records have both a trustworthy `first_actionable_at` and a newly observed `first_contactable_at`; all were resolved on the same run date, so a zero-day result is not a longitudinal business insight. Most legacy actionable timestamps were never captured, and no contactable-to-opening interval is currently measurable.

## Vendor readiness audit

The eight A/B leads are Wonder, Revo Casino, Aranco Oil, Quirk Commercial Trucks, FedEx, RPM Fuels, Kennebunk Savings (proposed; B), and Bluebird Salem (B). The Yatco project remains C because its stored lifecycle stage is stale despite useful operator/contact evidence. No C lead is included in vendor packets.

## Blind validation

The 63-record frozen batch produced 4 actionable, 2 not actionable, 10 false positive, 1 duplicate, and 46 stale results. False-positive rate was 15.9%, narrowly missing the gate. A parser boundary fix was tested; a separate two-record post-fix batch was 2/2 actionable but is too small for a new precision claim. See `docs/blind-validation-phase08.md`.

## Live validation

Only the actual 2026-08-19 observation period is reported. Collection added 73 documents, 222 raw records, 72 signals, and 65 reviewed opportunities including the two post-fix records. No future week or vendor response is claimed.

## Quality gates

- pytest: 38 passed
- ruff: passed
- mypy: passed
- Alembic upgrade/downgrade/upgrade: passed
- Phase 0.8 enrichment import: idempotent (second import created zero contacts)
- Phase 0.8 evidence import: idempotent (second import created zero rows)

## Recommendation

CONTINUE DATA VALIDATION

Contactability for the original cohort is now adequate and the product has eight defensible A/B leads, but it has not reached 10 distinct vendor-ready leads and the frozen false-positive rate is 15.9%. The next validation step is to enrich the four new blind actionables, collect a larger post-fix unseen batch, and then put only the audited A/B packet in front of real vendors.
