# Phase 0.7 contactability analysis

## Result

Six of 17 reviewed actionable opportunities have a verified official public route (35.3%). Eleven
are not contactable. None are counted as partially contactable or uncertain: a generic web result
was deliberately not enough. The original 16-opportunity cohort reached 5/16 (31.2%).

| Municipality | Actionable | Contactable | Rate |
|---|---:|---:|---:|
| Bedford | 5 | 1 | 20.0% |
| Manchester | 5 | 3 | 60.0% |
| Portsmouth | 3 | 0 | 0.0% |
| Salem | 4 | 2 | 50.0% |

| Industry | Actionable | Contactable | Rate |
|---|---:|---:|---:|
| Automotive | 1 | 1 | 100.0% |
| Entertainment | 1 | 1 | 100.0% |
| Restaurant | 4 | 3 | 75.0% |
| Warehouse/logistics | 3 | 1 | 33.3% |
| Other | 4 | 0 | 0.0% |
| Professional office | 4 | 0 | 0.0% |

## Chain versus independent

| Class | Actionable | Contact rate | Average readiness |
|---|---:|---:|---:|
| Chain/franchise | 3 | 100.0% | 89.5 |
| Independent/local | 5 | 60.0% | 74.0 |
| Unknown | 9 | 0.0% | 46.3 |

The result is materially stronger for known brands. It does not yet prove that the system works
well for unnamed local tenants. Portsmouth is the clearest failure mode: all three actionables name
property owners, and no verified operating-business route was found.

## Provenance and safeguards

Eight contact records were stored for the original cohort and two for the blind-batch Quirk lead.
Each includes source URL/name/type, retrieval and verification timestamps, confidence, public and
official flags, and an explicit entity-match reason. Phones are normalized to E.164. URLs are
canonicalized. Website contacts require strong same-brand, same-address, same-city, same-operator,
or official-location evidence. No private or inferred personal contact information is stored.

Verified routes include RPM Fuels' official location page and phone, the NH Lottery's public Revo
location phone plus Revo's official site, FMCSA's public Aranco business phone, Bluebird's official
rental site, Wonder's official support route, and Quirk Commercial Trucks' exact-address site and
phone. Corporate or public-registry contacts are labelled as such rather than presented as a local
owner.
# Phase 0.8 update — 2026-08-19

The original 17-actionable cohort now has 11 verified contactable records (64.7%), up from 6 (35.3%). Utility distribution is 3 LOCAL_DIRECT, 5 BUSINESS_GENERAL, 1 CORPORATE, 1 DEVELOPER, 1 PROPERTY_MANAGER, and 6 UNKNOWN. The last two categories are legitimate reachability paths but intentionally cannot make a lead A/B-ready.

The expanded corpus has 23 actionables and 11 contactable (47.8%); the four main blind-batch actionables and two post-fix actionables have not yet been enriched. Lifecycle fields now retain first operator identification and first contactability. Legacy timestamps are incomplete, so only three same-day actionable-to-contactable intervals are measurable and no longitudinal conclusion is warranted.
