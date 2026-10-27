# Step 4: Super Bowl historical surge benchmark

Investigates aviation activity around Super Bowl LVI (Los Angeles, Feb 13,
2022) per the Step 2 task sheet, and extends to Super Bowl LVII (Phoenix,
Feb 2023) and LVIII (Las Vegas, Feb 2024) as additional comparable
mega-events. Feeds the "historical surge multiplier" signal in the
forecast model (project brief §3.1) — the primary driver of the shape of
the event-week surge curve, not a single flat ratio.

**Status: qualitative/directional benchmark, not a precise measured
multiplier.** No source found gives an official, reconciled daily
arrivals/departures count for any of the three events. All figures below
are industry trade press and aircraft-tracking services (FlightAware,
WingX, Argus TraqPak), which disagree with each other significantly even
for the same event. This is documented as a known limitation, not
resolved by picking whichever number is largest.

## Why LAX's own historical data can't answer this (recap)

The parking team's monthly LAX movement data shows Feb 2022 only ~6.8% above the
January/March 2022 average — well within the normal year-to-year range for
an ordinary February (-6.7% to +11.1% across other years). A one-week
event surge is diluted into a 28-day average at monthly granularity, and
most Super Bowl LVI business-jet traffic went to satellite GA fields
(Van Nuys, Hawthorne), not LAX's own commercial-dominated ramps. Monthly
LAX data cannot see this event. See `data_sources_traffic.md` for the
underlying finding.

## The COVID-era complication

Super Bowl LVI (Feb 2022) landed during a period when **commercial** air
travel was still clearly suppressed: LAX's air-carrier movements were
~37,100 that February, about 20% below the pre-COVID Feb 2018/2019 level
of ~46,000-47,400 (source: `lax_monthly_movements.csv`). That would argue
for caution using LVI as a clean precedent.

But **business/private aviation ran the opposite direction during this
window**: high-net-worth travelers avoided commercial flying throughout
2021-2022, which increased private-jet demand even as commercial traffic
stayed down. This is consistent with WingX's reporting that Super Bowl
LVII (2023) arrivals were actually ~25% *lower* than Super Bowl LVI
(2022) — i.e., LVI's business-jet volume may have been *elevated* by
COVID-era shifts away from commercial flying, not suppressed. The
direction of any COVID effect on the parking-relevant signal (private/GA
traffic, not commercial) is genuinely unclear from available sources, not
confidently "too low" or "too high."

**Practical conclusion**: don't treat LVI's absolute private-jet numbers
as either the floor or the ceiling of a "normal" future surge. Use LVII
and LVIII (both clear of this ambiguity) for the quantitative surge-scale
benchmark, and keep LVI for what it uniquely offers: LA/LAX-specific
operational and logistics evidence.

## Super Bowl LVI — Los Angeles, Feb 13, 2022 (qualitative/logistics reference)

- FAA ran a formal GA parking **reservation program** at LA-area airports,
  including Van Nuys (VNY) and Hawthorne (HHR), Feb 6-14, 2022 — direct
  evidence the agency anticipated real capacity pressure at those fields,
  not at LAX itself.
- NBAA noted reservation slots were **more limited than the prior two
  Super Bowls** (both held in Florida), prompting a push toward drop-and-go
  operations over overnight parking.
- TFR over SoFi Stadium ran 2:30-8:30pm PST game day, 10nm inner
  core / 30nm outer ring — standard mega-event airspace restriction,
  not itself a traffic signal.
- ~140 private jets reported departing within hours post-game via ADS-B
  tracking (Plane & Pilot Magazine) — a single enthusiast tracking effort,
  not an official count. Order-of-magnitude only.
- Avfuel supplied 56,000+ gallons of sustainable aviation fuel at nearby
  FBOs specifically for the event — a concrete, sourced logistics number,
  though not a traffic count.
- Industry sources describe traffic as "returning to pre-pandemic Super
  Bowl levels" with a trend toward fewer passengers per jet.

**Use**: confirms the *pattern* (GA overflow routes to satellite fields,
not the host-city hub airport; reservation/capacity programs are a
standard real-world response; drop-and-go gets emphasized under tight
capacity) — not a usable number.

