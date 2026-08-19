# Phase 0.5 false-positive analysis

All nine false positives share one root cause: the project use was residential, while an LLC,
commercial owner, zoning label, or incidental keyword made the record appear commercial.

| Candidate | Root cause |
|---|---|
| Jeannette McDonald, Portsmouth | residential subdivision |
| 1151 Sagamore Avenue CBC, Portsmouth | residential condominiums |
| Brora, Portsmouth | multifamily project in Office Research zoning |
| J. Paul Griffin Family Trust, Portsmouth | residential subdivision |
| Regan Electric, Portsmouth | owner name mistaken for a commercial project |
| 251 Pine Street, Manchester | conversion to residential units |
| Main Street 401, Salem | office-to-apartment conversion |
| 308 Lake Avenue, Manchester | commercial-to-residential conversion |
| ZJBV Properties, Nashua | multifamily admitted by equipment-storage wording |

## Targeted correction

Phase 0.6 adds project-use exclusions for single/two-family, multifamily, dwelling units,
condominiums, residential subdivisions, and explicitly noncommercial municipal/nonprofit work.
Mixed-use records survive only when the text explicitly identifies commercial or retail space.
Portsmouth candidates are also keyed by normalized address to prevent legal-name variants from
creating multiple candidates.

Counterfactual replay against the 45 reviewed Phase 0.5 records suppresses all nine known false
positives and all three known duplicate variants while retaining all 16 known actionable records.
That is a replay result, not a new blind precision estimate: 0 known false positives among 33
retained records versus 9/45 (20.0%) before. The honest next test is blind review of newly acquired
records; the threshold was not raised and no actionable was removed to make the metric look good.

That blind test was then run on 16 historical permit candidates. Five were false positives
(31.3%), so aggregate Phase 0.6 precision did **not** improve: 14/61 reviewed candidates (23.0%)
are false positives versus 9/45 (20.0%) in Phase 0.5. Four errors came from residential
certificate-of-occupancy records and one from a temporary seasonal store. New exclusions cover
those exact causes, but their benefit must be measured on another unseen batch—not claimed from
the training cases.
