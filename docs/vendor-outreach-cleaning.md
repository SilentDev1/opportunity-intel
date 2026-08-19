# Commercial-cleaning vendor outreach

## Short outreach message

Hi — I’m testing a tool that finds New Hampshire businesses before they open or expand. I have five current local opportunities and want to learn whether they would actually be useful to a commercial-cleaning company. This is not a sales pitch and there is no charge; I’m looking for candid feedback in a 15-minute review. Would you be open to taking a look?

## Test workflow

1. Send `data/exports/vendor-test/cleaning-current.csv`; do not send the historical packet as current work.
2. Ask the per-lead questions in `data/vendor-feedback-template.csv`.
3. Ask the overall weekly-feed and $49/$79/$99/$149 pricing questions once per vendor.
4. Import the completed file with `opportunity-intel import-vendor-feedback --path FILE`.
5. Regenerate results with `opportunity-intel write-vendor-validation-report`.
6. If the vendor acts, record the event in `data/vendor-outcomes-template.csv` and import it with `opportunity-intel import-vendor-outcomes --path FILE`.

Never imply that a listed business has requested cleaning. Ask whether the evidence makes it a worthwhile prospect.
