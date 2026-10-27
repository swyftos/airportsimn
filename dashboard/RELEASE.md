# One coordinated team release

Owner: the dashboard team. Run from any directory, using Python 3.10+ with numpy and pandas installed and Git available:

```sh
python3 dashboard/scripts/release_team.py
```

The command builds an isolated copy of the repository’s tracked working files (including staged changes), then runs:

1. The data team: validate daily airport inputs, build estimated FBO history, then build the baseline and assumptions.
2. The forecast team: convert the current source to estimated FBO inputs; compare its input years/share with the data team’s baseline policy; produce forecasts and uncertainty.
3. The parking team: check opening inventory against the new ordinary forecast, then regenerate standard, ordinary, delayed and carryover parking outputs.
4. The data team: refresh the consolidated root assumption ledger.
5. The dashboard team: reproduce the complete parking pipeline; stamp the 21-file manifest, including the forecast team's holiday-history input; run forecast, parking and dashboard tests.
6. Install only the declared generated outputs, the report and the manifest, after every check passes.

No stage downloads data or changes anyone’s model code. The present the forecast team converter uses observed daily FAA LAX GA and air-taxi counts and applies the team's documented FBO share. The forecast receives the generated long holiday-history input for Presidents' Day. New producer entry points or schemas need a coordinated script update. Stage new scripts/inputs with `git add` first so they are included in the snapshot.

## Current provisional assumptions

The data team and the forecast team currently use 2023–2025 with a combined assumed 10% FBO share, so the year/share comparison has no mismatch. This does not validate the FBO share, event multiplier, forecast accuracy, or ramp capacity; the release remains provisional pending the data team and team review. The forecast's 2016–2019 airport rows are used only to estimate a scale-free Presidents' Day factor, not as ordinary traffic training observations.

If a future producer update creates a year/share mismatch, the default command stops before forecasting or replacing outputs. To build an explicitly provisional demonstration while recording that mismatch:

```sh
python3 dashboard/scripts/release_team.py --allow-provisional-mismatch
```

This exception permits only the reported year/share disagreements. It does not skip inventory, schema, file integrity, numerical coherence or test checks, and never marks assumptions approved. Event multipliers, capacity and model accuracy still require review. Do not use it to claim a final agreed forecast.

Add `--check-only` to either command to build and test without installing outputs. The staged directory is removed afterward. A successful installed release writes `dashboard/team_release_report.json` with the mismatch list, override flag, output hashes and matching run ID.

## Failure and update behavior

- Any failed stage stops the command. Working outputs remain unchanged during generation and testing.
- If a tracked working file changes during the build, installation stops rather than overwriting that edit.
- If opening inventory no longer matches the new baseline, the parking team updates the assumption ledger; the coordinator does not silently change it.
- Files are individually replaced and the manifest is written last. This is not an atomic directory swap; the dashboard rejects an intermediate mixed release. A caught installation failure restores previous output bytes. After abrupt process termination, rerun before refreshing.
- Only one coordinated release can run at a time. The ignored lock is `dashboard/.state/team-release.lock`. If a crash leaves it behind, confirm no release process remains before removing that lock.
- Close editing sessions during publication. Do not run independent producer scripts concurrently with the coordinator.

After success, inspect `git diff`, commit all generated outputs and the report together, and push one PR. After it merges, teammates pull and click **Refresh current source** in The Intelligent FBO. This command does not commit, push, fetch, approve a forecast, or authorize an operation.

The older `forecast/main_forecast/run_provisional.py` is retained for compatibility, but the coordinated command above is the team entry point. Do not run both for one release.
