# Phase 0.5 actionable opportunity analysis

All 16 Phase 0.5 actionable decisions were re-examined before adding Phase 0.6 data. The complete
evidence-derived score matrix is in `data/exports/phase05-actionable-matrix.csv`.

| Organization / likely brand | Municipality and location | Industry | Signals | Stage | Timing | What increases confidence |
|---|---|---|---:|---|---|---|
| 265 SRR / Rockfish REI | Bedford — 265/269 South River Rd | office/medical | 1 planning | PLANNING | MEDIUM | identify tenant/operator; building permit |
| Bedford RLG Properties | Bedford — 308 South River Rd | warehouse/manufacturing | 1 planning | STALE | LOW | current permit or tenant announcement |
| Bellazardan | Bedford — 30 Harvey Rd | light industrial | 1 planning | PLANNING | MEDIUM | operator and construction evidence |
| Net Lease Realty | Bedford — 137 Route 101 | fuel/convenience | 1 planning | PLANNING | MEDIUM | operating brand and building permit |
| SRR Bedford NH Ventures | Bedford — Technology Dr/South River Rd | restaurant/fuel | 1 planning | STALE | LOW | current filing and tenant identity |
| Aranosian Oil Company | Manchester — 1265 South Willow St | fuel/restaurant | 2 | PLANNING | MEDIUM | permit/buildout or restaurant brand |
| Brook Hollow | Manchester — 275 Hooksett Rd | car wash | 1 | PLANNING | MEDIUM | extension outcome and construction |
| Granite State Poker Alliance | Manchester — 1279 South Willow St | entertainment | 3 | PLANNING | MEDIUM | building permit or hiring |
| Greywacke | Manchester — 231 Woodland Ave | contractor office | 2 | PLANNING | MEDIUM | operator confirmation/buildout |
| 304 Maplewood | Portsmouth — 304 Maplewood Ave | office | 1 | PLANNING | MEDIUM | tenant identity and permit |
| Double MC | Portsmouth — 134 Pleasant St | mixed commercial | 1 | PLANNING | MEDIUM | operating tenants |
| Griffin Road Realty | Portsmouth — 218 Griffin Rd | warehouse | 1 | PLANNING | MEDIUM | operator/tenant; issued permits |
| Bluebird Salem | Salem — 9 Northeastern Blvd | self-storage | 1 | LOCATION_CONFIRMED | HIGH | building permit/construction |
| Singh Realty | Salem — 9 Manor Pkwy | contractor units | 1 | PLANNING | MEDIUM | tenant roster/buildout |
| Twenty-One Keewaydin | Salem — 21 Keewaydin Dr | adult education | 1 | PLANNING | MEDIUM | operator brand and occupancy evidence |
| Wonder | Salem — 125 South Broadway | restaurant | 1 | LOCATION_CONFIRMED | HIGH | fit-out, hiring, license, opening evidence |

## Findings

- Only 6 of 16 names clearly resemble operators; the rest are owners/developers. These can still
  be useful property/project leads, but they do not yet fulfill the operating-business promise.
- Three Manchester opportunities have two independent municipal source classes; Granite State
  Poker has three signals. Their observed actionable rates support corroboration: one-signal
  31.7%, two-signal 66.7%, three-signal 100%, though samples are far too small for inference.
- Timing value is 2 HIGH, 12 MEDIUM, and 2 LOW after current staleness rules.
- The database has no verified website, phone, or public contact route for any of the 16. Current
  measured contactability is therefore 0%, a major validation gap—not permission to collect
  personal contact data.
- Vendor matching is broadest for cleaning, MSP, telecom, and insurance because generic inferred
  needs dominate. Security, pest, waste, signage, payroll, landscaping, and POS matches are much
  more dependent on industry and stage. The matrix exposes this concentration rather than hiding it.

The actionable label means plausible vendor timing with official evidence. It does not mean the
named owner definitely buys the inferred service or that the project will open.
