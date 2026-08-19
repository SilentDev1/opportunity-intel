# Phase 0.8 blind validation

Run date: 2026-08-19

## Freeze procedure

All 63 newly processed, previously unreviewed opportunities from Manchester planning, Portsmouth planning, and Salem historical permits were frozen in `phase08-unseen-2026-08-19` before manual review. Frozen rows retain machine status, stage, score, operator status, contactability status, and payload. The review file is `data/review-decisions-phase08-blind.csv`.

## Frozen batch result

| Outcome | Count | Rate |
|---|---:|---:|
| Actionable | 4 | 6.3% |
| Not actionable | 2 | 3.2% |
| False positive | 10 | 15.9% |
| Duplicate | 1 | 1.6% |
| Stale | 46 | 73.0% |
| Uncertain | 0 | 0.0% |

The false-positive rate missed the `<15%` gate by 0.9 percentage points. Historical permits supplied 45 of the 63 candidates and mostly produced correctly stale results; this feed has low new-lead value despite its volume.

By municipality: Manchester 8 candidates (1 actionable, 6 false positives, 1 duplicate); Portsmouth 10 (3 actionable, 2 not actionable, 3 false positives, 2 stale); Salem 45 (1 false positive, 44 stale).

By source/signal: Manchester planning supplied 8 planning signals; Portsmouth planning supplied 10 planning signals; Salem historical permits supplied 45 permit/buildout candidates. The exact frozen source payloads remain in the database.

## Failure and post-fix check

Manchester's parser did not treat `PDSP` application IDs as item boundaries, allowing an adjacent applicant to bleed into the preceding address. The original frozen results were preserved. A regression test was added and the boundary parser fixed. Reprocessing created a separate two-record frozen batch, `phase08-postfix-2026-08-19`; both records were actionable and neither was a false positive. This tiny post-fix sample is directional only and does not replace the 63-record metric.

