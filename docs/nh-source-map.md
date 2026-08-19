# New Hampshire source feasibility map

Research checked 2026-08-19. “Implemented” means a collector was run or is test-covered in this repository; it does not imply normalized opportunities were produced. Unknown rate limits are handled conservatively with sequential requests, delay, timeouts, and content hashing.

| Municipality | Source | URL | Data | Format / history / cadence | Automatable / auth | Implemented | Notes |
|---|---|---|---|---|---|---|---|
| Nashua | Planning Board archive | https://www.nashuanh.gov/AgendaCenter/Planning-Board-23 | Agendas/minutes | HTML index + files; 2011–Feb 2025; meeting cadence | Likely yes / none | Yes, discovery/archive | Official page says current records moved to AMM; current portal adapter is still needed. |
| Nashua | Agenda Center RSS | https://nashuanh.gov/Rss.aspx | Agenda updates | RSS; historical archive categories | Likely yes / none | No | Candidate incremental feed; category URL must be verified. |
| Manchester | Planning Board agendas | https://www.manchesternh.gov/Departments/Planning-and-Comm-Dev/Planning-Board/Agendas | Agendas | HTML index + PDF; multiple years; ~biweekly | Yes / none | Yes | High-value site-plan evidence. Revised editions dedupe by content hash while retaining distinct provenance. |
| Manchester | Zoning Board agendas | https://www.manchesternh.gov/Departments/Planning-and-Comm-Dev/Zoning-Board/Agendas | Zoning agendas | HTML + PDF; multiple years; monthly | Likely yes / none | No | Same site pattern; add after planning parser stabilizes. |
| Salem | Planning Board Agenda Center | https://www.salemnh.gov/AgendaCenter | Agenda/material packets/minutes | CivicEngage HTML/PDF; 2016+; twice monthly | Likely yes / none | Yes, discovery | Broad index can contain other boards; collector needs category scoping refinement before production volume. |
| Concord | Planning Board / Legistar | https://www.concordnh.gov/273/Planning-Board | Agendas/minutes | Legistar-linked structured calendar; Feb 2017+; monthly | Likely yes / none | No | A Legistar adapter is preferable to scraping the city landing page. |
| Dover | Public Meeting Records | https://publicrecords.dover.nh.gov/public/1/deptnum/0/cab/Public_Meetings?autosearch=Planning+Board&index=public_body | Agendas, minutes, materials | Treeno Cabinet HTML/documents; historical; twice monthly | Needs technical/terms review / none visible | No | Public search is useful; adapter and stable document URLs need assessment. |
| Dover | Down to Business | https://www.dover.nh.gov/government/city-operations/executive/business-development/down-to-business/ | Economic-development newsletter | HTML archive; weekly | Likely yes / none | No | Promising enrichment and opening announcements, not primary proof by itself. |
| Portsmouth | Planning Board events | https://www.portsmouthnh.gov/planportsmouth/events | Agendas, packets, plans, decisions | HTML event pages + attachments; historical; meeting cadence | Likely yes / none | No | Rich project-level documents; event discovery/pagination needs a dedicated adapter. |
| Bedford | Agendas & Minutes | https://www.bedfordnh.org/129/Agendas-Minutes | Planning agendas/minutes | CivicEngage/files; multi-year; roughly twice monthly | Likely yes / none | No | Page coverage observed through 2025; confirm current 2026 location before enabling. |
| Merrimack | Planning Board agendas | https://www.merrimacknh.gov/node/2261/agenda/2026 | Agendas and project attachments | Drupal HTML + files; annual archive; twice monthly | Likely yes / none | No | Project attachments appear valuable; Drupal-specific adapter needed. |

## Statewide and complementary sources

| Jurisdiction | Source | URL | Data | Format / history / cadence | Automatable / auth | Implemented | Notes |
|---|---|---|---|---|---|---|---|
| New Hampshire | Secretary of State QuickStart | https://quickstart.sos.nh.gov/online/BusinessInquire | Business registrations/trade names | Interactive search | Bulk/API availability unverified | No | Registration alone is weak evidence. Do not automate until terms and a legitimate bulk/API route are confirmed. |
| New Hampshire | OPLC license lookup | https://www.oplc.nh.gov/license-lookup | Professional licenses | Interactive lookup | Bulk/API availability unverified | No | Limit to commercial entity/location evidence; avoid personal profiling. |
| New Hampshire | DRA tax licenses overview | https://www.revenue.nh.gov/licenses-certifications/tax-licenses-permits | Meals/rooms and other license context | Information page | No public dataset identified | No | Confirms licenses are pre-operation signals, but the page is not a record feed. |
| New Hampshire | DHHS Food Protection | https://www.dhhs.nh.gov/programs-services/environmental-health-and-you/food-protection | Food service licensing | Pages/forms | Dataset availability unverified | No | Investigate establishment lists without collecting personal data. |
| New Hampshire | Liquor Commission licensing | https://www.liquorandwineoutlets.com/about-us/divisions/enforcement-licensing | Liquor license information | Pages/lookup availability unclear | Needs terms/data assessment | No | High-value pre-opening signal if a public application/license feed is available. |

## Sources not yet treated as durable pipelines

Company pages, shopping-center announcements, franchise releases, company career pages, and reputable local news are valid corroborating sources, but each requires source-specific discovery and terms review. Search results are research aids, not an ingestion pipeline. Job boards that prohibit automated collection will not be scraped.
