# Four-week live validation

This directory contains observed cohorts only. Future weeks must not be pre-created.

Week boundaries use America/New_York calendar dates. A new candidate is counted once by
`first_detected_at`. Later signals on the same organization/location are reported as an existing
opportunity update; stage-history changes are reported separately. Historical event records
retrieved during a live week remain in the historical report, not fresh-opportunity volume.

Run collection on a schedule with:

```bash
uv run opportunity-intel collect-all --limit 20
uv run opportunity-intel process
```

Each weekly report must record attempted/successful sources, new documents/signals/entities/
locations/candidates/actionables, existing updates, transitions, review outcomes, and failures.
