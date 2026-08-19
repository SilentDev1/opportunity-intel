# Opportunity Intel vendor-validation package

Opportunity Intel finds New Hampshire businesses approaching a commercial change and provides
enough verified evidence and public contact information for a local vendor to decide whether to act.

## How these leads were found

Municipal planning and permit records identify the project and location. Targeted official company
pages or public registries resolve the operator and contact route. Repeated municipal documents for
one event count as one evidence family. No outreach has occurred and no vendor response is implied.

## Six vendor-ready samples

| Business | City | Stage | Readiness | Why now | Verified route |
|---|---|---|---:|---|---|
| Wonder | Salem | Pre-opening | 90.7 | Exact tenant, official announcement, and municipal filing | Official support/site |
| Revo Casino | Manchester | Planning | 89.5 | Large facility expansion at a confirmed operating location | Official site and NH Lottery location phone |
| Aranco Oil | Manchester | Planning | 88.9 | New fuel/convenience/restaurant project; legal/DBA identity confirmed | FMCSA public business phone |
| RPM Fuels | Bedford | Planning | 88.3 | Convenience-store conversion at the operator's exact address | Official site and business phone |
| Quirk Commercial Trucks | Manchester | Planning | 88.3 | Automotive-sales expansion at the operator's exact facility | Official site and location phone |
| Bluebird Self Storage | Salem | Location confirmed | 80.5 | New self-storage project tied to an official NH operating brand | Official rental/inquiry site |

The detailed, vendor-specific CSVs are in `data/exports/vendor-ready/`. The package has only six
distinct leads, not ten; it is suitable for internal review but does not satisfy the proposed vendor
validation gate.

## Feedback form

For each lead:

1. Did you already know about this business?
2. Would you contact this business?
3. Is this information early enough to be useful?
4. Is the opportunity relevant to what you sell?
5. Is the business/contact information sufficient?
6. What information is missing?
7. Would you want a weekly list like this?
8. What would make this worth paying for?

Record responses using `data/vendor-feedback-template.csv`. Its rows are intentionally empty.
Supported future outcomes are `NOT_REVIEWED`, `REVIEWED_USEFUL`, `REVIEWED_NOT_USEFUL`,
`CONTACT_ATTEMPTED`, `CONTACTED`, `MEETING`, `QUOTE`, `CUSTOMER_WON`, `NO_RESPONSE`, and
`BAD_LEAD`.
# Phase 0.8 update — 2026-08-19

Five plain-language CSV packets are available under `data/exports/vendor-ready/`: commercial cleaning (8), IT/MSP (8), commercial insurance (8), security/access control (4), and pest control (3). Only A/B leads are eligible; C leads are excluded. Each row includes the business, location, event, stage, timing explanation, category relevance, verified contact route, evidence, provenance, and last update.

There are eight distinct A/B leads, not ten. No vendor feedback has been received or invented. The packet is ready for internal audit and prospective vendor presentation only after the lead-count/precision concerns in the Phase 0.8 report are accepted.