Source: [FAA Super Bowl LVI Flight Requirements](https://www.faa.gov/newsroom/super-bowl-lvi-flight-requirements-ga-pilots),
[NBAA Super Bowl LVI airspace guidance](https://nbaa.org/aircraft-operations/airspace/regional/super-bowl-lvi/),
[Plane & Pilot Magazine, "The Great Super Bowl LVI Rush Hour"](https://planeandpilotmag.com/super-bowl-rush-hour/)

## Super Bowl LVII — Phoenix/Glendale, Feb 12, 2023 (quantitative benchmark)

Multiple trackers, materially different numbers depending on window and
definition:

| Source | Measure | Figure |
| --- | --- | --- |
| FlightAware (via AIN/BJT) | Business aircraft arrivals, 8 metro airports, 5 days pre-game | 1,700+ (Scottsdale 623, Sky Harbor 533 leading) |
| Scottsdale Airport (city release) | Corporate jet operations, <24h over Super Bowl weekend | 490; 911 aircraft parked overnight Thu-Mon |
| Cutter Aviation (FBO, self-reported) | Aircraft handled at KPHX + KDVT, 5-day span | 481 + 135 = 616 |
| Argus TraqPak | Departures, 9pm Sun to midnight | 900+ (KSDL and KPHX ~243 each) |
| WingX | Arrivals for the event itself | 562 (4th busiest of past 5 years); reported as **-25% vs. LVI (2022)** |

A ramp reservation system ran Feb 7-14 at metro Phoenix airports;
limited parking pushed operators toward drop-and-go.

Source: [AIN, "Arizona FBOs Score In Super Bowl Traffic"](https://oldain.ainonline.com/aviation-news/business-aviation/2023-02-14/arizona-fbos-score-super-bowl-traffic),
[Scottsdale Airport press release](https://scottsdaleaz.gov/news/scottsdale-airport-takes-off-during-super-bowl-lvii)

## Super Bowl LVIII — Las Vegas, Feb 11, 2024 (quantitative benchmark)

- FAA pre-game estimate: ~1,750 additional aircraft at Las Vegas-area
  airports, up to 700 more private aircraft parked over the week — a
  projected 10%+ increase over both 2023 (LVII) and 2019.
- WingX actual count: **882 private flights** into Las Vegas over the
  weekend — second-highest Super Bowl on record behind LVII's **931**
  (WingX's own all-time tracker, inconsistent with the 562 "event arrivals"
  figure it separately reported for LVII above — different count windows,
  not a correction).
- Four main GA/business airports (North Las Vegas, Henderson Executive,
  Harry Reid's two FBOs, Boulder City) combined have only ~500 parking
  spaces, far short of demand — most traffic relied on drop-and-go rather
  than overnight parking.

Source: [CNN/ABC17, "Record number of private jet flights expected"](https://abc17news.com/money/cnn-business-consumer/2024/02/09/its-not-just-taylor-swift-record-number-of-private-jet-flights-expected-for-this-years-super-bowl/),
[Boston Globe, "Private jets in Las Vegas"](https://www.bostonglobe.com/2024/02/14/science/private-jets-in-las-vegas/)

## What this means for the forecast model's event multipliers

1. **Order of magnitude, not a precise ratio**: across LVII and LVIII,
   a Super Bowl's private/business GA surge runs from several hundred to
   roughly 900-1,000 tracked aircraft operations across a metro's GA
   airports over the event week, concentrated in the 1-2 days immediately
   before and after game day. Use this to sanity-check the *scale* of
   The forecast team's Low/Medium/High multipliers, not to derive an exact number.
2. **Shape, not magnitude, is the more defensible transferable signal**:
   all three events show the same qualitative pattern — arrivals build in
   the days before the game, departures spike sharply in the hours/day
   immediately after, and capacity constraints push operators toward
   drop-and-go over overnight parking once reservation slots tighten.
   This shape (not the absolute counts) is what should most directly
   inform the arrival/departure multiplier curves.
3. **Source disagreement is itself a documented limitation**: FlightAware,
   WingX, and Argus TraqPak diverge by as much as 3x for the same event
   depending on counted window and airport set. Any number quoted from
   this benchmark to judges should be presented as a range with named
   sources, not a single authoritative figure.
4. **LVI's numbers should not be blended into the LVII/LVIII magnitude
   estimate** given the unresolved COVID-direction ambiguity above; its
   value is in the LA-specific operational pattern, not the count.

## Classification for the assumptions ledger

| Driver | Classification | Note |
| --- | --- | --- |
| Surge event-week shape (build-before / spike-after) | benchmark | Consistent across LVI, LVII, LVIII; directionally reliable |
| Surge magnitude (order of several hundred to ~1,000 aircraft) | benchmark | From LVII/LVIII only; wide source disagreement, use as a range |
| LVI absolute private-jet counts | assumption (not used quantitatively) | COVID-direction ambiguous; qualitative/logistics reference only |
| Any single numeric multiplier derived from the above | assumption | Must be explicitly owned by whoever sets the forecast team's event multipliers; this document does not prescribe one number |
