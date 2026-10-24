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

from readiness.data import read_paths, native_paths
from readiness.team_adapter import NATIVE_PATHS, load_native


def verify(repo=REPO):
    import pandas as pd

    repo = Path(repo)
    paths = native_paths(repo)
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
    def compare(actual, saved_key, keys):
        saved = pd.read_csv(paths[saved_key])
        pd.testing.assert_frame_equal(
            actual.sort_values(keys).reset_index(drop=True),
            saved.sort_values(keys).reset_index(drop=True),
            check_dtype=False, check_exact=False, rtol=1e-9, atol=1e-7,
        )
        return len(saved)

    extended = 'p3_ordinary' in paths
    standard_carry = {}
    actual_table, actual_plans = model.run(demand, assumptions, carryover=standard_carry) if extended else model.run(demand, assumptions)
    resource_rows = compare(actual_table, 'p3_resources', ['scenario', 'date'])
    if actual_plans != json.loads(raw['p3_recommendations'])['scenarios']:
        raise ValueError('P3 recommendations/impact differ from a run using current P2 inputs. Regenerate P3 before presenting.')
    extension_rows = {}
    if extended:
        delayed_carry = {}
        delayed_table, delayed_plans = model.run(demand, assumptions, 'departure_delay_24h', delayed_carry)
        extension_rows['delayed_resources'] = compare(delayed_table, 'p3_delay_resources', ['scenario', 'date'])
        if delayed_plans != json.loads(raw['p3_delay_recommendations'])['scenarios']:
            raise ValueError('Delayed recommendations/impact do not match current inputs.')
        ordinary_table, ordinary_carry = model.run_ordinary(model.load_ordinary_demand(repo / 'marvin/person_2_forecasting'), assumptions)
        extension_rows['ordinary_parking'] = compare(ordinary_table, 'p3_ordinary', ['date'])
        carry_rows = [{'variant': 'ordinary', 'scenario': 'ordinary', **ordinary_carry}]
        for variant, values in [('standard', standard_carry), ('departure_delay_24h', delayed_carry)]:
            carry_rows.extend({'variant': variant, 'scenario': scenario, **row} for scenario, row in values.items())
        extension_rows['carryover'] = compare(pd.DataFrame(carry_rows).assign(data_status='provisional'), 'p3_carryover', ['variant', 'scenario'])
    # Detect teammates editing inputs while the simulation was running.
    if raw != read_paths(paths) or model_bytes != model_path.read_bytes():
        raise ValueError('Inputs changed during verification; retry with a stable set.')
    return {
        'status': 'matched',
        'dataset_version': bundle['version'],
        'resource_rows': resource_rows,
        'extension_rows': extension_rows,
        'scenarios': sorted(actual_plans),
        'sha256': {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [*paths.values(), model_path]},
        'meaning': 'All supplied P3 standard/ordinary/delay resources, recommendations, impact and carryover reproduce from current P2 intervals and P3 assumptions. This does not validate forecast accuracy, source evidence or safe capacity.',
    }


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), indent=2))
    except (AssertionError, ValueError, OSError, ImportError, KeyError) as exc:
        print(f'Pipeline verification failed: {exc}', file=sys.stderr)
        sys.exit(1)
