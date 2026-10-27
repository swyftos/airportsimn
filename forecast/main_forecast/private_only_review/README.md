# Items 3 and 4 — private-only planning review for the data team

Prepared October 23, 2026. **This is a modeled private-only scenario, not an observed private-fleet count.** No air-taxi or charter count enters any forecast, historical comparison, sensitivity or assumption. The FAA observations retained here are *general aviation (GA) category* tower operations. [FAA's definition](https://aspmhelp.faa.gov/index/OPSNET_Reports__Definitions_of_Variables.html) excludes air carrier and air taxi from GA, but GA still includes civil activity beyond the selected private fleets. Its counts do not identify Part 91 status, the aircraft owner, the FBO or a booking.

The local package is for review. No repository commit or PR was made. Dashboard-facing P2 forecast filenames and columns were not changed; this review package uses a new clean private-only plan file.

## Method and scope

The [FAA ATADS/OPSNET LAX GA export](https://www.aspm.faa.gov/opsnet/sys/Airport.asp) gives **12,234 GA-category operations in 2025**. The included `ga_only_daily_source.csv` has 4,018 daily GA rows for 2015–2025, and `ga_only_monthly_check.csv` confirms the daily GA sums match the monthly GA totals in **132 of 132 months**. Neither file contains other airport traffic categories.

For the fictional FBO, the working baseline is:

    12,234 FAA GA operations
      × 50% hypothetical selected-private/FBO-eligible GA fraction
      × 20% assumed FBO capture of that filtered subset
      × 50% assumed arrivals
      ÷ 365 days
      = 1.676 expected arrivals/day

The **50% eligibility** and **50/50 direction split** are placeholders, not FAA measurements. The 20% FBO share comes from the [team assumptions ledger](assumptions.csv), but that row originally described a broader traffic scope; the data team must approve using it for the filtered GA subset. This method does not treat every airport or every GA operation as a potential customer. `private_eligibility_sensitivity.csv` shows the result for eligible fractions from 0% to 100%; 100% is an upper scenario, not an assertion.

The team’s **47% light / 33% midsize / 20% large** aircraft mix and 1 / 1.5 / 2.5 space units by size give **1.465 mean space units** per modeled aircraft. The inherited **75-space-unit** ramp figure is an [unverified P3 estimate](parking/assumptions_p3.csv), not known free PPR capacity.

## Item 3 — requested versus acceptable movements

The event multipliers are **synthetic**, with Medium arrival factors 1.25, 1.60, 2.20, 1.80, 1.10, 1.00, 1.00 and Medium departure factors 1.00, 1.00, 1.10, 1.30, 2.50, 1.80, 1.20 for Feb 11–17. Low applies half of each incremental uplift; High applies 1.6 times it. These are explicit planning choices, not measured Super Bowl or private-fleet effects. The plan rounds requested aircraft upward and applies the FBO parking ceiling and a hypothetical half-day departure turnover.

| 2027 date | Low land / leave | Medium land / leave | High land / leave |
| --- | ---: | ---: | ---: |
| Feb 11 | 2 / 2 | 3 / 2 | 3 / 2 |
| Feb 12 | 3 / 2 | 3 / 2 | 4 / 2 |
| Feb 13 | 3 / 2 | 4 / 2 | 5 / 2 |
| Feb 14 | 3 / 2 | 4 / 3 | 4 / 3 |
| Feb 15 | 2 / 3 | 2 / 5 | 2 / 6 |
| Feb 16 | 2 / 3 | 2 / 4 | 2 / 4 |
| Feb 17 | 2 / 2 | 2 / 3 | 2 / 3 |

Under this particular 75-unit estimate, no landing request exceeds the parking proxy. A lower actual free capacity could change the recommended PPR plan. Low is routine review; Medium checks Feb 13 arrivals and Feb 15 departures; High checks five Feb 13 arrivals and six Feb 15 departures against real stand sizes, opening inventory and hourly slots. The full `daily_private_only_plan.csv` contains requested versus acceptable counts, end-of-day aircraft and scenario factors.

The FAA [capacity-profile index](https://www.faa.gov/airports/planning_capacity/profiles) says these profiles replaced the older Benchmark Report. Its listed [LAX profile is from 2014](https://www.faa.gov/sites/faa.gov/files/airports/planning_capacity/profiles/LAX-Airport-Capacity-Profile-2014.pdf), with a **133–143 airport-wide gross operations/hour** range in instrument conditions. Our largest modeled FBO day is eleven movements, so it does not challenge the gross physical scale; this **does not establish spare 2027 runway slots**, because other airport traffic and hourly peaking are unknown. FBO/PPR parking remains the primary acceptance constraint.

## Item 4 — ground stay and category ratio

The team’s illustrative **40% same-day / 45% overnight / 15% multi-day** mix and 1.1-day ordinary dwell remain unchanged. The plan estimates 40% of admitted new arrivals leaving that day and 60% remaining at least overnight. It also carries opening aircraft forward day by day. These are cohort estimates, not matched aircraft histories.

The modeled same-day and overnight cohorts are **100% private by scenario definition**. Their **observed private-versus-charter ratio is unknown**; no real ratio can be calculated from FAA GA totals. This review supplies **no charter or air-taxi volume**. Real fleet/FBO records are required to establish the actual departure and overnight composition.

## Historical context, kept separate from private-only forecast

The `ga_category_historical_comparisons.csv` table compares 2023–2025 **FAA GA-category** counts with ordinary weekdays/weekends, Thanksgiving, Christmas/New Year, July 4, Oscars and Coachella dates. These are descriptive airport comparisons, not selected-fleet traffic or event-caused increases. Date sources are the [OPM holiday calendar](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/), Academy pages for [2023](https://www.oscars.org/oscars/ceremonies/2023/U--Z), [2024](https://www.oscars.org/oscars/ceremonies/2024) and [2025](https://www.oscars.org/oscars/ceremonies/2025), and Coachella announcements for [2023](https://blog.youtube/news-and-events/coachella-livestream-youtube-goldenvoice-2023/), [2024](https://blog.youtube/news-and-events/coachella-2024-livestream-how-to-watch/) and [2025](https://blog.youtube/news-and-events/the-countdown-to-coachella-weekend-1-begins/). Coachella is in Indio; its LAX date comparison is especially weak as a causal analog.

The repo’s [LVI surge analysis](sources/airport_traffic/data/processed/superbowl_lvi_surge.csv) gives **+3.1% for the LAX GA category** after its comparison-year adjustment. That 2022 result is retained in `lvi_ga_only_comparison.csv` for context, excluded from the ordinary baseline and **not** applied as a private-fleet multiplier. The review has no comparable selected-fleet ratios for LVII–LX; gaps are recorded in `super_bowl_private_scope_gaps.csv`. Unknown does not mean zero.

[OPM lists February 15, 2027](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/) as Washington’s Birthday, commonly called Presidents Day. No holiday effect is included in the primary forecast. `presidents_day_sensitivity.csv` shows hypothetical −10%, unchanged and +10% cases only; no aviation effect is measured.

## Source path and files

`source_links.csv` gives each direct source URL, its role and its limitation. The raw GA source can be checked at [FAA ATADS/OPSNET](https://www.aspm.faa.gov/opsnet/sys/Airport.asp), the team's [daily export PR](an earlier team pull request) and [monthly export](sources/airport_traffic/data/processed/opsnet_lax_monthly.csv). The GitHub paths may require team repository access. `rebuild_private_only.py` regenerates the modeled plan, historical GA analogs, sensitivity tables, assumptions ledger and metadata from the included GA-only extract.

The local `assumptions.csv` uses the team's 11-column schema and includes only this review's relevant source figures, inherited assumptions and 21 date/scenario outcomes. The former mixed-scope plan and eligibility sensitivity have been removed from this package.

The data team should review the private-eligible fraction, applicability of the 20% FBO share, direction split, actual free parking, opening inventory and operating cost before any integration. The GA-category comparisons cannot validate private-only forecasting accuracy.

