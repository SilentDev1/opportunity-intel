# Historical validation — Phase 0.6

Historical backfill is reported separately from live observation.

## Salem issued permits

- Official weekly permit reports collected: 15
- Covered event dates: 2025-06-23 through 2025-09-09 (79 days)
- Commercially filtered permit records preserved: 70
- High-value change-of-occupant, tenant-fit, construction, restaurant, or occupancy signals: 17
- Distinct location-level candidates: 16
- Manual result: 11 real but stale commercial events and 5 false positives

The collector retains permit number, issue date, address, description, and the public business
name when extractable. Residential-only work is filtered before normalization. Historical source
availability proves that these records existed; it does not prove exactly when a production
system would first have fetched them. `signal_date` retains the permit issue date while
`detected_at`/document retrieval retain the actual backfill time.

The 16 candidates include recognizable location events such as Go Games, Perfumania, Lululemon,
Caffè Nero, Casino Salem, Five Below, Sal's Pizza, Designer Perfume, Dairy Queen, and Salt & Straw.
They require retrospective opening verification before they can be counted as historical wins.

## License experiment

The official 2026 Salem hawker/peddler list produced 21 license records. Personal applicant names,
phones, and vehicle details were intentionally not retained. These licenses describe itinerant
sales activity, provide no new physical business location, and generated zero opportunities.
This license class is accessible but low value for the product thesis. Food, liquor, or local
change-of-ownership licenses remain higher-priority acquisition targets.

## Historical conclusion

Permit data materially increases signal diversity and reveals location events, but this first
blind parser run had a 31.3% false-positive rate: generic certificate-of-occupancy matching
admitted four residential homes/ADUs, and a temporary seasonal store was not useful. Targeted
residential and temporary-use exclusions were added after review. This one backfill does not
establish current weekly lead flow or opening outcomes. It brings the corpus to 61 reviewed
opportunities—not the 150-candidate gate.
