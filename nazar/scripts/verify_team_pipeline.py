"""Read-only check that committed P3 outputs reproduce from current P2 inputs.

Run from any directory; requires P3's numpy and pandas dependencies.
No producer output or dashboard state is overwritten. This checks numerical
coherence, not the validity of the inputs or accuracy of the models.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
sys.path.insert(0, str(APP))

from readiness.data import read_paths
from readiness.team_adapter import NATIVE_PATHS, load_native


def verify(repo=REPO):
    import pandas as pd

    repo = Path(repo)
    paths = {k: repo / p for k, p in NATIVE_PATHS.items()}
    raw = read_paths(paths)
    bundle = load_native(raw)
    model_path = repo / 'elia' / 'parking_optimizer.py'
    model_bytes = model_path.read_bytes()
    spec = importlib.util.spec_from_file_location('team_parking_verification', model_path)
    model = importlib.util.module_from_spec(spec)
    old_bytecode_setting = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(model)
    finally:
        sys.dont_write_bytecode = old_bytecode_setting
    demand = model.load_demand(repo / 'marvin' / 'person_2_forecasting')
    assumptions = model.load_assumptions(paths['p3_assumptions'])
    actual_table, actual_plans = model.run(demand, assumptions)
    saved_table = pd.read_csv(paths['p3_resources'])
    keys = ['scenario', 'date']
    pd.testing.assert_frame_equal(
        actual_table.sort_values(keys).reset_index(drop=True),
        saved_table.sort_values(keys).reset_index(drop=True),
        check_dtype=False, check_exact=False, rtol=1e-9, atol=1e-7,
    )
    if actual_plans != json.loads(raw['p3_recommendations'])['scenarios']:
        raise ValueError('P3 recommendations/impact differ from a run using current P2 inputs. Regenerate P3 before presenting.')
    # Detect teammates editing inputs while the simulation was running.
    if raw != read_paths(paths) or model_bytes != model_path.read_bytes():
        raise ValueError('Inputs changed during verification; retry with a stable set.')
    return {
        'status': 'matched',
        'dataset_version': bundle['version'],
        'resource_rows': len(saved_table),
        'scenarios': sorted(actual_plans),
        'sha256': {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [*paths.values(), model_path]},
        'meaning': 'Current P3 resources, recommendations and impact reproduce from current P2 intervals and P3 assumptions. This does not validate forecast accuracy, source evidence or safe capacity.',
    }


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), indent=2))
    except (AssertionError, ValueError, OSError, ImportError, KeyError) as exc:
        print(f'Pipeline verification failed: {exc}', file=sys.stderr)
        sys.exit(1)
