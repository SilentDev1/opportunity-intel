# New Hampshire source feasibility map

Last tested 2026-08-19. “Working” means a live request succeeded during this validation run;
“implemented” means a collector exists here. Requests are sequential, delayed, bounded, and
hash-deduplicated. No authentication barriers were bypassed.

| Municipality | Official source | Record type / history | Access | Implemented / working | Notes |
|---|---|---|---|---|---|
| Nashua | [Planning Board archive](https://www.nashuanh.gov/AgendaCenter/Planning-Board-23) | Agendas/minutes, HTML/PDF; 2011–Feb 2025 | Feasible, no auth | Yes / yes | Current records moved; collected archive is stale by design. |
| Manchester | [Planning Board agendas](https://www.manchesternh.gov/Departments/Planning-and-Comm-Dev/Planning-Board/Agendas) | Agendas, HTML/PDF; multi-year, ~twice monthly | Feasible, no auth | Yes / yes | High-value commercial site-plan evidence. |
| Manchester | [Zoning Board agendas](https://www.manchesternh.gov/Departments/Planning-and-Comm-Dev/Zoning-Board/Agendas) | Zoning/sign cases, HTML/PDF; monthly | Feasible, no auth | Yes / yes | Corroborates planning addresses. |
| Salem | [Agenda Center](https://www.salemnh.gov/AgendaCenter) | Planning packets, CivicEngage/PDF; 2016+ | Feasible, no auth | Yes / yes | Scoped to Planning Board. |
| Bedford | [Agendas & Minutes](https://www.bedfordnh.org/129/Agendas-Minutes) | Planning agendas, CivicEngage/PDF; multi-year | Feasible, no auth | Yes / yes | Strong commercial descriptions. |
| Portsmouth | [Planning Board](https://www.portsmouthnh.gov/planportsmouth/planning-board) | Agendas/memos/actions, HTML/PDF; historical | Feasible, no auth | Yes / yes | Keeps primary documents to limit plan-set noise. |
| Dover | [Down to Business](https://www.dover.nh.gov/government/city-operations/executive/business-development/down-to-business/) | Business announcements, HTML; weekly archive | Feasible but throttled | Yes / degraded | Ten documents persisted before HTTP 429; retry/backoff added. Often too late for pre-opening sales. |
| Concord | [Planning Board](https://www.concordnh.gov/273/Planning-Board) | Legistar agendas/minutes; 2017+ monthly | Likely feasible, no auth | No / unverified | Prefer a Legistar adapter. |
| Dover | [Public Meeting Records](https://publicrecords.dover.nh.gov/public/1/deptnum/0/cab/Public_Meetings?autosearch=Planning+Board&index=public_body) | Agendas/minutes/files; historical | Needs stable-URL/terms review | No / unverified | Treeno Cabinet needs an adapter. |
| Merrimack | [Planning Board agendas](https://www.merrimacknh.gov/node/2261/agenda/2026) | Agendas/attachments, Drupal; annual archive | Automated client blocked | No / no (403) | Do not bypass; seek approved access. |

## Statewide and complementary sources

| Official source | Potential signal | Access assessment | Status / limitation |
|---|---|---|---|
| [Secretary of State QuickStart](https://quickstart.sos.nh.gov/online/BusinessInquire) | Business/trade-name registration | Interactive; bulk/API route unverified | Not implemented. Registration is weak without a location. |
| [OPLC license lookup](https://www.oplc.nh.gov/license-lookup) | Professional license status | Interactive; bulk/API route unverified | Not implemented. Avoid personal profiling. |
| [DRA tax licenses](https://www.revenue.nh.gov/licenses-certifications/tax-licenses-permits) | Meals/rooms and tax-license context | Information page, not a feed | Not implemented. |
| [DHHS Food Protection](https://www.dhhs.nh.gov/programs-services/environmental-health-and-you/food-protection) | Food-service licensing | Public dataset not identified | Investigate an approved establishment feed. |
| [Liquor Commission licensing](https://www.liquorandwineoutlets.com/about-us/divisions/enforcement-licensing) | Liquor application/license | Public application feed not identified | Investigate agency records, not lookup scraping. |

## Expansion priorities

1. Add current building-permit feeds for Manchester/Nashua or another high-volume municipality.
2. Add Concord Legistar and Dover public-meeting adapters.
3. Obtain an approved statewide food or liquor establishment feed.
4. Use company announcements, careers pages, and local news only as corroboration after terms
   review. Search results are research aids, not ingestion.
