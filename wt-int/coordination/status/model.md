state: PARTIAL
task: T3 model signatures, schema skeletons, and contract tests
files: model/__init__.py, model/forecast.py, model/occupancy.py, model/recommend.py, model/impact.py, model/disruption.py, tests/test_contract.py, coordination/status/model.md
tests: n/a (dependencies absent; syntax compilation passed)
commit: n/a
requests: app supervisor to run pytest with project dependencies and commit these files; Git worktree metadata is read-only here
