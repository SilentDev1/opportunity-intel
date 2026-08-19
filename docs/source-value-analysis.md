# Phase 0.8 source value analysis

Run date: 2026-08-19

The ranking uses downstream value rather than acquisition volume: five points per A/B lead, three per resolved operator, two per actionable, and one per attributed contact. Corroboration and stage-transition counts are also retained.

| Source | Records | Candidates | Actionable | Operators | Corroborated | Stage transitions | A/B leads | Score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Manchester Planning | 28 | 18 | 8 | 4 | 3 | 0 | 3 | 43 |
| Portsmouth Planning | 50 | 26 | 6 | 2 | 1 | 26 | 2 | 28 |
| Manchester Zoning | 8 | 11 | 3 | 3 | 2 | 7 | 2 | 25 |
| Salem Planning | 5 | 7 | 4 | 2 | 4 | 6 | 2 | 24 |
| Bedford Planning | 14 | 5 | 5 | 2 | 1 | 5 | 1 | 21 |

Official operator/location pages have very high value per record: Quirk and RPM each contributed one A/B lead from one record; FedEx added operator confirmation, contact provenance, and corroboration from one record.

Salem Historical Permits produced 173 parsed records in the latest collection but 44/45 blind candidates were stale and one was a false positive. It should be deprioritized for new-lead discovery and retained only for chronology/backfill with strict date gating.
# Phase 0.9 prioritization — 2026-08-19

The updated ranking emphasizes fresh/actionable contribution and operator/contact conversion.

- **TIER 1 — Salem Planning:** 16 records, 13 candidates, 10 actionable, 4 resolved operators, 4 A/B leads. It produced both fresh opportunities in the current incomplete week and the only fresh cleaning A/B lead.
- **TIER 1 — Manchester Planning:** 28 records, 18 candidates, 7 actionable, 4 resolved operators, 3 A/B leads. Retain with boundary-regression monitoring.
- **TIER 2 — Manchester Zoning:** high-value corroboration; 3 actionable and 2 A/B leads from 8 records.
- **TIER 2 — Bedford Planning:** 5/5 actionable, but operator/contact resolution remains uneven.
- **TIER 3 — Portsmouth Planning:** 83 records, 37 candidates, 5 actionable, 2 A/B leads; adjacent-item extraction still caused blind false positives.
- **DEPRIORITIZE — Salem Historical Permits:** useful for chronology and regression work, not fresh discovery; it explains most stale volume.
- **DEPRIORITIZE — Dover municipal news and Nashua archive under current collectors:** the latest deeper runs added no opportunities.

Official company/location sources remain the highest-value corroboration layer per record. The municipal-land-use plus official-company combination is 4/4 actionable, contactable, and A/B-ready, though the sample is small.

# Phase 1.0 current-flow update — 2026-08-19

The latest live rerun produced 10 new Dover newsletter documents but zero signals or opportunities; one linked document was rate-limited. All other configured feeds produced zero new documents. Current-window fresh-opportunity contribution remains Salem planning 1 and Manchester planning 1. No other source contributes a fresh opportunity, and only Salem contributes a fresh cleaning A/B lead.

For production value, current issued permits, sign permits, and occupancy/inspection updates now rank above further archive depth. Historical sources remain useful for regression and chronology only.
