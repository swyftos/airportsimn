# One coordinated team release

Owner: Nazar. Run from any directory, using Python 3.10+ with numpy and pandas installed and Git available:

```sh
python3 nazar/scripts/release_team.py
```

The command builds an isolated copy of the repository’s tracked working files (including staged changes), then runs:

1. Alan: validate monthly inputs, build estimated daily airport history, then build the baseline and assumptions.
2. Marvin: convert the current source to estimated FBO inputs; compare its input years/share with Alan’s baseline policy; produce forecasts and uncertainty.
3. Elia: check opening inventory against the new ordinary forecast, then regenerate standard, ordinary, delayed and carryover parking outputs.
4. Alan: refresh the consolidated root assumption ledger.
5. Nazar: reproduce the complete parking pipeline; stamp the 20-file manifest; run forecast, parking and dashboard tests.
6. Install only the declared generated outputs, the report and the manifest, after every check passes.

No stage downloads data or changes anyone’s model code. The present Marvin converter reads the same monthly source as Alan, not Alan’s weekday-weighted baseline; the coordinator does not silently reconcile that methodological difference. New producer entry points or schemas need a coordinated script update. Stage new scripts/inputs with `git add` first so they are included in the snapshot.

## Current provisional mismatch

Today Alan uses 2023–2025 with a 20% capture share. Marvin’s converted history spans 2016–2019 and 2023–2025 at 25%, with a separate chronological training/calibration/test split. The default command stops before forecasting or replacing outputs when these policies disagree. It does not claim that matching input windows alone validates the model’s fitted training split.

To explicitly reproduce the existing provisional demo while recording those disagreements:

```sh
python3 nazar/scripts/release_team.py --allow-provisional-mismatch
```

This exception permits only the reported year/share disagreements. It does not skip inventory, schema, file integrity, numerical coherence or test checks, and never marks assumptions approved. Event multipliers, capacity and model accuracy still require review. Do not use it to claim a final agreed forecast.

Add `--check-only` to either command to build and test without installing outputs. The staged directory is removed afterward. A successful installed release writes `nazar/team_release_report.json` with the mismatch list, override flag, output hashes and matching run ID.

## Failure and update behavior

- Any failed stage stops the command. Working outputs remain unchanged during generation and testing.
- If a tracked working file changes during the build, installation stops rather than overwriting that edit.
- If opening inventory no longer matches the new baseline, Elia updates the assumption ledger; the coordinator does not silently change it.
- Files are individually replaced and the manifest is written last. This is not an atomic directory swap; the dashboard rejects an intermediate mixed release. A caught installation failure restores previous output bytes. After abrupt process termination, rerun before refreshing.
- Only one coordinated release can run at a time. The ignored lock is `nazar/.state/team-release.lock`. If a crash leaves it behind, confirm no release process remains before removing that lock.
- Close editing sessions during publication. Do not run independent producer scripts concurrently with the coordinator.

After success, inspect `git diff`, commit all generated outputs and the report together, and push one PR. After it merges, teammates pull and click **Refresh current source** in The Intelligent FBO. This command does not commit, push, fetch, approve a forecast, or authorize an operation.

The older `marvin/person_2_forecasting/run_provisional.py` is retained for compatibility, but the coordinated command above is the team entry point. Do not run both for one release.
