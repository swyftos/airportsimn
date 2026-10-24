# Alan: LAX FAA Airport Master Record (5010)

Retrieved 2026-10-23. This is the Person 1 / Step 2 contribution to the
shared data workstream: runway specs and based-aircraft count for LAX.
Merge these source IDs into the eventual team `data_sources.md`; the other
Step 2 pieces (apron area — Nazar, LAWA/BTS — Elia) remain separately owned.

## Result and recommended use

Runway specs are complete and high-confidence from the official FAA 5010
record, cross-checked against AirNav (exact match on all four runways).

**Based-aircraft count is NOT available.** The 5010's BASED AIRCRAFT block
(fields 90-96: single engine, multi engine, jet, helicopters, total,
gliders, military, ultra-light) is entirely blank — labeled "Source:
Self-reported" with nothing reported. AirNav independently shows no based-
aircraft figure either. Treat this as a confirmed gap, not a missing lookup.
This is plausible given LAX is an almost entirely commercial/Part 121 hub;
most LA-area GA based aircraft are at satellite fields (Van Nuys, Santa
Monica, Hawthorne, Long Beach), not LAX.

**Correction to an earlier verbal note:** a "90 single engine" figure was
referenced in conversation before this record was reviewed line-by-line.
That number does not appear in the actual data — "90" is the 5010 form's
field number for "SINGLE ENG," not a reported count. No based-aircraft
figure should be attributed to LAX from this source.

## Source register

| ID | Source and date | What it supports | Reliability and limitation |
|---|---|---|---|
| ALAN-S01 | FAA Airport Master Record (5010), printed 2026-10-23, effective 2026-10-01, via https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/ (retrieved through ADIP) | Ownership, acreage, elevation, all 4 runway specs (length/width/surface/PCN), control tower status | High for everything populated. Based-aircraft block (fields 90-96) is blank in the source itself — not a reliability issue, a genuine data gap. |
| ALAN-S02 | AirNav LAX page, https://www.airnav.com/airport/LAX, retrieved 2026-10-23 | Cross-check of runway specs (exact match); confirms no based-aircraft count published | Secondary aggregator of FAA 5010 data, not a primary source. Used only as a corroboration check, not cited independently for any number not already in ALAN-S01. |

Local copies: `../data/raw/alan_5010/LAX_5010_master_record.pdf` (the printed
5010 record, all 5 pages) and `../data/raw/alan_5010/airnav_lax_excerpt.md`
(AirNav extraction notes).

## Known limitations

- Acreage (3,500) is whole-airport, not FBO ramp/apron area — that's
  Nazar's separate apron workstream; do not substitute one for the other.
- No based-aircraft count, of any kind, is attributable to LAX from public
  5010/AirNav data. If the forecast/baseline model needs a based-aircraft
  reserve figure for LAX, it must be a tagged **assumption**, not public
  data, and should account for LAX's based GA population being near-zero
  relative to its commercial operations.
- Runway data is current as of the 5010's stated effective date
  (2026-10-01); re-pull before the hackathon if the window shifts materially.

## Handoff

- `alan/data/processed/master_record_alan.csv`: all extracted fields,
  tagged `public data` (populated fields) or `public data (gap)` (blank
  based-aircraft fields), with source IDs.
- `alan/data/raw/alan_5010/`: archived source PDF and AirNav excerpt.

Blank CSV numbers mean "field exists but FAA/AirNav reported nothing" —
never silently treat as zero. `classification` follows the team's
three-way tag: **public data**, **benchmark estimate**, or **assumption**.
These rows merge into the team's final `data_sources.md` and
`assumptions.csv` alongside Nazar's apron contribution and Elia's
LAWA/BTS contribution.
