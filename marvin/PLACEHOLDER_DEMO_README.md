# Person 2 placeholder forecast for PR #27

The reviewable Person 2 package is now in [person_2_part91_part135_forecast/](person_2_part91_part135_forecast/README.md) as individual source, test and result files. Open its [forecast report](person_2_part91_part135_forecast/results/report.html) for the seven-day Low, Medium and High scenarios.

This standalone package includes selected fleets' Part 91 and Part 135 activity and excludes Part 121. It replaces the earlier private-only ZIP demonstration in this PR. Its history and reservations remain synthetic, the Part 91 event profile is illustrative, and the Part 135 event factor transfers the observed 2022 LAX FAA Air Taxi five-day excess by assumption. FAA Air Taxi does not identify selected fleets. The invented 24 stands and inherited 75 space units are labeled sensitivities; the output flags overflow for manager review and never accepts or refuses an aircraft.

From `marvin/person_2_part91_part135_forecast/`, run `python -B run_demo.py` and `python -B -m unittest test_forecast_model test_operations_extension -v`. The package is separate from the shared `marvin/person_2_forecasting/` outputs and Nazar's coordinated dashboard release.
