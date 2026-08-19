# Phase 0 validation log

## Current experiment

- Start: 2026-08-19
- Geography: New Hampshire; priority municipalities are Nashua, Manchester, Salem, Concord, Dover, Portsmouth, Bedford, and Merrimack.
- Connected sources: three official municipal planning-board discovery pages.
- Method: preserve source artifacts, hash-deduplicate, extract text, normalize evidence to signals, resolve organization/location, score opportunities, then manually label results.

## Results to date

A bounded first live run collected 14 official documents and produced 14 raw records: Nashua 4, Manchester 5, and Salem 5. PDF extraction was inspected; Manchester agendas and Salem Planning Board packets contained readable project details. The conservative Manchester normalizer found seven commercial project IDs and produced six deduplicated organization/location signals and six candidate opportunities. All score 67.1 (`PLANNING`); none crosses the high-confidence threshold. Zero have yet been manually verified actionable, so the measured actionable conversion rate remains unavailable rather than assumed.

An initial Salem run exposed a scoping defect and downloaded five unrelated commission agendas. Those database records were removed, the collector was scoped to the Planning Board section, a regression test was added, and the corrected five-document sample was collected. This incident is retained here because collector precision is part of the experiment.

## Manual review

An opportunity counts as actionable only when it represents a real current commercial activity, has an identifiable location or market, offers plausible vendor timing, is not merely an established-location administrative filing, and every key claim traces to source evidence. Review verdicts are `true_positive`, `false_positive`, `uncertain`, `duplicate`, and `not_actionable`.

## Failure modes under evaluation

- agenda revisions and agenda/minute duplication;
- property-owner or engineering-firm names mistaken for operating brands;
- residential/site-only projects with no commercial tenant;
- established businesses performing routine maintenance;
- registrations without physical operations;
- scanned PDFs with unreadable text;
- projects delayed, cancelled, or stale;
- unresolved DBA/legal-entity relationships.

## Decision

**PROMISING / MORE DATA NEEDED**

The source research shows recurring, official, timely planning material across the target municipalities, and the prototype can preserve it with provenance. It has not yet established weekly actionable volume or precision because automated project extraction, cross-source normalization, and a manually reviewed live corpus are incomplete. Building customer SaaS now would be premature; the next decision gate is a multi-week collection and review benchmark across several municipalities.
