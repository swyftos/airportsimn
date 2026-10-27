# Person 2 forecast package (Part 91 and Part 135)

The package in `category_forecast/` forecasts FBO arrivals and departures for February 11–17, 2027 from observed FAA daily counts (general aviation as Part 91, air taxi as Part 135), with measured Super Bowl scenarios, a learned Presidents Day effect and observed NOAA weather effects. Shares, hourly shapes, service times, prices and the VIP pause are assumptions or placeholders; see its README for the full list.

The live forecast that feeds the parking optimizer and dashboard is still `main_forecast/`. This package reports both parts separately so the team can choose the scope.
