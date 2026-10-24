# LAX private-aircraft capacity and landing cost research (Items 1 & 2)

Prepared by Alan. Scope: FAR Part 91 (private) only, per team scope
narrowing — Part 135 (charter) and Part 121 (commercial) are explicitly
excluded from the numbers below wherever the underlying source allows
that distinction (noted per item where it does not).

## Item 1a — Apron/hangar capacity

**Primary finding: Atlantic Aviation's dedicated corporate hangar at
LAX, confirmed built and opened 2016** (not just proposed — an earlier
2013 CEQA filing for this same project was initially mistaken for the
current state; verified independently that construction completed).

| Source | Finding |
|---|---|
| https://live.ainonline.com/aviation-news/business-aviation/2016-04-19/lax-gets-first-corporate-aircraft-hangar | Grand opening confirmed April 2016. As-built: **37,000 sq ft hangar + 5,000 sq ft office**. Shelters up to **5 large-cabin/ultra-long-range jets simultaneously**. $9M total project. First such dedicated structure at LAX. |
| https://atlanticaviation.com/news/atlantic-opens-first-dedicated-corporate-hangar-at-lax | Atlantic's own press release (Oct 2016), corroborates the opening. |
| https://ainonline.com/aviation-news/2014-03-20/atlantic-aviation-starts-construction-36500-sq-ft-genav-hangar-lax | 2014 construction-start figure (36,500 sq ft, $7.8M budget) — shows the project's progression from proposal to final built size; minor size changes between proposal and as-built are normal, not a discrepancy. |
| https://www.ainonline.com/aviation-news/business-aviation/2008-02-08/atlantic-completes-los-angeles-and-santa-barbara-fbos | 2008, 13-acre (566,280 sq ft) total ramp estimate (already in the ledger as NAZAR-A02/ELIA-ramp_area_m2) — kept as the broader ramp-area figure, separate from this hangar-specific number. |

**Classification**: public data (high confidence) for the hangar specs
— independently corroborated across Atlantic's own release and AIN trade
press, describing a real, completed, operating structure.

**Additional detail recovered from the original 2013 LAWA project filing**
(decrypted and extracted locally; this is the primary CEQA-style document
behind the AIN reporting above, not a separate source): in 2004, the
predecessor operator (Mercury Air Group, acquired by Atlantic in 2007)
built a 10,059 sq ft FBO customer service/customs building plus a
**concrete aircraft parking apron** on the same leasehold — a real
construction record, though the filing does not give the apron's area.
The filing also explicitly states the 2013/2016 hangar project's purpose:
letting owners who previously based their aircraft elsewhere **stop
flying in empty to position the aircraft** before a passenger trip,
cutting operations per customer trip from 4 (empty positioning in/out,
then passenger in/out) to 2 (based at LAX, passenger in/out only). See
`alan/docs/traffic_categories_and_fleet_mix.md` section 1.3 for how this
grounds the project's positioning-flight contamination discussion in a
real, sourced example rather than a general statement.

## Item 1b — Runway throughput (sanity-check ceiling only)

Same FAA source Marvin also used for his Item 3 cross-check — see
`marvin/person_2_forecasting/private_only_review/README.md`.

| Source | Finding |
|---|---|
| https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/LAX-Airport-Capacity-Profile-2014.pdf | Official FAA LAX Airport Capacity Profile. Visual: 167-176 ops/hr (81% of year). Marginal: 147-153 ops/hr (11%). Instrument: 133-143 ops/hr (8%). This is LAX's **total** runway ceiling shared by all traffic (commercial, charter, private) — cannot be broken out by flight type. Underlying data from FY2009-2010 (dated). |

Not duplicated as a separate ledger row since Marvin's MARVIN-runway
assumption already captures this exact figure for the same purpose.

## Item 2 — Landing cost during Super Bowl week

**Baseline landing fee (official, current)**:

| Source | Finding |
|---|---|
| https://www.lawa.org/general-aviation-fees-lax | **$7.85 per 1,000 lbs**, all weights billed, effective March 1, 2026, approved by LAWA Board of Airport Commissioners Jan 2026. Billed on arrival, max landing weight, fixed-wing only, touch-and-goes billed. Exemptions: based aircraft, federal/military, state/county government, Angel Flights, air ambulances, firefighting, maintenance/test flights. Applies to the "General Aviation" billing category broadly — LAWA's schedule does not separate private from charter; both pay this rate. Parking/overnight fees not listed on this page (gap, not an oversight). |

**Super Bowl week premium — thin evidence, documented honestly rather
than forced**:

| Source | Finding |
|---|---|
| https://spectrumlocalnews.com/us/snplus/entertainment/2024/02/02/taylor-swift-super-bowl-private-jet-parking (AP wire, syndicated) | LVIII 2024, Las Vegas: aircraft parking fees **unchanged** from standard ($20-150/day by size). Four closest airports (~475 spaces combined) full. Same article separately notes Phoenix-area pads (1,100 total) also reported full — a nearby-alternative detail, not independent LVII-specific reporting. |
| https://www.businessinsider.nl/from-jet-parking-to-jostling-for-luxury-hotels-billionaires-can-spend-six-figures-at-the-super-bowl/ | LIX 2025, New Orleans: $3,000/day private jet parking reported. Airport not specified, not confirmed as an official rate — treat as directional, not a hard figure. |

No landing-fee-specific surge data found for any of the 5 recent Super
Bowls (LVI-LX). Across all three events with any pricing data, the
consistent pattern is **scarcity (full parking), not price increases**
— airports did not appear to raise landing/parking fees for the event,
they simply ran out of space. This is a useful qualitative finding for
the project's PPR-cap guidance even without a hard cost multiplier.

## Open items / not yet resolved

- The exact split between private (Part 91) and charter (Part 135)
  landing/parking costs is not available anywhere — LAWA's fee schedule
  and every Super Bowl cost report found treat "general aviation" as one
  undifferentiated category.
- No source quantifies a landing-fee percentage increase during event
  week at any of the 5 recent Super Bowls — the scarcity-not-price
  finding above is the best available substitute for that question.
