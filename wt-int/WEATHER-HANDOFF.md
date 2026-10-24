# Message for Alan, Marvin and Elia

Guys, let's include weather as a separate factor in the FBO parking planner.
For this hackathon, we should test its effects on timing and usable space, not
pretend we already know the weather for February 11–17, 2027.

- **Alan:** identify official weather sources and historical observations. Keep
  observation time, forecast issue time, valid period and airport with each record.
  LAX weather alone may miss disruption at origins or next destinations.
- **Marvin:** keep base event demand separate from the weather adjustment. If
  we have aligned historical traffic/weather data, test whether adding weather
  improves held-out predictions. Otherwise call the adjustment a scenario;
  do not invent a fixed cancellation or demand-reduction percentage.
- **Elia:** test late departures, shifted arrivals and any operator-supplied
  usable-space restriction. Keep parked aircraft across midnight, preserve
  reserve, and recompute shortages. Bad weather can mean more aircraft remain
  parked even if fewer new arrivals occur.
- **Nazar:** the UI exposes 0–6h departure delay and an optional unavailable-space
  assumption, with before/after results and stale review detection. These controls
  are a disruption rehearsal, not a meteorological forecast. Arrival changes are
  a separate daily what-if, so the effects are not counted twice.

Our question is **“How much parking might we need if aircraft are delayed?”**,
not “How many people do we want?” We model aircraft and parking units, not people.
The tool never decides whether it is safe to land or depart.

For a later live integration, use official forecasts only within their valid
period and show source/age/expiry. Near-term terminal aerodrome forecasts commonly
cover 24 or 30 hours; monthly/seasonal outlooks are probabilistic climate context,
not hourly event-week predictions. The prototype currently has no live feed.

Sources checked 23 October 2026:
- [NOAA Aviation Weather Center: product scope and TAF validity](https://aviationweather.gov/help/data/)
- [NOAA: monthly and seasonal outlooks](https://www.climate.gov/news-features/understanding-climate/understanding-noaas-monthly-and-seasonal-climate-outlooks)
