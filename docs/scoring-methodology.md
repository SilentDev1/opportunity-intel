# Scoring and inference methodology

Opportunity Intel keeps four separate concepts: entity confidence, lifecycle-stage confidence, opportunity score, and customer match score. Scores are internal prioritization aids, not probabilities or promised opening dates.

## Entity confidence

Deterministic resolution uses normalized name/aliases, normalized full address and suite, city/state, official external IDs, domain, and business phone. An exact name plus exact commercial address can be auto-linked. Conflicting addresses or fuzzy name-only candidates enter `review_items`; they are never silently merged. Legal suffix removal does not imply two entities are identical.

## Lifecycle confidence

Rules choose the strongest observed signal. Registration alone maps to `EARLY_SIGNAL` with low confidence. Planning/zoning maps to `PLANNING`; construction and trade permits to `BUILDOUT`; location-tied hiring/opening announcements to `PRE_OPENING`; inspection/occupancy to `FINAL_PREP`; confirmed opening to `OPEN`. Independent-source corroboration can add at most eight confidence points. Reason strings are stored with the stage.

## Opportunity score

The initial score is a transparent weighted sum:

| Dimension | Weight | Meaning |
|---|---:|---|
| Evidence strength | 35% | strongest signal, adjusted by signal confidence |
| Physical-location confidence | 25% | exact commercial location and site evidence |
| Recency | 15% | decays from the most recently detected signal |
| Independent corroboration | 15% | distinct sources, capped at 100 |
| Commercial relevance | 10% | likely vendor demand, not assumed revenue |

The full component breakdown is stored in `score_breakdown`. A high score cannot substitute for source review. Registration-only, residential, shell/holding, dissolved, online-only, duplicate, and stale candidates may be retained but suppressed.

## Vendor-need and customer matching

Vendor needs are rules-first and store their rule reason. Industry and stage select service categories; unknown industries receive only conservative general-commercial suggestions. Customer match assigns 35 points for target industry, 30 for an explicit service city, 25 for overlapping inferred services, and up to 10 from opportunity quality. Radius is accepted in the prototype profile but is not applied until locations have defensible coordinates.

## Staleness

Early/planning opportunities become stale after 180 days without a new signal; later pre-opening/buildout stages use 120 days. These are starting policies, not universal truths. A new verified signal can restore freshness. Cancelled, closed, or contradictory projects require manual review.

## Limitations

Weights are hypotheses and must be calibrated against manual verdicts (`true_positive`, `false_positive`, `uncertain`, `duplicate`, `not_actionable`). “92” does not mean a 92% chance of opening. Date ranges retain source precision; uncertain seasons/months must not be converted to invented exact dates.
